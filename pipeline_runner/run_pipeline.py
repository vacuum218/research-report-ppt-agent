"""Atomic single-command orchestration for the implemented pipeline stages."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from document_bundle.bundle import parse_pdf
from document_bundle.config import MinerUConfig
from document_bundle.markdown import build_from_markdown
from document_bundle.parser.mineru_client import MinerUClient
from document_intelligence import load_document_intelligence
from outline_generator.generate_outline import main as generate_outline_main
from ppt_engine.compiled_plan import validate_compiled_plan
from ppt_engine.abstract_layout import load_abstract_layout_catalog
from ppt_engine.compiler import compile_layout_plan
from ppt_engine.preflight import preflight_layouts
from ppt_engine.renderer import render_compiled_plan
from visualization_generator.audit import (
    audit_visualization_artifacts,
    serialize_metric_group_catalog,
    serialize_numeric_fact_ledger,
)
from visualization_generator.generate_visualizations import generate_visualizations
from visualization_generator.generator import GenerationIssue
from visualization_generator.manifest import (
    canonical_sha256,
    load_visualization_manifest,
    visual_type,
)
from visualization_generator.numeric_facts import build_numeric_fact_ledger
from visualization_generator.planning import build_candidate_report, plan_visualizations


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = PROJECT_ROOT / "schemas"
DEFAULT_TEMPLATE = PROJECT_ROOT / "templates/financial_report_template_v1.pptx"
SCHEMA_PATHS = {
    "document_bundle": SCHEMA_ROOT / "document_bundle.schema.json",
    "slide_outline": SCHEMA_ROOT / "slide_outline.schema.json",
    "visualization": SCHEMA_ROOT / "visualization.schema.json",
    "visualization_manifest": SCHEMA_ROOT / "visualization_manifest.schema.json",
    "template_profile": SCHEMA_ROOT / "template_profile.schema.json",
    "compiled_layout_plan": SCHEMA_ROOT / "compiled_layout_plan.schema.json",
    "run_manifest": SCHEMA_ROOT / "run_manifest.schema.json",
    "numeric_fact_ledger": SCHEMA_ROOT / "numeric_fact_ledger.schema.json",
    "metric_group": SCHEMA_ROOT / "metric_group.schema.json",
}


class PipelineRunError(RuntimeError):
    """A stage-qualified failure that prevents publishing pipeline output."""

    def __init__(self, stage: str, message: str):
        super().__init__(f"pipeline stage={stage}: {message}")
        self.stage = stage
        self.message = message


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineRunError(label, f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PipelineRunError(label, f"{path} root must be an object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _safe_failure_message(value: object) -> str:
    message = str(value).replace("\r", " ").replace("\n", " ")
    message = re.sub(
        r"(?i)(authorization:\s*bearer\s+)[^\s]+",
        r"\1<redacted>",
        message,
    )
    message = re.sub(
        r"(?i)(api[_-]?key\s*[=:]\s*)[^\s,;]+",
        r"\1<redacted>",
        message,
    )
    return message[:1000]


def _write_failure_report(
    output_directory: Path,
    error: PipelineRunError,
    *,
    last_successful_stage: str | None,
) -> None:
    try:
        _write_json(
            output_directory.with_name(output_directory.name + ".failure")
            / "failure.json",
            {
                "schema_version": "1.0.0",
                "status": "failed",
                "failed_stage": error.stage,
                "last_successful_stage": last_successful_stage,
                "error_code": "pipeline_stage_failed",
                "message": _safe_failure_message(error.message),
                "published_pptx": False,
            },
        )
    except OSError:
        # Diagnostics must never hide the original pipeline failure.
        return


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_.-") or "visualization"


def _validate_schema(
    value: Mapping[str, Any],
    schema_path: Path,
    *,
    stage: str,
) -> None:
    schema = _load_json(schema_path, f"{stage}-schema")
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise PipelineRunError(stage, errors[0].message)


def _source_bundle_directory(input_path: Path) -> Path | None:
    if input_path.is_dir() and (input_path / "document.json").is_file():
        return input_path
    if input_path.is_file() and input_path.name == "document.json":
        return input_path.parent
    return None


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _materialize_document_bundle(
    input_path: Path,
    bundle_directory: Path,
) -> None:
    source_bundle = _source_bundle_directory(input_path)
    if source_bundle is not None:
        shutil.copytree(source_bundle, bundle_directory)
        return
    if not input_path.is_file():
        raise PipelineRunError("document_bundle", f"input does not exist: {input_path}")
    if input_path.suffix.casefold() == ".pdf":
        parse_root = bundle_directory.parent / "_pdf_parse"
        try:
            with MinerUClient(MinerUConfig()) as client:
                parsed_bundle, _, validation = parse_pdf(
                    input_path,
                    parse_root,
                    input_path.stem,
                    client,
                )
        except Exception as exc:
            raise PipelineRunError("document_bundle", str(exc)) from exc
        if validation.get("status") == "failed":
            raise PipelineRunError(
                "document_bundle",
                "PDF conversion produced a failed validation result",
            )
        shutil.copytree(parsed_bundle, bundle_directory)
        shutil.rmtree(parse_root)
        return
    try:
        _, validation = build_from_markdown(
            input_path,
            bundle_directory,
            input_path.stem,
            source_format="auto",
        )
    except (OSError, ValueError) as exc:
        raise PipelineRunError("document_bundle", str(exc)) from exc
    if validation.get("status") == "failed":
        raise PipelineRunError(
            "document_bundle",
            "text conversion produced a failed validation result",
        )


def _materialize_outline(
    *,
    bundle_directory: Path,
    outline_path: Path,
    outline_input: Path | None,
    outline_model: str | None,
    outline_base_url: str | None,
    outline_api_provider: str | None,
    outline_max_tokens: int | None,
    outline_max_attempts: int | None,
    outline_timeout: int | None,
) -> dict[str, Any]:
    if outline_input is not None:
        outline = _load_json(outline_input, "outline")
        _validate_schema(
            outline,
            SCHEMA_PATHS["slide_outline"],
            stage="outline",
        )
        _write_json(outline_path, outline)
        return outline

    forwarded = [str(bundle_directory), "-o", str(outline_path)]
    optional_values = (
        ("--model", outline_model),
        ("--base-url", outline_base_url),
        ("--api-provider", outline_api_provider),
        ("--max-tokens", outline_max_tokens),
        ("--max-attempts", outline_max_attempts),
        ("--timeout", outline_timeout),
    )
    for option, value in optional_values:
        if value is not None:
            forwarded.extend([option, str(value)])
    exit_code = generate_outline_main(forwarded)
    if exit_code != 0 or not outline_path.is_file():
        raise PipelineRunError(
            "outline",
            f"outline generator exited with status {exit_code}",
        )
    return _load_json(outline_path, "outline")


def _write_visualizations(
    *,
    directory: Path,
    outline: Mapping[str, Any],
    document_source_sha256: str,
    artifacts: Sequence[Any],
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": "3.0.0",
        "outline_sha256": canonical_sha256(outline),
        "document_source_sha256": document_source_sha256,
        "asset_root": "../document_bundle",
        "bindings": [],
    }
    for artifact in artifacts:
        filename = (
            f"{_safe_name(artifact.slide_id)}__"
            f"{_safe_name(artifact.visualization_id)}.json"
        )
        _write_json(directory / filename, artifact.data)
        artifact_type = visual_type(artifact.data)
        if artifact_type is None:
            raise PipelineRunError(
                "visualization",
                f"cannot identify type for {artifact.visualization_id}",
            )
        manifest["bindings"].append(
            {
                "slide_id": artifact.slide_id,
                "visualization_id": artifact.visualization_id,
                "visual_type": artifact_type,
                "sources": list(artifact.sources),
                "visualization_file": filename,
            }
        )
    manifest_path = directory / "visualization_manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def _partition_generation_issues(
    outline: Mapping[str, Any],
    issues: Sequence[GenerationIssue],
) -> tuple[list[GenerationIssue], list[GenerationIssue]]:
    """Downgrade safe data-absence skips; keep explicit verification failures blocking."""

    explicit_ids = {
        str(candidate.get("candidate_id"))
        for slide in outline.get("slides", [])
        if isinstance(slide, Mapping)
        for candidate in slide.get("visual_candidates", [])
        if isinstance(candidate, Mapping) and candidate.get("candidate_id")
    }
    semantic_skip_codes = (
        "reject.mixed_metric",
        "reject.mixed_measure_kind",
        "reject.mixed_unit_family",
        "reject.mixed_unit_scale",
        "reject.mixed_currency",
        "reject.mixed_entity",
        "reject.mixed_scope",
        "reject.mixed_scenario",
        "reject.invalid_forecast_boundary",
        "reject.incomplete_metric_typing",
        "reject.invalid_category_count",
    )
    warnings = [
        issue
        for issue in issues
        if issue.visualization_id not in explicit_ids
        or issue.reason == "no_traceable_source_data"
        or any(code in issue.reason for code in semantic_skip_codes)
    ]
    warning_ids = {id(issue) for issue in warnings}
    blocking = [issue for issue in issues if id(issue) not in warning_ids]
    return blocking, warnings


def _generation_warning_report(
    issues: Sequence[GenerationIssue],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "status": "completed_with_warnings" if issues else "completed",
        "warning_count": len(issues),
        "warnings": [
            {
                "slide_id": issue.slide_id,
                "visualization_id": issue.visualization_id,
                "visual_type": issue.visual_type,
                "reason": issue.reason,
                "disposition": "skipped_unrenderable_candidate",
            }
            for issue in issues
        ],
    }


def _finalize_compiled_plan_asset_root(
    plan: Mapping[str, Any],
    final_asset_root: Path,
) -> dict[str, Any]:
    finalized = deepcopy(dict(plan))
    finalized["asset_root"] = str(final_asset_root.resolve())
    finalized["plan_id"] = "plan_0000000000000000"
    finalized["plan_id"] = "plan_" + canonical_sha256(finalized)[:16]
    schema = _load_json(
        SCHEMA_PATHS["compiled_layout_plan"],
        "compiled-layout-plan-schema",
    )
    errors = validate_compiled_plan(finalized, schema)
    if errors:
        raise PipelineRunError("compile", errors[0])
    return finalized


def _input_hash_path(input_path: Path) -> Path:
    source_bundle = _source_bundle_directory(input_path)
    return (
        source_bundle / "document.json"
        if source_bundle is not None
        else input_path
    )


def _run_manifest(
    *,
    input_path: Path,
    outline: Mapping[str, Any],
    manifest: Mapping[str, Any],
    template_profile: Mapping[str, Any],
    template_profile_path: Path,
    template_path: Path,
    compiled_plan: Mapping[str, Any],
    staging_directory: Path,
    visualization_warning_count: int,
) -> dict[str, Any]:
    artifact_paths = [
        staging_directory / "document_bundle/document.json",
        staging_directory / "slide_outline.json",
        staging_directory / "numeric_fact_ledger.json",
        staging_directory / "metric_groups.json",
        staging_directory / "numeric_audit.json",
        staging_directory / "visualization_warnings.json",
        staging_directory / "template_profile.json",
        staging_directory / "visualizations/visualization_manifest.json",
        *sorted(
            path
            for path in (staging_directory / "visualizations").glob("*.json")
            if path.name != "visualization_manifest.json"
        ),
        staging_directory / "compiled_layout_plan.json",
        staging_directory / "presentation.pptx",
    ]
    return {
        "schema_version": "1.0.0",
        "status": "completed",
        "input": {
            "path": str(input_path.resolve()),
            "sha256": _sha256_file(_input_hash_path(input_path)),
        },
        "schemas": {
            name: {
                "path": str(path.resolve()),
                "sha256": _sha256_file(path),
            }
            for name, path in SCHEMA_PATHS.items()
        },
        "hashes": {
            "outline_sha256": canonical_sha256(outline),
            "visualization_manifest_sha256": canonical_sha256(manifest),
            "template_profile_sha256": canonical_sha256(template_profile),
            "template_sha256": _sha256_file(template_path),
            "compiled_layout_plan_sha256": canonical_sha256(compiled_plan),
            "presentation_sha256": _sha256_file(
                staging_directory / "presentation.pptx"
            ),
        },
        "template": {
            "profile_path": str(template_profile_path.resolve()),
            "file_path": str(template_path.resolve()),
        },
        "warnings": {
            "visualization_count": visualization_warning_count,
            "file": "visualization_warnings.json",
        },
        "artifacts": [
            {
                "path": path.relative_to(staging_directory).as_posix(),
                "sha256": _sha256_file(path),
            }
            for path in artifact_paths
        ],
    }


def run_pipeline(
    input_path: Path,
    *,
    template_profile_path: Path,
    output_directory: Path,
    template_path: Path = DEFAULT_TEMPLATE,
    outline_input: Path | None = None,
    outline_model: str | None = None,
    outline_base_url: str | None = None,
    outline_api_provider: str | None = None,
    outline_max_tokens: int | None = None,
    outline_max_attempts: int | None = None,
    outline_timeout: int | None = None,
    candidate_mode: str = "shadow",
) -> Path:
    """Run all stages and publish output only after every stage succeeds."""

    input_path = input_path.resolve()
    output_directory = output_directory.resolve()
    template_profile_path = template_profile_path.resolve()
    template_path = template_path.resolve()
    if not input_path.exists():
        raise PipelineRunError("preflight", f"input does not exist: {input_path}")
    if not template_profile_path.is_file():
        raise PipelineRunError(
            "preflight",
            f"template profile does not exist: {template_profile_path}",
        )
    if not template_path.is_file():
        raise PipelineRunError("preflight", f"template does not exist: {template_path}")
    source_bundle = _source_bundle_directory(input_path)
    if source_bundle is not None and _is_within(output_directory, source_bundle):
        raise PipelineRunError(
            "preflight",
            "output directory cannot be inside the input DocumentBundle",
        )
    if output_directory.exists():
        if not output_directory.is_dir():
            raise PipelineRunError(
                "preflight",
                f"output path is not a directory: {output_directory}",
            )
        if any(output_directory.iterdir()):
            raise PipelineRunError(
                "preflight",
                f"output directory is not empty: {output_directory}",
            )

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    staging_directory = Path(
        tempfile.mkdtemp(
            prefix=f".{output_directory.name}.staging-",
            dir=output_directory.parent,
        )
    )
    last_successful_stage: str | None = None
    try:
        bundle_directory = staging_directory / "document_bundle"
        _materialize_document_bundle(input_path, bundle_directory)
        try:
            snapshot = load_document_intelligence(
                bundle_directory,
                SCHEMA_PATHS["document_bundle"],
            )
        except Exception as exc:
            raise PipelineRunError("document_bundle", str(exc)) from exc
        last_successful_stage = "document_bundle"

        outline_path = staging_directory / "slide_outline.json"
        outline = _materialize_outline(
            bundle_directory=bundle_directory,
            outline_path=outline_path,
            outline_input=outline_input.resolve() if outline_input else None,
            outline_model=outline_model,
            outline_base_url=outline_base_url,
            outline_api_provider=outline_api_provider,
            outline_max_tokens=outline_max_tokens,
            outline_max_attempts=outline_max_attempts,
            outline_timeout=outline_timeout,
        )
        last_successful_stage = "outline"

        try:
            candidate_report = build_candidate_report(
                outline,
                snapshot,
                candidate_mode=candidate_mode,
            )
            _write_json(
                staging_directory / "candidate_locator_report.json",
                candidate_report,
            )
        except Exception as exc:
            raise PipelineRunError("candidate_locator", str(exc)) from exc
        last_successful_stage = "candidate_locator"

        try:
            planned_visuals = plan_visualizations(
                outline,
                snapshot,
                candidate_mode=candidate_mode,
            )
            layout_preflight = preflight_layouts(
                outline,
                planned_visuals,
                load_abstract_layout_catalog(),
            )
            _write_json(
                staging_directory / "layout_preflight.json",
                layout_preflight,
            )
            if layout_preflight["status"] != "passed":
                first_error = next(
                    issue
                    for page in layout_preflight["pages"]
                    for issue in page["issues"]
                    if issue["severity"] == "error"
                )
                raise PipelineRunError("layout_preflight", first_error["message"])
        except PipelineRunError:
            raise
        except Exception as exc:
            raise PipelineRunError("layout_preflight", str(exc)) from exc
        last_successful_stage = "layout_preflight"

        try:
            artifacts, issues = generate_visualizations(
                outline,
                snapshot,
                candidate_mode=candidate_mode,
            )
        except Exception as exc:
            raise PipelineRunError("visualization", str(exc)) from exc
        blocking_issues, warning_issues = _partition_generation_issues(
            outline,
            issues,
        )
        if blocking_issues:
            raise PipelineRunError(
                "visualization",
                blocking_issues[0].format(),
            )
        last_successful_stage = "visualization"
        _write_json(
            staging_directory / "visualization_warnings.json",
            _generation_warning_report(warning_issues),
        )
        try:
            ledger = build_numeric_fact_ledger(snapshot)
            numeric_audit = audit_visualization_artifacts(artifacts, ledger)
        except Exception as exc:
            raise PipelineRunError("numeric_audit", str(exc)) from exc
        numeric_ledger_data = serialize_numeric_fact_ledger(ledger)
        metric_group_data = serialize_metric_group_catalog(artifacts)
        _validate_schema(
            numeric_ledger_data,
            SCHEMA_PATHS["numeric_fact_ledger"],
            stage="numeric_fact_ledger",
        )
        _validate_schema(
            metric_group_data,
            SCHEMA_PATHS["metric_group"],
            stage="metric_group",
        )
        _write_json(
            staging_directory / "numeric_fact_ledger.json",
            numeric_ledger_data,
        )
        _write_json(
            staging_directory / "metric_groups.json",
            metric_group_data,
        )
        _write_json(staging_directory / "numeric_audit.json", numeric_audit)
        last_successful_stage = "numeric_audit"

        try:
            manifest_path = _write_visualizations(
                directory=staging_directory / "visualizations",
                outline=outline,
                document_source_sha256=str(
                    snapshot.metadata.get("source_sha256") or "0" * 64
                ),
                artifacts=artifacts,
            )
            manifest = load_visualization_manifest(manifest_path)
        except Exception as exc:
            raise PipelineRunError("manifest", str(exc)) from exc
        last_successful_stage = "manifest"

        template_profile = _load_json(template_profile_path, "template-profile")
        _write_json(
            staging_directory / "template_profile.json",
            template_profile,
        )
        try:
            compiled_plan = compile_layout_plan(
                outline,
                template_profile,
                manifest,
            )
        except Exception as exc:
            raise PipelineRunError("compile", str(exc)) from exc
        last_successful_stage = "compile"
        try:
            render_compiled_plan(
                compiled_plan,
                template_path=template_path,
                output_path=staging_directory / "presentation.pptx",
            )
        except Exception as exc:
            raise PipelineRunError("render", str(exc)) from exc
        last_successful_stage = "render"
        finalized_plan = _finalize_compiled_plan_asset_root(
            compiled_plan,
            output_directory / "document_bundle",
        )
        compiled_plan_path = staging_directory / "compiled_layout_plan.json"
        _write_json(compiled_plan_path, finalized_plan)

        manifest_data = _load_json(manifest_path, "visualization-manifest")
        run_manifest = _run_manifest(
            input_path=input_path,
            outline=outline,
            manifest=manifest_data,
            template_profile=template_profile,
            template_profile_path=template_profile_path,
            template_path=template_path,
            compiled_plan=finalized_plan,
            staging_directory=staging_directory,
            visualization_warning_count=len(warning_issues),
        )
        _validate_schema(
            run_manifest,
            SCHEMA_PATHS["run_manifest"],
            stage="run_manifest",
        )
        _write_json(staging_directory / "run_manifest.json", run_manifest)

        if output_directory.exists():
            output_directory.rmdir()
        staging_directory.replace(output_directory)
        return output_directory
    except PipelineRunError as exc:
        _write_failure_report(
            output_directory,
            exc,
            last_successful_stage=last_successful_stage,
        )
        raise
    except Exception as exc:
        error = PipelineRunError("execution", str(exc))
        _write_failure_report(
            output_directory,
            error,
            last_successful_stage=last_successful_stage,
        )
        raise error from exc
    finally:
        if staging_directory.exists():
            shutil.rmtree(staging_directory)

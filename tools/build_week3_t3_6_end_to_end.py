#!/usr/bin/env python3
"""Build the Week 3 T3.6 end-to-end evidence and numeric-audit deck."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from document_intelligence import load_document_intelligence
from ppt_engine.compiler import compile_layout_plan
from ppt_engine.renderer import render_compiled_plan
from tools.build_template_profile import build_template_profile
from visualization_generator.audit import (
    audit_visualization_artifacts,
    serialize_numeric_fact_ledger,
)
from visualization_generator.generate_visualizations import (
    generate_visualizations,
)
from visualization_generator.manifest import (
    canonical_sha256,
    load_visualization_manifest,
    visual_type,
)
from visualization_generator.numeric_facts import build_numeric_fact_ledger
from visualization_generator.planning import plan_visualizations


FIXTURE_ROOT = PROJECT_ROOT / "examples/week3_t3_6"
DEFAULT_BUNDLE = FIXTURE_ROOT / "document_bundle"
DEFAULT_OUTLINE = FIXTURE_ROOT / "outline.json"
DEFAULT_EXPECTATIONS = FIXTURE_ROOT / "expectations.json"
DEFAULT_LAYOUT_MAP = PROJECT_ROOT / "templates/template_layout_map.json"
DEFAULT_TEMPLATE = PROJECT_ROOT / "templates/financial_report_template_v1.pptx"
DEFAULT_BUNDLE_SCHEMA = PROJECT_ROOT / "schemas/document_bundle.schema.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "output/week3_t3.6_end_to_end"


class T36AcceptanceError(ValueError):
    """Raised when a fixed T3.6 scenario does not meet its contract."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T36AcceptanceError(f"cannot load {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise T36AcceptanceError(f"{label} root must be an object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_.-") or "visualization"


def _check_scenarios(
    *,
    artifacts: Sequence[Any],
    plans: Sequence[Any],
    expectations: Mapping[str, Any],
) -> dict[str, Any]:
    artifacts_by_slide = {artifact.slide_id: artifact for artifact in artifacts}
    plans_by_slide: dict[str, list[Any]] = {}
    for plan in plans:
        plans_by_slide.setdefault(plan.slide_id, []).append(plan)
    results: list[dict[str, Any]] = []

    for scenario in expectations.get("successful_scenarios", []):
        slide_id = str(scenario["slide_id"])
        artifact = artifacts_by_slide.get(slide_id)
        slide_plans = plans_by_slide.get(slide_id, [])
        if len(slide_plans) != 1:
            raise T36AcceptanceError(
                f"successful scenario {slide_id} must produce exactly one plan"
            )
        if artifact is None:
            raise T36AcceptanceError(
                f"successful scenario {slide_id} produced no Visualization"
            )
        actual_type = visual_type(artifact.data)
        if actual_type != scenario["visual_type"]:
            raise T36AcceptanceError(
                f"{slide_id} expected {scenario['visual_type']}, got {actual_type}"
            )
        expected_chart_type = scenario.get("chart_type")
        if expected_chart_type is not None and (
            artifact.data.get("chart_type") != expected_chart_type
        ):
            raise T36AcceptanceError(
                f"{slide_id} expected chart_type={expected_chart_type}, "
                f"got {artifact.data.get('chart_type')}"
            )
        results.append(
            {
                **dict(scenario),
                "status": "passed",
                "visualization_id": artifact.visualization_id,
            }
        )

    for scenario in expectations.get("rejected_scenarios", []):
        slide_id = str(scenario["slide_id"])
        if plans_by_slide.get(slide_id):
            raise T36AcceptanceError(
                f"rejected scenario {slide_id} unexpectedly produced a plan"
            )
        if slide_id in artifacts_by_slide:
            raise T36AcceptanceError(
                f"rejected scenario {slide_id} unexpectedly produced a Visualization"
            )
        results.append({**dict(scenario), "status": "rejected_as_expected"})

    return {
        "schema_version": "1.0.0",
        "status": "passed",
        "successful_count": len(expectations.get("successful_scenarios", [])),
        "rejected_count": len(expectations.get("rejected_scenarios", [])),
        "scenarios": results,
    }


def _write_manifest(
    *,
    output_directory: Path,
    outline: Mapping[str, Any],
    snapshot: Any,
    artifacts: Sequence[Any],
) -> Path:
    visualization_directory = output_directory / "visualizations"
    visualization_directory.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": "3.0.0",
        "outline_sha256": canonical_sha256(outline),
        "document_source_sha256": str(
            snapshot.metadata.get("source_sha256") or "0" * 64
        ),
        "asset_root": str(snapshot.bundle_directory.resolve()),
        "bindings": [],
    }
    for artifact in artifacts:
        filename = (
            f"{_safe_name(artifact.slide_id)}__"
            f"{_safe_name(artifact.visualization_id)}.json"
        )
        _write_json(visualization_directory / filename, artifact.data)
        manifest["bindings"].append(
            {
                "slide_id": artifact.slide_id,
                "visualization_id": artifact.visualization_id,
                "visual_type": visual_type(artifact.data),
                "sources": list(artifact.sources),
                "visualization_file": filename,
            }
        )
    manifest_path = visualization_directory / "visualization_manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def build_acceptance_output(
    *,
    bundle_path: Path = DEFAULT_BUNDLE,
    outline_path: Path = DEFAULT_OUTLINE,
    expectations_path: Path = DEFAULT_EXPECTATIONS,
    layout_map_path: Path = DEFAULT_LAYOUT_MAP,
    template_path: Path = DEFAULT_TEMPLATE,
    output_directory: Path = DEFAULT_OUTPUT,
) -> dict[str, Path]:
    outline = _load_json(outline_path, "T3.6 Outline")
    expectations = _load_json(expectations_path, "T3.6 expectations")
    layout_map = _load_json(layout_map_path, "Layout Map")
    snapshot = load_document_intelligence(bundle_path, DEFAULT_BUNDLE_SCHEMA)

    plans = plan_visualizations(outline, snapshot)
    artifacts, issues = generate_visualizations(outline, snapshot)
    if issues:
        raise T36AcceptanceError(issues[0].format())
    scenario_results = _check_scenarios(
        artifacts=artifacts,
        plans=plans,
        expectations=expectations,
    )

    ledger = build_numeric_fact_ledger(snapshot)
    numeric_audit = audit_visualization_artifacts(artifacts, ledger)
    output_directory.mkdir(parents=True, exist_ok=True)
    ledger_path = output_directory / "numeric_fact_ledger.json"
    audit_path = output_directory / "numeric_audit.json"
    scenario_path = output_directory / "scenario_results.json"
    _write_json(ledger_path, serialize_numeric_fact_ledger(ledger))
    _write_json(audit_path, numeric_audit)
    _write_json(scenario_path, scenario_results)

    manifest_path = _write_manifest(
        output_directory=output_directory,
        outline=outline,
        snapshot=snapshot,
        artifacts=artifacts,
    )
    manifest = load_visualization_manifest(manifest_path)

    template_profile = build_template_profile(
        layout_map,
        template_path,
        profile_id="week3-t3.6-financial-report-v1",
    )
    profile_path = output_directory / "template_profile.json"
    _write_json(profile_path, template_profile)
    compiled_plan = compile_layout_plan(
        outline,
        template_profile,
        manifest,
    )
    compiled_plan_path = output_directory / "compiled_layout_plan.json"
    _write_json(compiled_plan_path, compiled_plan)

    presentation_path = output_directory / "week3_t3.6_end_to_end.pptx"
    render_compiled_plan(
        compiled_plan,
        template_path=template_path,
        output_path=presentation_path,
    )
    return {
        "ledger": ledger_path,
        "audit": audit_path,
        "scenarios": scenario_path,
        "manifest": manifest_path,
        "profile": profile_path,
        "compiled_plan": compiled_plan_path,
        "presentation": presentation_path,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Week 3 T3.6 end-to-end numeric-audit deck"
    )
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--outline", type=Path, default=DEFAULT_OUTLINE)
    parser.add_argument(
        "--expectations",
        type=Path,
        default=DEFAULT_EXPECTATIONS,
    )
    parser.add_argument("--layout-map", type=Path, default=DEFAULT_LAYOUT_MAP)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("-o", "--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        outputs = build_acceptance_output(
            bundle_path=args.bundle,
            outline_path=args.outline,
            expectations_path=args.expectations,
            layout_map_path=args.layout_map,
            template_path=args.template,
            output_directory=args.output_dir,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Created T3.6 acceptance deck: {outputs['presentation']}")
    print("Successful scenarios: 3")
    print("Rejected scenarios: 2")
    print(f"Numeric audit: {outputs['audit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

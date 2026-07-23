"""Compile Outline, Visualization Manifest, and Template Profile into a plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from tools.build_template_profile import validate_template_profile
from visualization_generator.manifest import (
    LoadedVisualizationManifest,
    VisualizationManifestError,
    canonical_sha256,
    load_visualization_manifest,
)

from .compiled_plan import validate_compiled_plan
from .layout_resolver import LayoutResolutionError, resolve_profile_layout


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PROFILE_SCHEMA = PROJECT_ROOT / "schemas/template_profile.schema.json"
COMPILED_PLAN_SCHEMA = PROJECT_ROOT / "schemas/compiled_layout_plan.schema.json"
OUTLINE_SCHEMA = PROJECT_ROOT / "schemas/slide_outline.schema.json"
SUPPORTED_CHART_TYPES = {"line", "column", "bar", "area", "pie"}


class LayoutCompileError(ValueError):
    """Raised when deterministic layout compilation cannot complete."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise LayoutCompileError(f"cannot load {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LayoutCompileError(f"{label} root must be an object")
    return value


def _schema_errors(
    value: Mapping[str, Any], schema: Mapping[str, Any]
) -> list[str]:
    return [
        error.message
        for error in sorted(
            Draft202012Validator(schema).iter_errors(value),
            key=lambda error: list(error.absolute_path),
        )
    ]


def _source_value(
    source: str,
    slide: Mapping[str, Any],
    metadata: Mapping[str, Any],
    page_number: int,
) -> Any:
    if source == "compiler.page_number":
        return page_number
    if source == "compiler.cover_meta":
        return "  |  ".join(
            str(metadata[key])
            for key in ("stock_code", "report_date")
            if metadata.get(key)
        )
    prefix, _, field = source.partition(".")
    owner = slide if prefix == "slide" else metadata if prefix == "metadata" else {}
    value = owner.get(field)
    if source == "metadata.report_title" and not value:
        return slide.get("title", "")
    return value


def _compile_binding(
    binding: Mapping[str, Any],
    slide: Mapping[str, Any],
    metadata: Mapping[str, Any],
    page_number: int,
) -> dict[str, Any]:
    value = _source_value(str(binding["source"]), slide, metadata, page_number)
    operation = str(binding["operation"])
    if operation == "set_text":
        if isinstance(value, list):
            value = str(binding.get("separator", ", ")).join(str(item) for item in value)
        if value is None:
            value = ""
        return {
            "op": "set_text",
            "binding_id": binding["binding_id"],
            "target": dict(binding["target"]),
            "value": value,
        }
    if operation == "set_bullets":
        values = value if isinstance(value, list) else []
        return {
            "op": "set_bullets",
            "binding_id": binding["binding_id"],
            "target": dict(binding["target"]),
            "values": [
                item for item in values if isinstance(item, (str, int, float, bool))
            ],
        }
    if operation == "set_repeated_text":
        values = value if isinstance(value, list) else []
        max_items = int(binding.get("max_items", len(binding["targets"])))
        return {
            "op": "set_repeated_text",
            "binding_id": binding["binding_id"],
            "targets": [dict(group) for group in binding["targets"]],
            "values": [
                item
                for item in values[:max_items]
                if isinstance(item, (str, int, float, bool, Mapping))
            ],
        }
    raise LayoutCompileError(f"unsupported binding operation: {operation!r}")


def _check_capacity(
    slide_id: str,
    slot: Mapping[str, Any],
    visualization: Mapping[str, Any],
) -> None:
    capacity = slot.get("capacity", {})
    data = visualization["data"]
    kind = slot["kind"]
    if kind == "chart":
        chart_type = str(data.get("chart_type", ""))
        if chart_type not in SUPPORTED_CHART_TYPES:
            raise LayoutCompileError(
                f"slide {slide_id}: chart_type {chart_type!r} is not renderer-supported"
            )
        limits = (
            ("categories", "max_categories"),
            ("series", "max_series"),
        )
    elif kind == "table":
        limits = (
            ("rows", "max_rows"),
            ("columns", "max_columns"),
        )
    else:
        limits = ()
    for data_key, limit_key in limits:
        limit = capacity.get(limit_key)
        values = data.get(data_key, [])
        if isinstance(limit, int) and isinstance(values, list) and len(values) > limit:
            raise LayoutCompileError(
                f"slide {slide_id}: visualization {visualization['visualization_id']!r} "
                f"exceeds {slot['slot_id']}.{limit_key}={limit}"
            )


def _compile_visual_operations(
    slide_id: str,
    slots: Sequence[Mapping[str, Any]],
    visualizations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    available = list(visualizations)
    operations: list[dict[str, Any]] = []
    consumed: set[str] = set()
    for slot in slots:
        match = next(
            (
                item
                for item in available
                if item["visual_type"] == slot["kind"]
                and item["visualization_id"] not in consumed
            ),
            None,
        )
        if match is None:
            if slot.get("required") is True:
                raise LayoutCompileError(
                    f"slide {slide_id}: required {slot['kind']} slot "
                    f"{slot['slot_id']!r} has no visualization"
                )
            continue
        _check_capacity(slide_id, slot, match)
        operation = {
            "op": slot["operation"],
            "slot_id": slot["slot_id"],
            "target": dict(slot["target"]),
            "visualization_id": match["visualization_id"],
        }
        if "title_target" in slot:
            operation["title_target"] = dict(slot["title_target"])
        operations.append(operation)
        consumed.add(str(match["visualization_id"]))
    unused = [
        item["visualization_id"]
        for item in available
        if item["visualization_id"] not in consumed
    ]
    if unused:
        raise LayoutCompileError(
            f"slide {slide_id}: no explicit Template Profile slot for "
            + ", ".join(repr(value) for value in unused)
        )
    return operations


def compile_layout_plan(
    outline: Mapping[str, Any],
    template_profile: Mapping[str, Any],
    manifest: LoadedVisualizationManifest,
    *,
    outline_schema: Mapping[str, Any] | None = None,
    profile_schema: Mapping[str, Any] | None = None,
    plan_schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    outline_schema = outline_schema or _load_json(OUTLINE_SCHEMA, "Outline schema")
    profile_schema = profile_schema or _load_json(
        TEMPLATE_PROFILE_SCHEMA, "Template Profile schema"
    )
    plan_schema = plan_schema or _load_json(
        COMPILED_PLAN_SCHEMA, "Compiled Layout Plan schema"
    )
    outline_errors = _schema_errors(outline, outline_schema)
    if outline_errors:
        raise LayoutCompileError(f"Outline schema validation failed: {outline_errors[0]}")
    profile_errors = validate_template_profile(template_profile, profile_schema)
    if profile_errors:
        raise LayoutCompileError(
            f"Template Profile validation failed: {profile_errors[0]}"
        )

    outline_hash = canonical_sha256(outline)
    manifest_outline_hash = str(manifest.data["outline_sha256"])
    if manifest_outline_hash != "0" * 64 and manifest_outline_hash != outline_hash:
        raise LayoutCompileError("Visualization Manifest was built for a different Outline")
    outline_slide_ids = {
        str(slide.get("slide_id"))
        for slide in outline.get("slides", [])
        if isinstance(slide, Mapping)
    }
    unknown_manifest_slides = set(manifest.bindings_by_slide) - outline_slide_ids
    if unknown_manifest_slides:
        raise LayoutCompileError(
            f"Visualization Manifest references unknown slide_id: "
            f"{sorted(unknown_manifest_slides)[0]}"
        )

    metadata = outline.get("metadata", {})
    compiled_slides: list[dict[str, Any]] = []
    embedded_visualizations: list[dict[str, Any]] = []
    for item in manifest.visualizations_by_id.values():
        embedded_visualizations.append(
            {
                "visualization_id": item["visualization_id"],
                "slide_id": item["slide_id"],
                "visual_type": item["visual_type"],
                "data": dict(item["data"]),
            }
        )
    for page_number, slide in enumerate(outline.get("slides", []), start=1):
        slide_id = str(slide["slide_id"])
        records = list(manifest.bindings_by_slide.get(slide_id, ()))
        resolution = resolve_profile_layout(
            slide,
            visualizations=[item["data"] for item in records],
            template_profile=template_profile,
        )
        layout = template_profile["layouts"][resolution.layout_id]
        operations = [
            _compile_binding(binding, slide, metadata, page_number)
            for binding in layout.get("bindings", [])
        ]
        if layout.get("remove_shapes"):
            operations.append(
                {"op": "remove_shapes", "names": list(layout["remove_shapes"])}
            )
        operations.extend(
            _compile_visual_operations(
                slide_id,
                layout.get("slots", []),
                records,
            )
        )
        compiled_slides.append(
            {
                "slide_id": slide_id,
                "layout_id": resolution.layout_id,
                "template_slide": resolution.template_slide,
                "operations": operations,
            }
        )

    profile_hash = canonical_sha256(template_profile)
    manifest_hash = canonical_sha256(dict(manifest.data))
    plan: dict[str, Any] = {
        "schema_version": "1.0.0",
        "plan_id": "plan_0000000000000000",
        "source": {
            "outline_sha256": outline_hash,
            "manifest_sha256": manifest_hash,
        },
        "template": {
            "profile_id": template_profile["profile_id"],
            "profile_sha256": profile_hash,
            "file": template_profile["template"]["file"],
            "sha256": template_profile["template"]["sha256"],
        },
        "asset_root": str(manifest.asset_root),
        "visualizations": embedded_visualizations,
        "slides": compiled_slides,
    }
    plan["plan_id"] = "plan_" + canonical_sha256(plan)[:16]
    errors = validate_compiled_plan(plan, plan_schema)
    if errors:
        raise LayoutCompileError(f"Compiled Layout Plan is invalid: {errors[0]}")
    return plan


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile Outline, Manifest, and Template Profile into a layout plan"
    )
    parser.add_argument("outline", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("template_profile", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        outline = _load_json(args.outline, "Outline")
        profile = _load_json(args.template_profile, "Template Profile")
        manifest = load_visualization_manifest(args.manifest)
        plan = compile_layout_plan(outline, profile, manifest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (
        LayoutCompileError,
        LayoutResolutionError,
        VisualizationManifestError,
        OSError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Created Compiled Layout Plan: {args.output}")
    print(f"Slides: {len(plan['slides'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
from .abstract_layout import (
    AbstractLayoutError,
    DEFAULT_ABSTRACT_LAYOUT_CATALOG,
    load_abstract_layout_catalog,
    select_abstract_layout,
)


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


def _required_text_sources(slide: Mapping[str, Any]) -> set[str]:
    required = {"slide.title"} if slide.get("title") else set()
    if (
        slide.get("key_message")
        and slide.get("slide_type") != "figure_page"
    ):
        required.add("slide.key_message")
    if slide.get("bullet_points"):
        required.add("slide.bullet_points")
    return required


def _exact_layout_feasible(
    slide: Mapping[str, Any],
    layout: Mapping[str, Any],
    visualizations: Sequence[Mapping[str, Any]],
) -> bool:
    if layout.get("has_unbound_example_content") is True:
        return False
    if slide.get("page_role") == "content":
        sources = {
            str(binding.get("source"))
            for binding in layout.get("bindings", [])
            if isinstance(binding, Mapping)
        }
        if not _required_text_sources(slide).issubset(sources):
            return False
    try:
        _compile_visual_operations(
            str(slide.get("slide_id", "")),
            layout.get("slots", []),
            visualizations,
        )
    except LayoutCompileError:
        return False
    return True


def _select_exact_layout(
    slide: Mapping[str, Any],
    visualizations: Sequence[Mapping[str, Any]],
    template_profile: Mapping[str, Any],
) -> tuple[str, Mapping[str, Any]] | None:
    try:
        resolution = resolve_profile_layout(
            slide,
            visualizations=[item["data"] for item in visualizations],
            template_profile=template_profile,
        )
    except LayoutResolutionError:
        return None
    layout = template_profile.get("layouts", {}).get(resolution.layout_id)
    if not isinstance(layout, Mapping):
        return None
    if not _exact_layout_feasible(slide, layout, visualizations):
        return None
    return resolution.layout_id, layout


def _absolute_target(
    bounds: Mapping[str, Any],
    *,
    width_in: float,
    height_in: float,
) -> dict[str, Any]:
    return {
        "bounds_in": {
            "left": round(float(bounds["left"]) * width_in, 4),
            "top": round(float(bounds["top"]) * height_in, 4),
            "width": round(float(bounds["width"]) * width_in, 4),
            "height": round(float(bounds["height"]) * height_in, 4),
        }
    }


def _check_text_capacity(
    slide_id: str,
    layout_id: str,
    region: Mapping[str, Any],
    values: Sequence[object],
) -> None:
    capacity = region.get("capacity", {})
    if not isinstance(capacity, Mapping):
        return
    texts = [str(value) for value in values if value is not None]
    max_chars = capacity.get("max_chars")
    if isinstance(max_chars, int) and sum(len(value) for value in texts) > max_chars:
        raise LayoutCompileError(
            f"slide {slide_id}: text exceeds "
            f"{layout_id}.{region['region_id']}.max_chars={max_chars}"
        )
    max_chars_per_item = capacity.get("max_chars_per_item")
    if isinstance(max_chars_per_item, int):
        for value in texts:
            if len(value) > max_chars_per_item:
                raise LayoutCompileError(
                    f"slide {slide_id}: text item exceeds "
                    f"{layout_id}.{region['region_id']}"
                    f".max_chars_per_item={max_chars_per_item}"
                )


def _compile_adaptive_slide(
    slide: Mapping[str, Any],
    visualizations: Sequence[Mapping[str, Any]],
    template_profile: Mapping[str, Any],
    abstract_catalog: Mapping[str, Any],
) -> dict[str, Any]:
    adaptive = template_profile.get("adaptive_canvas", {})
    if not isinstance(adaptive, Mapping) or adaptive.get("enabled") is not True:
        raise LayoutCompileError(
            f"slide {slide.get('slide_id')}: no exact template and adaptive_canvas is disabled"
        )
    has_body = bool(
        (
            slide.get("key_message")
            and slide.get("slide_type") != "figure_page"
        )
        or slide.get("bullet_points")
    )
    try:
        layout_id, layout = select_abstract_layout(
            abstract_catalog,
            page_role=str(slide.get("page_role", "content")),
            visualizations=visualizations,
            has_body=has_body,
        )
    except AbstractLayoutError as exc:
        raise LayoutCompileError(f"slide {slide.get('slide_id')}: {exc}") from exc
    template = template_profile["template"]
    width_in = float(template["width_in"])
    height_in = float(template["height_in"])
    styles = adaptive.get("style_tokens", {})
    operations: list[dict[str, Any]] = []
    remaining = list(visualizations)
    emitted_roles: set[str] = set()
    for region in layout.get("regions", []):
        role = str(region["content_role"])
        target = _absolute_target(
            region["bounds"], width_in=width_in, height_in=height_in
        )
        if role == "title":
            value = slide.get("title", "")
            _check_text_capacity(
                str(slide["slide_id"]), layout_id, region, [value]
            )
            operations.append(
                {
                    "op": "add_text_box",
                    "element_id": region["region_id"],
                    "target": target,
                    "value": value,
                    "style": dict(styles[region["style_role"]]),
                }
            )
            emitted_roles.add(role)
        elif (
            role == "key_message"
            and slide.get("key_message")
            and slide.get("slide_type") != "figure_page"
        ):
            _check_text_capacity(
                str(slide["slide_id"]),
                layout_id,
                region,
                [slide["key_message"]],
            )
            operations.append(
                {
                    "op": "add_text_box",
                    "element_id": region["region_id"],
                    "target": target,
                    "value": slide["key_message"],
                    "style": dict(styles[region["style_role"]]),
                }
            )
            emitted_roles.add(role)
        elif role == "bullet_list" and slide.get("bullet_points"):
            capacity = region.get("capacity", {})
            values = list(slide["bullet_points"])
            if len(values) > int(capacity.get("max_items", len(values))):
                raise LayoutCompileError(
                    f"slide {slide.get('slide_id')}: bullet_points exceed "
                    f"{layout_id}.{region['region_id']} capacity"
                )
            _check_text_capacity(
                str(slide["slide_id"]), layout_id, region, values
            )
            style = dict(styles[region["style_role"]])
            minimum_font_size = capacity.get("minimum_font_size_pt")
            if isinstance(minimum_font_size, (int, float)):
                style["font_size_pt"] = min(
                    float(style["font_size_pt"]), float(minimum_font_size)
                )
            operations.append(
                {
                    "op": "add_bullet_list",
                    "element_id": region["region_id"],
                    "target": target,
                    "values": values,
                    "style": style,
                }
            )
            emitted_roles.add(role)
        elif role == "visual":
            match = next(
                (
                    item for item in remaining
                    if item["visual_type"] in region.get("accepts", [])
                ),
                None,
            )
            if match is None:
                if region.get("required") is True:
                    raise LayoutCompileError(
                        f"slide {slide.get('slide_id')}: adaptive visual region "
                        f"{region['region_id']!r} is unbound"
                    )
                continue
            pseudo_slot = {
                "slot_id": region["region_id"],
                "kind": match["visual_type"],
                "capacity": region.get("capacity", {}),
            }
            _check_capacity(str(slide["slide_id"]), pseudo_slot, match)
            visual_operation = {
                    "op": f"render_{match['visual_type']}",
                    "slot_id": region["region_id"],
                    "target": target,
                    "visualization_id": match["visualization_id"],
                }
            if match["visual_type"] == "table":
                visual_operation["style"] = dict(styles.get("table", {}))
            elif match["visual_type"] == "chart":
                visual_operation["style"] = dict(
                    styles.get("primary_visual", {})
                )
            operations.append(visual_operation)
            remaining.remove(match)
    if (
        slide.get("key_message")
        and slide.get("slide_type") != "figure_page"
        and "key_message" not in emitted_roles
    ):
        raise LayoutCompileError(
            f"slide {slide.get('slide_id')}: adaptive layout does not preserve key_message"
        )
    if slide.get("bullet_points") and "bullet_list" not in emitted_roles:
        raise LayoutCompileError(
            f"slide {slide.get('slide_id')}: adaptive layout does not preserve bullet_points"
        )
    if remaining:
        raise LayoutCompileError(
            f"slide {slide.get('slide_id')}: adaptive layout left visualizations unconsumed"
        )
    return {
        "slide_id": str(slide["slide_id"]),
        "slide_mode": "adaptive_canvas",
        "abstract_layout_id": layout_id,
        "base": {
            "mode": "blank",
            "slide_layout_index": int(
                adaptive.get("base", {}).get("slide_layout_index", 0)
            ),
            "clear_placeholders": bool(
                adaptive.get("base", {}).get("clear_placeholders", True)
            ),
            "width_in": width_in,
            "height_in": height_in,
            "background_color": str(
                adaptive.get("base", {}).get("background_color", "FFFFFF")
            ),
        },
        "operations": operations,
    }


def compile_layout_plan(
    outline: Mapping[str, Any],
    template_profile: Mapping[str, Any],
    manifest: LoadedVisualizationManifest,
    *,
    outline_schema: Mapping[str, Any] | None = None,
    profile_schema: Mapping[str, Any] | None = None,
    plan_schema: Mapping[str, Any] | None = None,
    abstract_layout_catalog: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    outline_schema = outline_schema or _load_json(OUTLINE_SCHEMA, "Outline schema")
    profile_schema = profile_schema or _load_json(
        TEMPLATE_PROFILE_SCHEMA, "Template Profile schema"
    )
    plan_schema = plan_schema or _load_json(
        COMPILED_PLAN_SCHEMA, "Compiled Layout Plan schema"
    )
    abstract_layout_catalog = (
        abstract_layout_catalog or load_abstract_layout_catalog()
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
        exact = _select_exact_layout(slide, records, template_profile)
        if exact is None:
            compiled_slides.append(
                _compile_adaptive_slide(
                    slide,
                    records,
                    template_profile,
                    abstract_layout_catalog,
                )
            )
        else:
            layout_id, layout = exact
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
                    "slide_mode": "exact_template",
                    "layout_id": layout_id,
                    "template_slide": int(layout["template_slide"]),
                    "operations": operations,
                }
            )

    profile_hash = canonical_sha256(template_profile)
    manifest_hash = canonical_sha256(dict(manifest.data))
    plan: dict[str, Any] = {
        "schema_version": "2.0.0",
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
    parser.add_argument(
        "--abstract-layouts",
        type=Path,
        default=DEFAULT_ABSTRACT_LAYOUT_CATALOG,
    )
    parser.add_argument("-o", "--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        outline = _load_json(args.outline, "Outline")
        profile = _load_json(args.template_profile, "Template Profile")
        manifest = load_visualization_manifest(args.manifest)
        plan = compile_layout_plan(
            outline,
            profile,
            manifest,
            abstract_layout_catalog=load_abstract_layout_catalog(args.abstract_layouts),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (
        LayoutCompileError,
        LayoutResolutionError,
        AbstractLayoutError,
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

"""Resolve semantic slides to the fixed template layout IDs.

The resolver deliberately consumes the existing Slide Outline and Visualization
contracts.  It never adds layout fields to an outline object.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


class LayoutResolutionError(ValueError):
    """Raised when a slide cannot be mapped to a usable template layout."""


class LayoutMapError(LayoutResolutionError):
    """Raised when the Layout Map is structurally or semantically invalid."""


@dataclass(frozen=True)
class ResolvedLayout:
    slide_id: str
    layout_id: str
    template_slide: int
    reason: str


DEFAULT_SLIDE_TYPE_LAYOUT: dict[str, str] = {
    "company_overview": "company_overview",
    "industry_analysis": "industry_outlook",
    "business_model": "company_overview",
    "core_competitiveness": "capability_map",
    "financial_forecast": "executive_summary",
    "valuation_analysis": "valuation",
    "investment_risk": "risk_catalyst",
    "summary": "executive_summary",
}


def load_layout_map(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LayoutResolutionError(f"layout map not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LayoutResolutionError(f"layout map is invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LayoutResolutionError("layout map root must be an object")
    return value


def _layout_ids(layout_map: Mapping[str, Any]) -> set[str]:
    layouts = layout_map.get("layouts")
    if not isinstance(layouts, Mapping):
        raise LayoutResolutionError("layout map must contain an object 'layouts'")
    return {str(key) for key in layouts}


def _configured_mapping(layout_map: Mapping[str, Any], key: str) -> Mapping[str, str]:
    section = layout_map.get("layout_resolution", {})
    value = section.get(key, {}) if isinstance(section, Mapping) else {}
    if not isinstance(value, Mapping):
        return {}
    return {str(k): str(v) for k, v in value.items()}


class LayoutResolver:
    """Runtime resolver for the fixed template mapping rules."""

    def __init__(self, layout_map: Mapping[str, Any]):
        errors = validate_layout_map(layout_map)
        if errors:
            raise LayoutMapError("; ".join(errors))
        self.layout_map = layout_map
        self.layouts = layout_map["layouts"]
        self.rules = layout_map.get("layout_resolution", {})

    def resolve(
        self,
        slide: Mapping[str, Any],
        visualizations: Sequence[Mapping[str, Any]] = (),
    ) -> str:
        """Return only the layout ID for compatibility with the T2.5 API."""

        role_rules = _configured_mapping(self.layout_map, "page_role_overrides")
        if not role_rules:
            role_rules = _configured_mapping(self.layout_map, "page_role")
        visual_rules = _configured_mapping(self.layout_map, "visualization_overrides")
        if not visual_rules:
            visual_rules = _configured_mapping(self.layout_map, "visualization")
        type_rules = _configured_mapping(self.layout_map, "slide_type_defaults")
        if not type_rules:
            type_rules = _configured_mapping(self.layout_map, "slide_type")

        role = str(slide.get("page_role", "content"))
        visual_kind = None
        if any("columns" in item for item in visualizations):
            visual_kind = "table"
        elif any("chart_type" in item for item in visualizations):
            visual_kind = "chart"

        if role == "title" and "title" in role_rules:
            layout_id = role_rules["title"]
        elif visual_kind and visual_kind in visual_rules:
            layout_id = visual_rules[visual_kind]
        elif role in role_rules and role != "content":
            layout_id = role_rules[role]
        else:
            layout_id = type_rules.get(str(slide.get("slide_type", "summary")))
            if layout_id is None:
                layout_id = self.rules.get("fallback_layout", "executive_summary")
        if layout_id not in self.layouts:
            raise LayoutMapError(f"UNKNOWN_RESOLUTION_TARGET: {layout_id!r}")
        return str(layout_id)


def _visualization_kind(visualizations: Sequence[Mapping[str, Any]]) -> str | None:
    kinds = {"table" if "columns" in item else "chart" for item in visualizations}
    if len(kinds) > 1:
        raise LayoutResolutionError("a slide cannot mix chart and table visualizations in MVP")
    if not kinds:
        return None
    kind = next(iter(kinds))
    if kind == "chart" and len(visualizations) > 1:
        return "chart_pair"
    return kind


def resolve_layout(
    slide: Mapping[str, Any],
    *,
    visualizations: Sequence[Mapping[str, Any]] = (),
    layout_map: Mapping[str, Any],
) -> ResolvedLayout:
    """Resolve one outline slide using page role, visualizations, and slide type."""

    slide_id = slide.get("slide_id")
    if not isinstance(slide_id, str) or not slide_id:
        raise LayoutResolutionError("slide is missing a non-empty slide_id")

    layouts = layout_map.get("layouts")
    layout_ids = _layout_ids(layout_map)
    resolver = LayoutResolver(layout_map)
    layout_id = resolver.resolve(slide, visualizations)
    reason = f"layout_id={layout_id}"

    if layout_id not in layout_ids:
        raise LayoutResolutionError(f"slide {slide_id}: unknown layout_id {layout_id!r}")
    definition = layouts[layout_id]
    template_slide = definition.get("template_slide") if isinstance(definition, Mapping) else None
    if not isinstance(template_slide, int) or template_slide < 1:
        raise LayoutResolutionError(
            f"layout {layout_id!r} must contain a positive integer template_slide"
        )
    return ResolvedLayout(slide_id, layout_id, template_slide, reason)


def resolve_outline(
    outline: Mapping[str, Any],
    *,
    visualizations_by_slide: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    layout_map: Mapping[str, Any],
) -> list[ResolvedLayout]:
    """Resolve all outline slides in input order."""

    slides = outline.get("slides")
    if not isinstance(slides, list):
        raise LayoutResolutionError("outline must contain a slides array")
    visualizations_by_slide = visualizations_by_slide or {}
    return [
        resolve_layout(
            slide,
            visualizations=visualizations_by_slide.get(str(slide.get("slide_id")), ()),
            layout_map=layout_map,
        )
        for slide in slides
        if isinstance(slide, Mapping)
    ]


def validate_layout_map(layout_map: Mapping[str, Any]) -> list[str]:
    """Return structural and semantic Layout Map validation errors."""

    errors: list[str] = []
    layouts = layout_map.get("layouts")
    if not isinstance(layouts, Mapping) or not layouts:
        return ["layout map must contain a non-empty layouts object"]

    presentation = layout_map.get("presentation", {})
    slide_count = presentation.get("slide_count") if isinstance(presentation, Mapping) else None
    for layout_id, definition in layouts.items():
        context = f"layouts.{layout_id}"
        if not isinstance(definition, Mapping):
            errors.append(f"{context} must be an object")
            continue
        template_slide = definition.get("template_slide")
        if not isinstance(template_slide, int) or template_slide < 1:
            errors.append(f"{context}.template_slide must be a positive integer")
        elif isinstance(slide_count, int) and template_slide > slide_count:
            errors.append(f"{context}.template_slide {template_slide} exceeds slide_count {slide_count}")
        fields = definition.get("fields")
        if not isinstance(fields, Mapping):
            errors.append(f"{context}.fields must be an object")
            continue
        for field_name, spec in fields.items():
            if not isinstance(spec, Mapping):
                errors.append(f"{context}.fields.{field_name} must be an object")
                continue
            if spec.get("required", True) is False:
                continue
            field_type = spec.get("type")
            if field_type in {"text", "bullet_list", "source_list", "auto", "composite_text", "table"}:
                target = spec.get("target")
                if not isinstance(target, Mapping):
                    errors.append(f"{context}.fields.{field_name} has no resolved target")
            elif field_type == "chart_slot":
                if not isinstance(spec.get("anchor"), Mapping):
                    errors.append(f"{context}.fields.{field_name} has no resolved chart anchor")
                if not isinstance(spec.get("title_target"), Mapping):
                    errors.append(f"{context}.fields.{field_name} has no resolved chart title target")
            elif field_type == "repeated_group":
                targets = spec.get("targets")
                if not isinstance(targets, list) or not targets:
                    errors.append(f"{context}.fields.{field_name} has no resolved repeated targets")
            elif field_type == "matrix":
                if not isinstance(spec.get("anchor"), Mapping):
                    errors.append(f"{context}.fields.{field_name} has no resolved matrix anchor")

    resolution = layout_map.get("layout_resolution", {})
    if not isinstance(resolution, Mapping):
        errors.append("layout_resolution must be an object")
    else:
        known = set(str(key) for key in layouts)
        for group_name, mappings in resolution.items():
            if group_name == "fallback_layout":
                if mappings not in known:
                    errors.append(f"UNKNOWN_RESOLUTION_TARGET: {mappings!r}")
                continue
            if not isinstance(mappings, Mapping):
                errors.append(f"layout_resolution.{group_name} must be an object")
                continue
            for key, layout_id in mappings.items():
                if layout_id not in known:
                    errors.append(
                        f"UNKNOWN_RESOLUTION_TARGET: layout_resolution.{group_name}.{key}={layout_id!r}"
                    )
    return errors


def main(argv: list[str] | None = None) -> int:
    """CLI entry point kept here for the existing unified main.py dispatch."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Validate template_layout_map.json")
    parser.add_argument("layout_map", type=Path)
    args = parser.parse_args(argv)
    try:
        errors = validate_layout_map(load_layout_map(args.layout_map))
    except LayoutResolutionError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    for error in errors:
        print(f"[ERROR] {error}")
    print(f"{'VALID' if not errors else 'INVALID'}: {len(errors)} error(s)")
    return 0 if not errors else 1

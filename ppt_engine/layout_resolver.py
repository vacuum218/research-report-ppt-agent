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


@dataclass(frozen=True)
class LayoutDecision:
    """Detailed decision used for resolver diagnostics."""

    layout_id: str
    matched_rule: str
    visual_candidate_types: tuple[str, ...]


DEFAULT_SLIDE_TYPE_LAYOUT: dict[str, str] = {
    "company_overview": "company_overview",
    "industry_analysis": "industry_outlook",
    "business_model": "business_structure",
    "core_competitiveness": "competitive_landscape",
    "financial_forecast": "earnings_forecast",
    "valuation_analysis": "valuation",
    "investment_risk": "risk_catalyst",
    "figure_page": "image_only_layout",
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

        return self.resolve_decision(slide, visualizations).layout_id

    def resolve_decision(
        self,
        slide: Mapping[str, Any],
        visualizations: Sequence[Mapping[str, Any]] = (),
    ) -> LayoutDecision:
        """Resolve a layout and retain the exact rule that matched."""

        role_rules = _configured_mapping(self.layout_map, "page_role_overrides")
        if not role_rules:
            role_rules = _configured_mapping(self.layout_map, "page_role")
        type_rules = _configured_mapping(self.layout_map, "slide_type_defaults")
        if not type_rules:
            type_rules = _configured_mapping(self.layout_map, "slide_type")

        role = str(slide.get("page_role", "content"))
        slide_type = str(slide.get("slide_type", "summary"))
        visual_types = _collect_visual_types(slide, visualizations)
        layout_hint = str(slide.get("layout_hint", "")).casefold()

        # Page-role special pages are structurally fixed and therefore have the
        # highest priority over content semantics.
        if role in role_rules and role != "content":
            layout_id = role_rules[role]
            matched_rule = f"page_role_overrides.{role}"
        else:
            layout_id = None
            matched_rule = ""
            rules = self.rules.get("semantic_visual_rules", [])
            if isinstance(rules, list):
                for rule in rules:
                    if not isinstance(rule, Mapping):
                        continue
                    if str(rule.get("slide_type")) != slide_type:
                        continue
                    if str(rule.get("visual_type")) not in visual_types:
                        continue
                    hint_tokens = rule.get("layout_hint_any", [])
                    if isinstance(hint_tokens, list) and hint_tokens:
                        if not any(str(token).casefold() in layout_hint for token in hint_tokens):
                            continue
                    layout_id = str(rule.get("layout_id"))
                    matched_rule = f"semantic_visual_rules.{rule.get('rule_id')}"
                    break

            if layout_id is None:
                layout_id = type_rules.get(slide_type)
                if layout_id is not None:
                    matched_rule = f"slide_type_defaults.{slide_type}"
            if layout_id is None:
                layout_id = self.rules.get("fallback_layout", "executive_summary")
                matched_rule = "fallback_layout"
        if layout_id not in self.layouts:
            raise LayoutMapError(f"UNKNOWN_RESOLUTION_TARGET: {layout_id!r}")
        return LayoutDecision(str(layout_id), matched_rule, visual_types)


def _collect_visual_types(
    slide: Mapping[str, Any],
    visualizations: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """Merge Outline visual intent with any bound Visualization JSON objects."""

    values: list[str] = []
    candidates = slide.get("visual_candidates", [])
    if isinstance(candidates, list):
        for candidate in candidates:
            if isinstance(candidate, Mapping) and candidate.get("type") in {"chart", "table", "image"}:
                values.append(str(candidate["type"]))
    for visualization in visualizations:
        if visualization.get("type") == "image":
            values.append("image")
        elif "columns" in visualization:
            values.append("table")
        elif "chart_type" in visualization:
            values.append("chart")
    return tuple(dict.fromkeys(values))


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
    decision = resolver.resolve_decision(slide, visualizations)
    layout_id = decision.layout_id
    reason = decision.matched_rule

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
    debug: bool = True,
) -> list[ResolvedLayout]:
    """Resolve all outline slides in input order."""

    slides = outline.get("slides")
    if not isinstance(slides, list):
        raise LayoutResolutionError("outline must contain a slides array")
    visualizations_by_slide = visualizations_by_slide or {}
    resolver = LayoutResolver(layout_map)
    layouts = layout_map["layouts"]
    results: list[ResolvedLayout] = []
    for slide in slides:
        if not isinstance(slide, Mapping):
            continue
        slide_id = str(slide.get("slide_id", ""))
        decision = resolver.resolve_decision(
            slide,
            visualizations_by_slide.get(slide_id, ()),
        )
        definition = layouts[decision.layout_id]
        template_slide = definition.get("template_slide")
        result = ResolvedLayout(
            slide_id=slide_id,
            layout_id=decision.layout_id,
            template_slide=template_slide,
            reason=decision.matched_rule,
        )
        results.append(result)
        if debug:
            visual_text = ",".join(decision.visual_candidate_types) or "none"
            print(
                "[layout-resolver] "
                f"slide_id={slide_id} "
                f"slide_type={slide.get('slide_type')} "
                f"visual_candidates={visual_text} "
                f"matched_rule={decision.matched_rule} "
                f"final_layout_id={decision.layout_id}"
            )
    return results


def resolve_profile_layout(
    slide: Mapping[str, Any],
    *,
    visualizations: Sequence[Mapping[str, Any]] = (),
    template_profile: Mapping[str, Any],
) -> ResolvedLayout:
    """Resolve one slide against a Template Profile without changing legacy APIs.

    Template Profile deliberately has no fallback.  The legacy resolver is
    reused only for its frozen rule precedence; a fallback result is rejected.
    """

    profile_layouts = template_profile.get("layouts")
    template = template_profile.get("template", {})
    if not isinstance(profile_layouts, Mapping):
        raise LayoutResolutionError("Template Profile must contain layouts")
    adapter = {
        "presentation": {
            "slide_count": template.get("slide_count")
            if isinstance(template, Mapping)
            else None
        },
        "layout_resolution": dict(template_profile.get("layout_resolution", {})),
        "layouts": {
            str(layout_id): {
                "template_slide": layout.get("template_slide"),
                "fields": {},
            }
            for layout_id, layout in profile_layouts.items()
            if isinstance(layout, Mapping)
        },
    }
    resolver = LayoutResolver(adapter)
    decision = resolver.resolve_decision(slide, visualizations)
    if decision.matched_rule == "fallback_layout":
        raise LayoutResolutionError(
            f"slide {slide.get('slide_id')!r} has no Template Profile layout rule"
        )
    layout = profile_layouts[decision.layout_id]
    return ResolvedLayout(
        slide_id=str(slide.get("slide_id", "")),
        layout_id=decision.layout_id,
        template_slide=int(layout["template_slide"]),
        reason=decision.matched_rule,
    )


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
            elif field_type == "image_slot":
                bounds = spec.get("bounds_in")
                if (
                    not isinstance(bounds, Mapping)
                    or not all(
                        isinstance(bounds.get(key), (int, float))
                        and float(bounds[key]) > 0
                        for key in ("left", "top", "width", "height")
                    )
                ):
                    errors.append(
                        f"{context}.fields.{field_name} has no positive bounds_in image slot"
                    )
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
        seen_rule_ids: set[str] = set()
        for group_name, mappings in resolution.items():
            if group_name == "fallback_layout":
                if mappings not in known:
                    errors.append(f"UNKNOWN_RESOLUTION_TARGET: {mappings!r}")
                continue
            if group_name == "semantic_visual_rules":
                if not isinstance(mappings, list):
                    errors.append("layout_resolution.semantic_visual_rules must be an array")
                    continue
                for index, rule in enumerate(mappings):
                    context = f"layout_resolution.semantic_visual_rules[{index}]"
                    if not isinstance(rule, Mapping):
                        errors.append(f"{context} must be an object")
                        continue
                    rule_id = rule.get("rule_id")
                    if not isinstance(rule_id, str) or not rule_id:
                        errors.append(f"{context}.rule_id must be a non-empty string")
                    elif rule_id in seen_rule_ids:
                        errors.append(f"{context}.rule_id is duplicated: {rule_id!r}")
                    else:
                        seen_rule_ids.add(rule_id)
                    if not isinstance(rule.get("slide_type"), str):
                        errors.append(f"{context}.slide_type must be a string")
                    if rule.get("visual_type") not in {"chart", "table", "image"}:
                        errors.append(f"{context}.visual_type must be chart, table, or image")
                    hint_tokens = rule.get("layout_hint_any", [])
                    if not isinstance(hint_tokens, list) or not all(
                        isinstance(token, str) and token for token in hint_tokens
                    ):
                        errors.append(f"{context}.layout_hint_any must be an array of strings")
                    layout_id = rule.get("layout_id")
                    if layout_id not in known:
                        errors.append(f"UNKNOWN_RESOLUTION_TARGET: {context}.layout_id={layout_id!r}")
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

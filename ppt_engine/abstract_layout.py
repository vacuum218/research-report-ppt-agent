"""Validation and deterministic selection for template-independent layouts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ABSTRACT_LAYOUT_SCHEMA = PROJECT_ROOT / "schemas/abstract_layout.schema.json"
DEFAULT_ABSTRACT_LAYOUT_CATALOG = PROJECT_ROOT / "layouts/abstract_layout_catalog.json"


class AbstractLayoutError(ValueError):
    """Raised when an abstract layout catalog cannot satisfy a page."""


def load_abstract_layout_catalog(
    path: Path = DEFAULT_ABSTRACT_LAYOUT_CATALOG,
    *,
    schema_path: Path = DEFAULT_ABSTRACT_LAYOUT_SCHEMA,
) -> dict[str, Any]:
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AbstractLayoutError(f"cannot load Abstract Layout Catalog: {exc}") from exc
    errors = sorted(
        Draft202012Validator(schema).iter_errors(catalog),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise AbstractLayoutError(f"Abstract Layout schema validation failed: {errors[0].message}")
    semantic_errors = validate_abstract_layout_catalog(catalog)
    if semantic_errors:
        raise AbstractLayoutError(semantic_errors[0])
    return catalog


def validate_abstract_layout_catalog(catalog: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for layout_id, layout in dict(catalog.get("layouts", {})).items():
        region_ids: set[str] = set()
        regions: list[tuple[str, Mapping[str, Any]]] = []
        for region in layout.get("regions", []):
            region_id = str(region.get("region_id", ""))
            if region_id in region_ids:
                errors.append(f"abstract layout {layout_id!r} has duplicate region_id {region_id!r}")
            region_ids.add(region_id)
            bounds = region.get("bounds", {})
            if float(bounds.get("left", 0)) + float(bounds.get("width", 0)) > 1:
                errors.append(f"abstract layout {layout_id!r} region {region_id!r} exceeds width")
            if float(bounds.get("top", 0)) + float(bounds.get("height", 0)) > 1:
                errors.append(f"abstract layout {layout_id!r} region {region_id!r} exceeds height")
            if isinstance(bounds, Mapping):
                regions.append((region_id, bounds))
        for index, (left_id, left) in enumerate(regions):
            for right_id, right in regions[index + 1:]:
                horizontal_overlap = min(
                    float(left["left"]) + float(left["width"]),
                    float(right["left"]) + float(right["width"]),
                ) - max(float(left["left"]), float(right["left"]))
                vertical_overlap = min(
                    float(left["top"]) + float(left["height"]),
                    float(right["top"]) + float(right["height"]),
                ) - max(float(left["top"]), float(right["top"]))
                if horizontal_overlap > 1e-6 and vertical_overlap > 1e-6:
                    errors.append(
                        f"abstract layout {layout_id!r} regions "
                        f"{left_id!r} and {right_id!r} overlap"
                    )
    return errors


def select_abstract_layout(
    catalog: Mapping[str, Any],
    *,
    page_role: str,
    visualizations: Sequence[Mapping[str, Any]],
    has_body: bool,
) -> tuple[str, Mapping[str, Any]]:
    """Select the least-waste compatible structural layout deterministically."""

    visual_kinds = [str(item["visual_type"]) for item in visualizations]
    candidates: list[tuple[int, str, Mapping[str, Any]]] = []
    for layout_id, layout in dict(catalog.get("layouts", {})).items():
        if page_role not in layout.get("eligible_page_roles", []):
            continue
        capabilities = layout.get("capabilities", {})
        if not int(capabilities.get("min_visuals", 0)) <= len(visual_kinds) <= int(
            capabilities.get("max_visuals", 0)
        ):
            continue
        accepted = set(capabilities.get("accepted_visual_kinds", []))
        if any(kind not in accepted for kind in visual_kinds):
            continue
        if has_body and not capabilities.get("body_supported", False):
            continue
        visual_regions = [
            region for region in layout.get("regions", [])
            if region.get("content_role") == "visual"
        ]
        remaining = list(visual_kinds)
        for region in visual_regions:
            match = next((kind for kind in remaining if kind in region.get("accepts", [])), None)
            if match is not None:
                remaining.remove(match)
        if remaining:
            continue
        waste = int(capabilities.get("max_visuals", 0)) - len(visual_kinds)
        candidates.append((waste, str(layout_id), layout))
    if not candidates:
        raise AbstractLayoutError(
            f"no Abstract Layout covers page_role={page_role!r}, "
            f"visuals={visual_kinds!r}, has_body={has_body}"
        )
    _, layout_id, layout = sorted(candidates, key=lambda item: (item[0], item[1]))[0]
    return layout_id, layout

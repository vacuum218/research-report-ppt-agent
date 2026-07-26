"""Lightweight visual-budget and Abstract Layout preflight."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from .abstract_layout import AbstractLayoutError, select_abstract_layout


def _has_body(slide: Mapping[str, Any]) -> bool:
    return bool(
        (
            slide.get("key_message")
            and slide.get("slide_type") != "figure_page"
        )
        or slide.get("bullet_points")
    )


def _budget(slide: Mapping[str, Any]) -> tuple[int, int]:
    page_role = str(slide.get("page_role") or "content")
    if page_role in {"title", "section", "closing"}:
        return 0, 0
    if slide.get("slide_type") == "figure_page":
        return 1, 1
    return 1, 2


def preflight_layouts(
    outline: Mapping[str, Any],
    plans: Sequence[object],
    abstract_catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """Check per-page visual budgets and structural layout compatibility."""

    by_slide: dict[str, list[dict[str, str]]] = defaultdict(list)
    for plan in plans:
        slide_id = str(getattr(plan, "slide_id"))
        by_slide[slide_id].append(
            {
                "visualization_id": str(getattr(plan, "visualization_id")),
                "visual_type": str(getattr(plan, "visual_type")),
            }
        )

    pages: list[dict[str, Any]] = []
    error_count = 0
    warning_count = 0
    for slide in outline.get("slides", []):
        if not isinstance(slide, Mapping):
            continue
        slide_id = str(slide.get("slide_id") or "")
        page_role = str(slide.get("page_role") or "content")
        visuals = by_slide.get(slide_id, [])
        recommended, maximum = _budget(slide)
        issues: list[dict[str, str]] = []
        selected_layout: str | None = None

        if len(visuals) > maximum:
            issues.append(
                {
                    "severity": "error",
                    "code": "visual_budget_exceeded",
                    "message": f"{len(visuals)} visuals exceed page maximum {maximum}",
                }
            )
        elif len(visuals) > recommended:
            issues.append(
                {
                    "severity": "warning",
                    "code": "visual_budget_above_recommended",
                    "message": f"{len(visuals)} visuals exceed recommended count {recommended}",
                }
            )

        if page_role == "content" and len(visuals) <= maximum:
            try:
                selected_layout, _ = select_abstract_layout(
                    abstract_catalog,
                    page_role=page_role,
                    visualizations=visuals,
                    has_body=_has_body(slide),
                )
            except AbstractLayoutError as exc:
                issues.append(
                    {
                        "severity": "error",
                        "code": "no_compatible_abstract_layout",
                        "message": str(exc),
                    }
                )

        error_count += sum(item["severity"] == "error" for item in issues)
        warning_count += sum(item["severity"] == "warning" for item in issues)
        pages.append(
            {
                "slide_id": slide_id,
                "page_role": page_role,
                "slide_type": str(slide.get("slide_type") or ""),
                "visual_count": len(visuals),
                "recommended_visual_count": recommended,
                "maximum_visual_count": maximum,
                "selected_abstract_layout": selected_layout,
                "issues": issues,
            }
        )

    return {
        "schema_version": "1.0.0",
        "status": "failed" if error_count else "passed",
        "error_count": error_count,
        "warning_count": warning_count,
        "pages": pages,
    }

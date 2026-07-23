"""Semantic visualization planning over Slide Outline evidence.

This layer decides what a visual should communicate.  It never extracts or
emits chart values, table cells, or asset paths.  LLM-produced Outline
``visual_candidates`` are treated as suggestions and every native evidence
reference is checked against Document Intelligence before generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from document_intelligence.models import DocumentIntelligenceSnapshot


class VisualizationPlanningError(ValueError):
    """Raised when a semantic plan references nonexistent bundle evidence."""


@dataclass(frozen=True, slots=True)
class VisualizationPlan:
    slide_id: str
    visualization_id: str
    visual_type: str
    purpose: str
    chart_intent: str | None
    data_requirement: Mapping[str, str]
    evidence_refs: tuple[tuple[str, str], ...]
    source_refs: tuple[str, ...]


def _refs(values: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return ()
    result: list[tuple[str, str]] = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        kind = str(value.get("kind") or "")
        identity = str(value.get("id") or "")
        if kind and identity:
            result.append((kind, identity))
    return tuple(dict.fromkeys(result))


def _source_refs(slide: Mapping[str, Any], candidate: Mapping[str, Any]) -> tuple[str, ...]:
    values = candidate.get("source_refs") or slide.get("source_refs") or []
    return tuple(dict.fromkeys(str(value) for value in values if isinstance(value, str)))


def _intent(candidate: Mapping[str, Any]) -> str | None:
    value = str(candidate.get("chart_intent") or "").strip().lower()
    return value if value in {"trend", "comparison", "composition", "relationship"} else None


def _require_valid_evidence(
    snapshot: DocumentIntelligenceSnapshot,
    refs: Sequence[tuple[str, str]],
) -> None:
    for kind, identity in refs:
        if kind not in {"block", "table", "figure"}:
            raise VisualizationPlanningError(f"Unsupported evidence kind: {kind}")
        if snapshot.evidence(kind, identity) is None:
            raise VisualizationPlanningError(
                f"Visualization plan references unknown {kind}: {identity}"
            )


def plan_visualizations(
    outline: Mapping[str, Any],
    snapshot: DocumentIntelligenceSnapshot,
) -> list[VisualizationPlan]:
    """Convert semantic Outline suggestions into validated, data-free plans."""

    plans: list[VisualizationPlan] = []
    auto_index = 1
    for slide in outline.get("slides", []):
        if not isinstance(slide, Mapping):
            continue
        slide_id = str(slide.get("slide_id") or "")
        slide_refs = _refs(slide.get("evidence_refs"))
        _require_valid_evidence(snapshot, slide_refs)
        candidates = [
            value
            for value in slide.get("visual_candidates", [])
            if isinstance(value, Mapping)
        ]
        for candidate in candidates:
            forbidden = {"values", "categories", "series", "columns", "rows", "asset_path"} & set(candidate)
            if forbidden:
                raise VisualizationPlanningError(
                    "Visualization planning suggestion contains deterministic data fields: "
                    + ", ".join(sorted(forbidden))
                )
            visual_type = str(candidate.get("type") or "")
            if visual_type not in {"chart", "table"}:
                raise VisualizationPlanningError(
                    f"Unsupported visual candidate type: {visual_type or '<empty>'}"
                )
            candidate_refs = _refs(candidate.get("evidence_refs")) or slide_refs
            _require_valid_evidence(snapshot, candidate_refs)
            purpose = str(candidate.get("purpose") or candidate.get("description") or slide.get("key_message") or slide.get("title") or "").strip()
            requirement = candidate.get("data_requirement")
            requirement_items = requirement.items() if isinstance(requirement, Mapping) else ()
            plans.append(
                VisualizationPlan(
                    slide_id=slide_id,
                    visualization_id=str(candidate.get("candidate_id") or f"visual_auto_{auto_index:03d}"),
                    visual_type=visual_type,
                    purpose=purpose,
                    chart_intent=_intent(candidate),
                    data_requirement={
                        str(key): str(value)
                        for key, value in requirement_items
                        if isinstance(key, str)
                    },
                    evidence_refs=candidate_refs,
                    source_refs=_source_refs(slide, candidate),
                )
            )
            auto_index += 1

        # Original PDF figures are intentionally restricted to dedicated,
        # one-figure-per-slide pages in this phase.
        if slide.get("slide_type") == "figure_page":
            figure_refs = tuple(ref for ref in slide_refs if ref[0] == "figure")
            if candidates or len(figure_refs) != 1 or len(slide_refs) != 1:
                raise VisualizationPlanningError(
                    "figure_page requires exactly one figure evidence ref and no visual candidates"
                )
            plans.append(
                VisualizationPlan(
                    slide_id=slide_id,
                    visualization_id=f"visual_auto_{auto_index:03d}",
                    visual_type="image",
                    purpose=str(slide.get("key_message") or slide.get("title") or "原始研报图片"),
                    chart_intent=None,
                    data_requirement={},
                    evidence_refs=figure_refs,
                    source_refs=tuple(
                        str(value)
                        for value in slide.get("source_refs", [])
                        if isinstance(value, str)
                    ),
                )
            )
            auto_index += 1
    return plans

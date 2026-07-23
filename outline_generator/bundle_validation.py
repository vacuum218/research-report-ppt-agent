"""Validate generated Outline references against the source DocumentBundle."""

from __future__ import annotations

from typing import Any, Mapping

from document_intelligence.figures import build_figure_inventory
from document_intelligence.models import DocumentIntelligenceSnapshot
from tools.validate_outline import Issue


def _descendant_or_same(
    snapshot: DocumentIntelligenceSnapshot,
    candidate: str | None,
    ancestor: str,
) -> bool:
    return candidate == ancestor or (
        candidate is not None and ancestor in snapshot.section_paths.get(candidate, ())
    )


def validate_outline_evidence(
    outline: Mapping[str, Any],
    snapshot: DocumentIntelligenceSnapshot,
    allowed_evidence: set[tuple[str, str]] | None = None,
) -> list[Issue]:
    issues: list[Issue] = []
    section_positions = {value: index for index, value in enumerate(snapshot.section_order)}
    figure_inventory = build_figure_inventory(snapshot)
    figure_positions = {
        str(item["figure_id"]): int(item["order"]) for item in figure_inventory
    }
    selectable_figures = {
        str(item["figure_id"])
        for item in figure_inventory
        if item.get("selectable") is True
    }
    previous_figure_position = 0
    previous_position = -1
    for slide_index, slide in enumerate(outline.get("slides", [])):
        if not isinstance(slide, Mapping):
            continue
        base = f"$.slides[{slide_index}]"
        section_ref = slide.get("section_ref")
        if section_ref is not None:
            section_ref = str(section_ref)
            if section_ref not in snapshot.sections_by_id:
                issues.append(Issue("error", "BUNDLE.UNKNOWN_SECTION", f"{base}.section_ref", f"unknown section_ref {section_ref!r}"))
            else:
                position = section_positions[section_ref]
                if position < previous_position:
                    issues.append(Issue("error", "BUNDLE.SECTION_ORDER", f"{base}.section_ref", "slide section order differs from DocumentBundle"))
                previous_position = max(previous_position, position)
                section = snapshot.sections_by_id[section_ref]
                title_block = snapshot.blocks_by_id.get(str(section.get("title_block_id") or ""), {})
                canonical_title = str(title_block.get("text_raw") or "").strip()
                declared_section = str(slide.get("section") or "").strip()
                if declared_section and canonical_title and declared_section != canonical_title:
                    issues.append(Issue("error", "BUNDLE.SECTION_TITLE_MISMATCH", f"{base}.section", "slide section label must match the DocumentBundle heading"))
                if slide.get("page_role") == "section" and canonical_title and str(slide.get("title") or "").strip() != canonical_title:
                    issues.append(Issue("error", "BUNDLE.SECTION_SLIDE_TITLE", f"{base}.title", "section slide title must match the DocumentBundle heading"))

        role = slide.get("page_role")
        refs = slide.get("evidence_refs", [])
        slide_type = slide.get("slide_type")
        figure_refs = [
            str(ref.get("id") or "")
            for ref in refs
            if isinstance(ref, Mapping) and ref.get("kind") == "figure"
        ] if isinstance(refs, list) else []
        if slide_type == "figure_page":
            if len(refs) != 1 or len(figure_refs) != 1:
                issues.append(
                    Issue(
                        "error",
                        "FIGURE.PAGE_REQUIRES_ONE_FIGURE",
                        f"{base}.evidence_refs",
                        "figure_page must reference exactly one figure and no other evidence",
                    )
                )
            elif figure_refs[0] not in selectable_figures:
                issues.append(
                    Issue(
                        "error",
                        "FIGURE.ASSET_UNAVAILABLE",
                        f"{base}.evidence_refs[0]",
                        f"figure {figure_refs[0]!r} has no available original asset",
                    )
                )
            else:
                current_figure_position = figure_positions[figure_refs[0]]
                if current_figure_position <= previous_figure_position:
                    issues.append(
                        Issue(
                            "error",
                            "FIGURE.ORDER",
                            f"{base}.evidence_refs[0]",
                            "figure_page order must be strictly increasing in PDF order",
                        )
                    )
                previous_figure_position = max(
                    previous_figure_position, current_figure_position
                )
        elif figure_refs:
            issues.append(
                Issue(
                    "error",
                    "FIGURE.REQUIRES_FIGURE_PAGE",
                    f"{base}.evidence_refs",
                    "figure evidence must be migrated on a dedicated figure_page",
                )
            )
        if role == "content" and not refs:
            issues.append(Issue("error", "BUNDLE.CONTENT_WITHOUT_EVIDENCE", f"{base}.evidence_refs", "content slide must reference DocumentBundle evidence"))
        if role in {"content", "section"} and section_ref is None:
            issues.append(Issue("error", "BUNDLE.SLIDE_WITHOUT_SECTION", f"{base}.section_ref", f"{role} slide must reference an existing section"))
        if role == "content" and not slide.get("source_refs"):
            issues.append(Issue("error", "BUNDLE.CONTENT_WITHOUT_SOURCE", f"{base}.source_refs", "content slide must preserve source_refs"))
        if not isinstance(refs, list):
            continue
        for ref_index, ref in enumerate(refs):
            path = f"{base}.evidence_refs[{ref_index}]"
            if not isinstance(ref, Mapping):
                continue
            kind = str(ref.get("kind") or "")
            identity = str(ref.get("id") or "")
            evidence = snapshot.evidence(kind, identity)
            if evidence is None:
                issues.append(Issue("error", "BUNDLE.UNKNOWN_EVIDENCE", path, f"unknown {kind} evidence {identity!r}"))
            elif allowed_evidence is not None and (kind, identity) not in allowed_evidence:
                issues.append(Issue("error", "BUNDLE.EVIDENCE_NOT_IN_MEMORY", path, f"evidence {identity!r} was not preserved by Context Compression"))
            elif section_ref in snapshot.sections_by_id and not _descendant_or_same(snapshot, evidence.section_id, str(section_ref)):
                issues.append(Issue("error", "BUNDLE.CROSS_SECTION_EVIDENCE", path, f"evidence {identity!r} is outside section {section_ref!r}"))
    return issues

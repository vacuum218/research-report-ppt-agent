"""Validate generated Outline references against the source DocumentBundle."""

from __future__ import annotations

import re
from typing import Any, Mapping

from document_intelligence.figures import build_figure_inventory
from document_intelligence.models import DocumentIntelligenceSnapshot
from tools.validate_outline import Issue


_CITATION_RE = re.compile(r"\[\^[^\]]+\]")
_SPACE_RE = re.compile(r"\s+")
_FIRST_SENTENCE_RE = re.compile(r"^(.+?[。！？：])")
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:\d{1,4}(?:[.,]\d+)*)(?:%|倍|X|x|亿元|万元|百万元|TOPS|POPS)?"
)


def _normalized_text(value: object) -> str:
    return _SPACE_RE.sub("", _CITATION_RE.sub("", str(value or ""))).strip()


def _first_topic_sentence(value: object) -> str | None:
    text = _normalized_text(value)
    if not text:
        return None
    match = _FIRST_SENTENCE_RE.match(text)
    sentence = match.group(1) if match else text
    # A long analytical paragraph often starts directly with supporting detail.
    # Enforce verbatim preservation only for a concise, presentation-ready lead.
    return sentence if 6 <= len(sentence) <= 120 else None


def _grounded_number_issues(
    slide: Mapping[str, Any],
    *,
    evidence_text: str,
    base: str,
) -> list[Issue]:
    def number_key(value: str) -> str:
        match = re.search(r"\d{1,4}(?:[.,]\d+)*", value)
        return match.group(0).replace(",", "") if match else ""

    available = {number_key(value) for value in _NUMBER_RE.findall(evidence_text)}
    normalized_evidence = _normalized_text(evidence_text)
    for start, end in re.findall(r"((?:19|20)\d{2})[-—至]((?:19|20)\d{2})", normalized_evidence):
        if int(start) <= int(end) <= int(start) + 20:
            available.update(str(year) for year in range(int(start), int(end) + 1))
    issues: list[Issue] = []
    fields: list[tuple[str, object]] = [
        ("title", slide.get("title")),
        ("key_message", slide.get("key_message")),
        *[
            (f"bullet_points[{index}]", value)
            for index, value in enumerate(slide.get("bullet_points", []))
        ],
    ]
    for field, value in fields:
        for token in _NUMBER_RE.findall(str(value or "")):
            normalized = number_key(token)
            if normalized and normalized not in available:
                issues.append(
                    Issue(
                        "error",
                        "BUNDLE.UNGROUNDED_NUMBER",
                        f"{base}.{field}",
                        f"numeric claim {token!r} is absent from the cited evidence",
                    )
                )
    return issues


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
                if (
                    slide.get("page_role") in {"section", "content"}
                    and slide.get("slide_type") != "figure_page"
                    and canonical_title
                    and slide.get("title") is not None
                    and str(slide.get("title") or "").strip() != canonical_title
                ):
                    issues.append(
                        Issue(
                            "error",
                            "BUNDLE.SECTION_SLIDE_TITLE",
                            f"{base}.title",
                            "section/content slide title must exactly match the DocumentBundle heading",
                        )
                    )

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
                figure = snapshot.figures_by_id[figure_refs[0]]
                caption_block = snapshot.blocks_by_id.get(
                    str(figure.get("caption_block_id") or ""), {}
                )
                canonical_caption = str(
                    caption_block.get("text_raw") or ""
                ).strip()
                if (
                    canonical_caption
                    and str(slide.get("title") or "").strip()
                    != canonical_caption
                ):
                    issues.append(
                        Issue(
                            "error",
                            "FIGURE.TITLE_MISMATCH",
                            f"{base}.title",
                            "figure page title must exactly match its source caption",
                        )
                    )
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
        evidence_blocks: list[Mapping[str, Any]] = []
        evidence_text_parts: list[str] = []
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
            if evidence is not None:
                if kind == "block" and identity in snapshot.blocks_by_id:
                    block = snapshot.blocks_by_id[identity]
                    evidence_blocks.append(block)
                    evidence_text_parts.append(str(block.get("text_raw") or ""))
                elif kind == "table" and identity in snapshot.tables_by_id:
                    table = snapshot.tables_by_id[identity]
                    evidence_text_parts.append(str(table.get("structure_raw") or ""))

        for candidate_index, candidate in enumerate(
            slide.get("visual_candidates", [])
        ):
            if not isinstance(candidate, Mapping):
                continue
            candidate_refs = candidate.get("evidence_refs", [])
            if not isinstance(candidate_refs, list):
                continue
            if not candidate_refs:
                issues.append(
                    Issue(
                        "error",
                        "BUNDLE.VISUAL_WITHOUT_NATIVE_EVIDENCE",
                        f"{base}.visual_candidates[{candidate_index}].evidence_refs",
                        "visual candidate must cite native block/table evidence",
                    )
                )
                continue
            for ref_index, ref in enumerate(candidate_refs):
                if not isinstance(ref, Mapping):
                    continue
                path = (
                    f"{base}.visual_candidates[{candidate_index}]"
                    f".evidence_refs[{ref_index}]"
                )
                kind = str(ref.get("kind") or "")
                identity = str(ref.get("id") or "")
                evidence = snapshot.evidence(kind, identity)
                if evidence is None:
                    issues.append(
                        Issue(
                            "error",
                            "BUNDLE.UNKNOWN_VISUAL_EVIDENCE",
                            path,
                            f"unknown {kind} evidence {identity!r}",
                        )
                    )
                elif (
                    section_ref in snapshot.sections_by_id
                    and not _descendant_or_same(
                        snapshot, evidence.section_id, str(section_ref)
                    )
                ):
                    issues.append(
                        Issue(
                            "error",
                            "BUNDLE.CROSS_SECTION_VISUAL_EVIDENCE",
                            path,
                            f"visual evidence {identity!r} is outside section {section_ref!r}",
                        )
                    )

        if role == "content" and slide_type != "figure_page":
            first_paragraph = next(
                (
                    block
                    for block in evidence_blocks
                    if str(block.get("type")) in {"paragraph", "blockquote"}
                ),
                None,
            )
            topic_sentence = (
                _first_topic_sentence(first_paragraph.get("text_raw"))
                if first_paragraph is not None
                else None
            )
            key_message = _normalized_text(slide.get("key_message"))
            if (
                topic_sentence
                and slide.get("key_message") is not None
                and key_message != topic_sentence
            ):
                issues.append(
                    Issue(
                        "error",
                        "BUNDLE.TOPIC_SENTENCE_MISMATCH",
                        f"{base}.key_message",
                        "a concise first-sentence topic statement must be preserved verbatim",
                    )
                )
            evidence_text = " ".join(evidence_text_parts)
            if section_ref in snapshot.sections_by_id:
                section = snapshot.sections_by_id[str(section_ref)]
                title_block = snapshot.blocks_by_id.get(
                    str(section.get("title_block_id") or ""), {}
                )
                evidence_text += " " + str(title_block.get("text_raw") or "")
            issues.extend(
                _grounded_number_issues(
                    slide,
                    evidence_text=evidence_text,
                    base=base,
                )
            )
    return issues

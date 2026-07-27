"""Phase 2 contracts separating report understanding from deck editing."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from document_intelligence.figures import build_figure_inventory
from document_intelligence.models import DocumentIntelligenceSnapshot
from tools.validate_outline import Issue


_SPACE_RE = re.compile(r"\s+")


def source_id_for(snapshot: DocumentIntelligenceSnapshot) -> str:
    document_id = str(snapshot.metadata.get("id") or "document")
    safe = "".join(
        character if character.isalnum() or character in "_.-" else "_"
        for character in document_id
    ).strip("_.-")
    return "src_" + (safe or "document")


def section_catalog(snapshot: DocumentIntelligenceSnapshot) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for ordinal, section_id in enumerate(snapshot.section_order):
        section = snapshot.sections_by_id[section_id]
        title_block_id = str(section.get("title_block_id") or "")
        title = str(
            snapshot.blocks_by_id.get(title_block_id, {}).get("text_raw") or ""
        ).strip()
        result.append(
            {
                "ordinal": ordinal,
                "section_ref": section_id,
                "section_title": title,
                "parent_id": section.get("parent_id"),
                "level": section.get("level"),
            }
        )
    return result


def build_report_map_messages(
    snapshot: DocumentIntelligenceSnapshot,
    runtime_memories: Sequence[Mapping[str, Any]],
    schema: Mapping[str, Any],
    system_prompt: str,
) -> list[dict[str, str]]:
    payload = {
        "task": "build_evidence_grounded_report_map",
        "document": dict(snapshot.metadata),
        "required_source_id": source_id_for(snapshot),
        "section_catalog": section_catalog(snapshot),
        "selectable_figures": [
            item
            for item in build_figure_inventory(snapshot)
            if item.get("selectable") is True
        ],
        "runtime_context_memories": [dict(memory) for memory in runtime_memories],
        "exclusion_reason_codes": [
            "disclaimer",
            "analyst_profile",
            "analyst_certificate",
            "contact_information",
            "rating_definition",
            "legal_notice",
            "administrative_metadata",
        ],
        "schema": dict(schema),
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def build_storyboard_messages(
    report_map: Mapping[str, Any],
    schema: Mapping[str, Any],
    system_prompt: str,
) -> list[dict[str, str]]:
    payload = {
        "task": "edit_report_map_into_deck_storyboard",
        "report_map": dict(report_map),
        "constraints": {
            "content_slide_has_one_claim": True,
            "content_slide_has_unique_purpose": True,
            "headline_is_audience_facing_takeaway": True,
            "section_title_is_provenance_not_headline": True,
            "excluded_content_must_not_be_used": True,
            "native_figure_may_share_content_slide": True,
            "native_figure_requires_supports_claim": True,
            "recommended_visuals_per_content_slide": 1,
            "maximum_visuals_per_content_slide": 2,
            "do_not_emit_chart_values": True,
        },
        "schema": dict(schema),
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def preview_report_map(snapshot: DocumentIntelligenceSnapshot) -> dict[str, Any]:
    """Schema-shaped placeholder used only to preview the second LLM request."""

    metadata = snapshot.metadata
    source_file = str(metadata.get("source_file") or "document")
    return {
        "schema_version": "1.0.0",
        "report_id": str(metadata.get("id") or "document"),
        "source_id": source_id_for(snapshot),
        "presentation_metadata": {
            "company": "",
            "company_name": "",
            "stock_code": "",
            "industry": "",
            "report_title": str(metadata.get("title") or source_file),
            "report_date": "",
            "source_file": source_file,
        },
        "sections": [
            {
                "section_ref": item["section_ref"],
                "section_title": item["section_title"],
                "summary": "dry-run preview",
                "claims": [],
                "native_figures": [],
            }
            for item in section_catalog(snapshot)
            if item["section_title"]
        ],
        "excluded_content": [],
    }


def _ref_set(values: object) -> set[tuple[str, str]]:
    if not isinstance(values, list):
        return set()
    return {
        (str(item.get("kind") or ""), str(item.get("id") or ""))
        for item in values
        if isinstance(item, Mapping)
    }


def _canonical_section_titles(
    snapshot: DocumentIntelligenceSnapshot,
) -> dict[str, str]:
    return {
        item["section_ref"]: item["section_title"]
        for item in section_catalog(snapshot)
    }


def validate_report_map(
    report_map: Mapping[str, Any],
    snapshot: DocumentIntelligenceSnapshot,
    allowed_evidence: set[tuple[str, str]] | None = None,
) -> list[Issue]:
    from outline_generator.bundle_validation import validate_outline_evidence

    issues: list[Issue] = []
    titles = _canonical_section_titles(snapshot)
    selectable_figures = {
        str(item["figure_id"])
        for item in build_figure_inventory(snapshot)
        if item.get("selectable") is True
    }
    claim_ids: set[str] = set()
    claim_evidence: set[tuple[str, str]] = set()
    for section_index, section in enumerate(report_map.get("sections", [])):
        if not isinstance(section, Mapping):
            continue
        base = f"$.sections[{section_index}]"
        section_ref = str(section.get("section_ref") or "")
        if section_ref not in titles:
            issues.append(Issue("error", "REPORT_MAP.UNKNOWN_SECTION", f"{base}.section_ref", f"unknown section_ref {section_ref!r}"))
        elif str(section.get("section_title") or "").strip() != titles[section_ref]:
            issues.append(Issue("error", "REPORT_MAP.SECTION_TITLE_MISMATCH", f"{base}.section_title", "section_title must exactly preserve the DocumentBundle heading"))
        for claim_index, claim in enumerate(section.get("claims", [])):
            if not isinstance(claim, Mapping):
                continue
            claim_base = f"{base}.claims[{claim_index}]"
            claim_id = str(claim.get("claim_id") or "")
            if claim_id in claim_ids:
                issues.append(Issue("error", "REPORT_MAP.DUPLICATE_CLAIM_ID", f"{claim_base}.claim_id", f"duplicate claim_id {claim_id!r}"))
            claim_ids.add(claim_id)
            for ref in _ref_set(claim.get("evidence_refs")):
                claim_evidence.add(ref)
                if snapshot.evidence(*ref) is None:
                    issues.append(Issue("error", "REPORT_MAP.UNKNOWN_EVIDENCE", f"{claim_base}.evidence_refs", f"unknown evidence {ref!r}"))
                elif ref[0] == "figure" and ref[1] not in selectable_figures:
                    issues.append(Issue("error", "REPORT_MAP.FIGURE_ASSET_UNAVAILABLE", f"{claim_base}.evidence_refs", f"figure {ref[1]!r} has no available original asset"))
                elif allowed_evidence is not None and ref not in allowed_evidence:
                    issues.append(Issue("error", "REPORT_MAP.OUT_OF_CONTEXT_EVIDENCE", f"{claim_base}.evidence_refs", f"evidence {ref!r} was not available to the model"))
            numeric_probe = {
                "slides": [{
                    "page_role": "content",
                    "slide_type": "summary",
                    "title": "",
                    "key_message": str(claim.get("text") or ""),
                    "bullet_points": [],
                    "section_ref": section_ref,
                    "source_refs": [source_id_for(snapshot)],
                    "evidence_refs": list(claim.get("evidence_refs", [])),
                    "visual_candidates": [],
                }]
            }
            issues.extend(
                Issue(
                    issue.severity,
                    issue.code,
                    f"{claim_base}.text",
                    issue.message,
                )
                for issue in validate_outline_evidence(
                    numeric_probe,
                    snapshot,
                    allowed_evidence,
                )
                if issue.code == "BUNDLE.UNGROUNDED_NUMBER"
            )
        for figure_id in section.get("native_figures", []):
            if str(figure_id) not in snapshot.figures_by_id:
                issues.append(Issue("error", "REPORT_MAP.UNKNOWN_FIGURE", f"{base}.native_figures", f"unknown figure {figure_id!r}"))
            elif str(figure_id) not in selectable_figures:
                issues.append(Issue("error", "REPORT_MAP.FIGURE_ASSET_UNAVAILABLE", f"{base}.native_figures", f"figure {figure_id!r} has no available original asset"))

    excluded: set[tuple[str, str]] = set()
    for index, item in enumerate(report_map.get("excluded_content", [])):
        if not isinstance(item, Mapping):
            continue
        refs = _ref_set([item.get("evidence_ref")])
        if not refs:
            continue
        ref = next(iter(refs))
        excluded.add(ref)
        if snapshot.evidence(*ref) is None:
            issues.append(Issue("error", "REPORT_MAP.UNKNOWN_EXCLUSION", f"$.excluded_content[{index}].evidence_ref", f"unknown evidence {ref!r}"))
    overlap = claim_evidence & excluded
    if overlap:
        issues.append(Issue("error", "REPORT_MAP.EXCLUDED_EVIDENCE_USED", "$.excluded_content", f"excluded evidence is also used by claims: {sorted(overlap)}"))
    return issues


def normalize_report_map_assets(
    report_map: dict[str, Any],
    snapshot: DocumentIntelligenceSnapshot,
) -> None:
    """Drop unusable figure registrations and ungrounded candidate claims."""

    from outline_generator.bundle_validation import validate_outline_evidence

    selectable = {
        str(item["figure_id"])
        for item in build_figure_inventory(snapshot)
        if item.get("selectable") is True
    }
    for section in report_map.get("sections", []):
        if isinstance(section, dict):
            grounded_claims = []
            for claim in section.get("claims", []):
                if not isinstance(claim, dict):
                    continue
                numeric_probe = {
                    "slides": [{
                        "page_role": "content",
                        "slide_type": "summary",
                        "title": "",
                        "key_message": str(claim.get("text") or ""),
                        "bullet_points": [],
                        "section_ref": str(section.get("section_ref") or ""),
                        "source_refs": [source_id_for(snapshot)],
                        "evidence_refs": list(claim.get("evidence_refs", [])),
                        "visual_candidates": [],
                    }]
                }
                numeric_errors = [
                    issue
                    for issue in validate_outline_evidence(numeric_probe, snapshot)
                    if issue.code == "BUNDLE.UNGROUNDED_NUMBER"
                ]
                if not numeric_errors:
                    grounded_claims.append(claim)
            section["claims"] = grounded_claims
            section["native_figures"] = [
                figure_id
                for figure_id in section.get("native_figures", [])
                if str(figure_id) in selectable
            ]


def validate_storyboard(
    storyboard: Mapping[str, Any],
    report_map: Mapping[str, Any],
    snapshot: DocumentIntelligenceSnapshot,
) -> list[Issue]:
    issues: list[Issue] = []
    titles = _canonical_section_titles(snapshot)
    claims: dict[str, Mapping[str, Any]] = {}
    report_refs: set[tuple[str, str]] = set()
    for section in report_map.get("sections", []):
        if not isinstance(section, Mapping):
            continue
        for claim in section.get("claims", []):
            if isinstance(claim, Mapping):
                claims[str(claim.get("claim_id") or "")] = claim
                report_refs.update(_ref_set(claim.get("evidence_refs")))
        report_refs.update(
            ("figure", str(figure_id))
            for figure_id in section.get("native_figures", [])
        )
    excluded = {
        ref
        for item in report_map.get("excluded_content", [])
        if isinstance(item, Mapping)
        for ref in _ref_set([item.get("evidence_ref")])
    }
    purposes: dict[str, int] = {}
    story_ids: set[str] = set()
    for index, slide in enumerate(storyboard.get("slides", [])):
        if not isinstance(slide, Mapping):
            continue
        base = f"$.slides[{index}]"
        story_id = str(slide.get("story_id") or "")
        if story_id in story_ids:
            issues.append(Issue("error", "STORYBOARD.DUPLICATE_STORY_ID", f"{base}.story_id", f"duplicate story_id {story_id!r}"))
        story_ids.add(story_id)
        purpose_key = _SPACE_RE.sub("", str(slide.get("purpose") or "")).casefold()
        if purpose_key in purposes:
            issues.append(Issue("error", "STORYBOARD.DUPLICATE_PURPOSE", f"{base}.purpose", f"purpose duplicates slide {purposes[purpose_key] + 1}"))
        purposes[purpose_key] = index

        if slide.get("page_role") != "content":
            continue
        section_ref = str(slide.get("section_ref") or "")
        if section_ref not in titles:
            issues.append(Issue("error", "STORYBOARD.UNKNOWN_SECTION", f"{base}.section_ref", f"unknown section_ref {section_ref!r}"))
        elif str(slide.get("section_title") or "").strip() != titles[section_ref]:
            issues.append(Issue("error", "STORYBOARD.SECTION_TITLE_MISMATCH", f"{base}.section_title", "section_title must preserve provenance and may not be rewritten as the headline"))
        claim_ref = str(slide.get("claim_ref") or "")
        source_claim = claims.get(claim_ref)
        if source_claim is None:
            issues.append(Issue("error", "STORYBOARD.UNKNOWN_CLAIM", f"{base}.claim_ref", f"unknown claim_ref {claim_ref!r}"))
            claim_refs: set[tuple[str, str]] = set()
        else:
            claim_refs = _ref_set(source_claim.get("evidence_refs"))
            if str(slide.get("claim") or "").strip() != str(source_claim.get("text") or "").strip():
                issues.append(Issue("error", "STORYBOARD.CLAIM_MISMATCH", f"{base}.claim", "claim must exactly preserve the selected ReportMap claim; rewrite only the headline"))
        slide_refs = _ref_set(slide.get("evidence_refs"))
        if not claim_refs <= slide_refs:
            issues.append(Issue("error", "STORYBOARD.CLAIM_EVIDENCE_MISSING", f"{base}.evidence_refs", "slide evidence must include the selected claim evidence"))
        if not slide_refs <= report_refs:
            issues.append(Issue("error", "STORYBOARD.OUTSIDE_REPORT_MAP", f"{base}.evidence_refs", "supporting evidence must come from ReportMap"))
        if slide_refs & excluded:
            issues.append(Issue("error", "STORYBOARD.EXCLUDED_EVIDENCE", f"{base}.evidence_refs", "excluded evidence cannot enter a presentation page"))
        for visual_index, visual in enumerate(slide.get("visual_candidates", [])):
            if not isinstance(visual, Mapping):
                continue
            visual_refs = _ref_set(visual.get("evidence_refs"))
            if not visual_refs <= slide_refs:
                issues.append(Issue("error", "STORYBOARD.VISUAL_OUTSIDE_SLIDE", f"{base}.visual_candidates[{visual_index}].evidence_refs", "visual evidence must be within the slide evidence"))
            visual_type = str(visual.get("type") or "")
            if visual_type == "image" and any(kind != "figure" for kind, _ in visual_refs):
                issues.append(Issue("error", "STORYBOARD.IMAGE_REQUIRES_FIGURE", f"{base}.visual_candidates[{visual_index}]", "image candidates may reference only native figures"))
            if visual_type in {"chart", "table"} and any(kind == "figure" for kind, _ in visual_refs):
                issues.append(Issue("error", "STORYBOARD.DATA_VISUAL_REQUIRES_DATA", f"{base}.visual_candidates[{visual_index}]", "chart/table candidates cannot use figure evidence"))

    # Catch unsupported numbers while the storyboard LLM can still correct its
    # wording or citations, instead of failing only after deterministic adaptation.
    from outline_generator.bundle_validation import validate_outline_evidence

    issues.extend(
        issue
        for issue in validate_outline_evidence(
            storyboard_to_outline(report_map, storyboard),
            snapshot,
        )
        if issue.code in {
            "BUNDLE.UNGROUNDED_NUMBER",
            "BUNDLE.SLIDE_WITHOUT_SECTION",
            "BUNDLE.SECTION_ORDER",
        }
    )
    return issues


def normalize_storyboard_shape(
    storyboard: dict[str, Any],
    report_map: Mapping[str, Any] | None = None,
) -> None:
    """Apply deterministic size, numeric, and evidence safety fallbacks."""

    from outline_generator.bundle_validation import _number_keys_in_text

    slides = [item for item in storyboard.get("slides", []) if isinstance(item, dict)]
    if len(slides) > 24:
        title = next((item for item in slides if item.get("page_role") == "title"), None)
        closing = next((item for item in reversed(slides) if item.get("page_role") == "closing"), None)
        boundaries = [item for item in (title, closing) if item is not None]
        content = [item for item in slides if item.get("page_role") == "content"]
        limit = 24 - len(boundaries)
        if len(content) > limit and limit > 1:
            indexes = [
                index * (len(content) - 1) // (limit - 1)
                for index in range(limit)
            ]
            content = [content[index] for index in indexes]
        storyboard["slides"] = ([title] if title else []) + content[:limit] + ([closing] if closing else [])

    claims: dict[str, Mapping[str, Any]] = {}
    allowed_refs: set[tuple[str, str]] = set()
    excluded_refs: set[tuple[str, str]] = set()
    if report_map is not None:
        for section in report_map.get("sections", []):
            if not isinstance(section, Mapping):
                continue
            for claim in section.get("claims", []):
                if isinstance(claim, Mapping):
                    claims[str(claim.get("claim_id") or "")] = claim
                    allowed_refs.update(_ref_set(claim.get("evidence_refs")))
            allowed_refs.update(
                ("figure", str(figure_id))
                for figure_id in section.get("native_figures", [])
            )
        excluded_refs = {
            ref
            for item in report_map.get("excluded_content", [])
            if isinstance(item, Mapping)
            for ref in _ref_set([item.get("evidence_ref")])
        }

    for slide in storyboard.get("slides", []):
        if not isinstance(slide, dict):
            continue
        if slide.get("page_role") != "content":
            slide.setdefault("claim", None)
            continue
        evidence = list(slide.get("evidence_refs", []))
        evidence_keys = _ref_set(evidence)
        source_claim = claims.get(str(slide.get("claim_ref") or ""))
        claim_text = str(
            source_claim.get("text") if source_claim else slide.get("claim") or ""
        )
        claim_numbers = _number_keys_in_text(claim_text)
        headline = str(slide.get("headline") or "")
        if len(headline) > 80 or not _number_keys_in_text(headline) <= claim_numbers:
            fallback = re.split(r"[，；。;]", claim_text, maxsplit=1)[0].strip()
            if (
                not fallback
                or len(fallback) > 80
                or not _number_keys_in_text(fallback) <= claim_numbers
            ):
                fallback = "核心结论"
            slide["headline"] = fallback
        slide["supporting_points"] = [
            point
            for point in slide.get("supporting_points", [])
            if _number_keys_in_text(point) <= claim_numbers
        ]
        required = _ref_set(source_claim.get("evidence_refs")) if source_claim else set()
        visuals = slide.get("visual_candidates", [])
        for visual in visuals if isinstance(visuals, list) else []:
            if not isinstance(visual, dict):
                continue
            visual_refs = _ref_set(visual.get("evidence_refs"))
            required.update((visual_refs & allowed_refs) - excluded_refs)
            if visual_refs and all(kind == "figure" for kind, _ in visual_refs):
                visual["type"] = "image"
                visual.pop("chart_intent", None)
        for kind, reference_id in sorted(required - evidence_keys):
            evidence.append({"kind": kind, "id": reference_id})
        slide["evidence_refs"] = evidence


def storyboard_to_outline(
    report_map: Mapping[str, Any],
    storyboard: Mapping[str, Any],
) -> dict[str, Any]:
    source_id = str(report_map["source_id"])
    metadata = dict(report_map["presentation_metadata"])
    slides: list[dict[str, Any]] = []
    for index, story in enumerate(storyboard.get("slides", []), start=1):
        if not isinstance(story, Mapping):
            continue
        claim = str(story.get("claim") or "").strip()
        headline = str(story.get("headline") or "").strip()
        purpose = str(story.get("purpose") or "").strip()
        slide: dict[str, Any] = {
            "slide_id": f"slide_{index:03d}",
            "page_role": story["page_role"],
            "slide_type": story["slide_type"],
            "title": headline,
            "headline": headline,
            "purpose": purpose,
            "claim": claim or None,
            "key_message": claim or purpose or headline,
            "bullet_points": list(story.get("supporting_points", [])),
            "source_refs": [source_id],
            "evidence_refs": list(story.get("evidence_refs", [])),
            "visual_candidates": [
                {
                    "candidate_id": visual["candidate_id"],
                    "type": visual["type"],
                    "description": visual["purpose"],
                    "purpose": visual["purpose"],
                    "supports_claim": True,
                    "source_refs": [source_id],
                    "evidence_refs": list(visual.get("evidence_refs", [])),
                    **(
                        {"chart_intent": visual["chart_intent"]}
                        if visual.get("chart_intent")
                        else {}
                    ),
                }
                for visual in story.get("visual_candidates", [])
                if isinstance(visual, Mapping)
            ],
        }
        if story.get("section_ref"):
            slide["section_ref"] = story["section_ref"]
            slide["section_title"] = story["section_title"]
            slide["section"] = story["section_title"]
        if story.get("layout_hint"):
            slide["layout_hint"] = story["layout_hint"]
        slides.append(slide)
    return {
        "schema_version": "1.0.0",
        "metadata": metadata,
        "sources": [
            {
                "source_id": source_id,
                "type": "broker_report",
                "title": metadata["report_title"],
                "published_date": metadata.get("report_date", ""),
                "file_name": metadata["source_file"],
            }
        ],
        "slides": slides,
    }


def legacy_outline_to_editorial_artifacts(
    outline: Mapping[str, Any],
    snapshot: DocumentIntelligenceSnapshot,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create auditable compatibility artifacts without changing an old outline."""

    source_id = str(
        next(
            (
                item.get("source_id")
                for item in outline.get("sources", [])
                if isinstance(item, Mapping) and item.get("source_id")
            ),
            source_id_for(snapshot),
        )
    )
    section_items: dict[str, dict[str, Any]] = {}
    storyboard_slides: list[dict[str, Any]] = []
    for index, slide in enumerate(outline.get("slides", []), start=1):
        if not isinstance(slide, Mapping):
            continue
        section_ref = str(slide.get("section_ref") or "")
        section_title = str(slide.get("section_title") or slide.get("section") or "").strip()
        claim_id = f"claim_legacy_{index:03d}"
        claim = str(slide.get("claim") or slide.get("key_message") or slide.get("title") or "").strip()
        refs = list(slide.get("evidence_refs", []))
        if section_ref:
            section = section_items.setdefault(
                section_ref,
                {
                    "section_ref": section_ref,
                    "section_title": section_title or _canonical_section_titles(snapshot).get(section_ref, section_ref),
                    "summary": claim or section_title or "Legacy outline section",
                    "claims": [],
                    "native_figures": [],
                },
            )
            if slide.get("page_role") == "content" and refs:
                section["claims"].append(
                    {"claim_id": claim_id, "text": claim, "evidence_refs": refs}
                )
                section["native_figures"].extend(
                    str(ref.get("id"))
                    for ref in refs
                    if isinstance(ref, Mapping) and ref.get("kind") == "figure"
                )
                section["native_figures"] = list(dict.fromkeys(section["native_figures"]))
        candidates = []
        for visual in slide.get("visual_candidates", []):
            if not isinstance(visual, Mapping):
                continue
            candidates.append(
                {
                    "candidate_id": visual.get("candidate_id", f"visual_legacy_{index:03d}"),
                    "type": visual.get("type", "chart"),
                    "purpose": visual.get("purpose") or visual.get("description") or claim,
                    "supports_claim": True,
                    "evidence_refs": list(visual.get("evidence_refs") or refs),
                    **({"chart_intent": visual["chart_intent"]} if visual.get("chart_intent") else {}),
                }
            )
        storyboard_slides.append(
            {
                "story_id": f"story_legacy_{index:03d}",
                "page_role": slide.get("page_role", "content"),
                "slide_type": slide.get("slide_type", "summary"),
                "purpose": slide.get("purpose") or slide.get("key_message") or slide.get("title"),
                "claim": claim if slide.get("page_role") == "content" else None,
                "headline": slide.get("headline") or slide.get("title"),
                "supporting_points": list(slide.get("bullet_points", [])),
                "evidence_refs": refs,
                "visual_candidates": candidates,
                **(
                    {
                        "section_ref": section_ref,
                        "section_title": section_title
                        or _canonical_section_titles(snapshot).get(
                            section_ref, section_ref
                        ),
                    }
                    if section_ref
                    and slide.get("page_role") in {"content", "section"}
                    else {}
                ),
                **(
                    {"claim_ref": claim_id}
                    if section_ref and slide.get("page_role") == "content"
                    else {}
                ),
            }
        )
    metadata = dict(outline.get("metadata", {}))
    report_map = {
        "schema_version": "1.0.0",
        "report_id": str(snapshot.metadata.get("id") or "document"),
        "source_id": source_id,
        "presentation_metadata": metadata,
        "sections": list(section_items.values()),
        "excluded_content": [],
    }
    storyboard = {
        "schema_version": "1.0.0",
        "report_id": report_map["report_id"],
        "slides": storyboard_slides,
    }
    return report_map, storyboard

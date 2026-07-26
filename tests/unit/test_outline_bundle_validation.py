from __future__ import annotations

from pathlib import Path

from document_bundle.markdown import build_from_markdown
from document_intelligence import load_document_intelligence
from outline_generator.bundle_validation import (
    canonicalize_outline_from_bundle,
    normalize_topic_sentence_key_messages,
    validate_outline_evidence,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _snapshot(tmp_path):
    bundle = tmp_path / "document_bundle"
    build_from_markdown(PROJECT_ROOT / "tests" / "fixtures" / "heading_paragraph.md", bundle)
    return load_document_intelligence(
        bundle, PROJECT_ROOT / "schemas" / "document_bundle.schema.json"
    )


def _content_slide(section_id, block_id):
    return {
        "page_role": "content",
        "section_ref": section_id,
        "evidence_refs": [{"kind": "block", "id": block_id}],
        "source_refs": ["src_fixture"],
    }


def test_valid_native_section_and_evidence_pass(tmp_path):
    snapshot = _snapshot(tmp_path)
    section_id = snapshot.section_order[0]
    block_id = next(
        value
        for value in snapshot.ordered_block_ids
        if snapshot.blocks_by_id[value].get("section_id") == section_id
    )
    assert validate_outline_evidence(
        {"slides": [_content_slide(section_id, block_id)]}, snapshot
    ) == []


def test_unknown_section_and_evidence_are_rejected(tmp_path):
    snapshot = _snapshot(tmp_path)
    issues = validate_outline_evidence(
        {"slides": [_content_slide("sec-missing", "block-missing")]}, snapshot
    )
    assert {issue.code for issue in issues} >= {
        "BUNDLE.UNKNOWN_SECTION",
        "BUNDLE.UNKNOWN_EVIDENCE",
    }


def test_section_order_cannot_move_backwards(tmp_path):
    snapshot = _snapshot(tmp_path)
    first, second = snapshot.section_order[:2]
    first_block = next(
        value for value in snapshot.ordered_block_ids
        if snapshot.blocks_by_id[value].get("section_id") == first
    )
    second_block = next(
        value for value in snapshot.ordered_block_ids
        if snapshot.blocks_by_id[value].get("section_id") == second
    )
    issues = validate_outline_evidence(
        {
            "slides": [
                _content_slide(second, second_block),
                _content_slide(first, first_block),
            ]
        },
        snapshot,
    )
    assert any(issue.code == "BUNDLE.SECTION_ORDER" for issue in issues)


def test_content_slide_requires_section_and_evidence(tmp_path):
    issues = validate_outline_evidence(
        {"slides": [{"page_role": "content"}]}, _snapshot(tmp_path)
    )
    assert {issue.code for issue in issues} == {
        "BUNDLE.CONTENT_WITHOUT_EVIDENCE",
        "BUNDLE.CONTENT_WITHOUT_SOURCE",
        "BUNDLE.SLIDE_WITHOUT_SECTION",
    }


def test_content_title_must_preserve_section_heading(tmp_path):
    snapshot = _snapshot(tmp_path)
    section_id = snapshot.section_order[0]
    block_id = next(
        value
        for value in snapshot.ordered_block_ids
        if snapshot.blocks_by_id[value].get("section_id") == section_id
        and snapshot.blocks_by_id[value].get("type") == "paragraph"
    )
    slide = _content_slide(section_id, block_id)
    slide["title"] = "模型自行总结的标题"
    issues = validate_outline_evidence({"slides": [slide]}, snapshot)
    assert any(issue.code == "BUNDLE.SECTION_SLIDE_TITLE" for issue in issues)


def test_concise_first_sentence_must_be_preserved_as_key_message(tmp_path):
    snapshot = _snapshot(tmp_path)
    section_id = snapshot.section_order[0]
    block_id = next(
        value
        for value in snapshot.ordered_block_ids
        if snapshot.blocks_by_id[value].get("section_id") == section_id
        and snapshot.blocks_by_id[value].get("type") == "paragraph"
    )
    title_block_id = snapshot.sections_by_id[section_id]["title_block_id"]
    slide = _content_slide(section_id, block_id)
    slide["title"] = snapshot.blocks_by_id[title_block_id]["text_raw"]
    slide["key_message"] = "模型重新概括的主旨"
    issues = validate_outline_evidence({"slides": [slide]}, snapshot)
    assert any(issue.code == "BUNDLE.TOPIC_SENTENCE_MISMATCH" for issue in issues)


def test_topic_sentence_is_restored_before_validation(tmp_path):
    snapshot = _snapshot(tmp_path)
    section_id = snapshot.section_order[0]
    block_id = next(
        value
        for value in snapshot.ordered_block_ids
        if snapshot.blocks_by_id[value].get("section_id") == section_id
        and snapshot.blocks_by_id[value].get("type") == "paragraph"
    )
    title_block_id = snapshot.sections_by_id[section_id]["title_block_id"]
    slide = _content_slide(section_id, block_id)
    slide["title"] = snapshot.blocks_by_id[title_block_id]["text_raw"]
    slide["key_message"] = "模型重新概括的主旨"
    outline = {"slides": [slide]}

    assert normalize_topic_sentence_key_messages(outline, snapshot) == 1
    assert not any(
        issue.code == "BUNDLE.TOPIC_SENTENCE_MISMATCH"
        for issue in validate_outline_evidence(outline, snapshot)
    )


def test_numeric_claims_must_exist_in_cited_evidence(tmp_path):
    snapshot = _snapshot(tmp_path)
    section_id = snapshot.section_order[0]
    block_id = next(
        value
        for value in snapshot.ordered_block_ids
        if snapshot.blocks_by_id[value].get("section_id") == section_id
        and snapshot.blocks_by_id[value].get("type") == "paragraph"
    )
    title_block_id = snapshot.sections_by_id[section_id]["title_block_id"]
    slide = _content_slide(section_id, block_id)
    slide["title"] = snapshot.blocks_by_id[title_block_id]["text_raw"]
    slide["bullet_points"] = ["2026年收入增长99%。"]
    issues = validate_outline_evidence({"slides": [slide]}, snapshot)
    assert any(issue.code == "BUNDLE.UNGROUNDED_NUMBER" for issue in issues)


def test_equivalent_numeric_formatting_is_grounded(tmp_path):
    source = tmp_path / "valuation.md"
    source.write_text(
        "# 估值\n\n2026年EV/EBITDA为34.00倍，2028年为8.50倍，股息率为2.50%。\n",
        encoding="utf-8",
    )
    bundle = tmp_path / "valuation_bundle"
    build_from_markdown(source, bundle)
    snapshot = load_document_intelligence(
        bundle, PROJECT_ROOT / "schemas" / "document_bundle.schema.json"
    )
    section_id = snapshot.section_order[0]
    block_id = next(
        value
        for value in snapshot.ordered_block_ids
        if snapshot.blocks_by_id[value].get("type") == "paragraph"
    )
    slide = _content_slide(section_id, block_id)
    slide["key_message"] = "估值逐步回落。"
    slide["bullet_points"] = ["EV/EBITDA由34倍降至8.5倍，股息率升至2.5%。"]

    issues = validate_outline_evidence({"slides": [slide]}, snapshot)

    assert not any(issue.code == "BUNDLE.UNGROUNDED_NUMBER" for issue in issues)


def test_bundle_canonicalization_owns_section_labels_and_titles(tmp_path):
    snapshot = _snapshot(tmp_path)
    section_id = snapshot.section_order[0]
    section = snapshot.sections_by_id[section_id]
    canonical_title = snapshot.blocks_by_id[section["title_block_id"]]["text_raw"]
    block_id = next(
        value
        for value in snapshot.ordered_block_ids
        if snapshot.blocks_by_id[value].get("section_id") == section_id
        and snapshot.blocks_by_id[value].get("type") == "paragraph"
    )
    slide = _content_slide(section_id, block_id)
    slide.update({"section": "模型改写章节", "title": "模型总结标题"})

    changes = canonicalize_outline_from_bundle({"slides": [slide]}, snapshot)

    assert slide["section"] == canonical_title
    assert slide["title"] == canonical_title
    assert changes == {
        "labels": 1,
        "titles": 1,
        "evidence_refs": 0,
        "null_fields": 0,
        "figure_pages_removed": 0,
    }


def test_bundle_canonicalization_adds_omitted_numeric_evidence(tmp_path):
    source = tmp_path / "industry.md"
    source.write_text(
        "# 行业格局\n\n企业级需求保持强劲。\n\n"
        "前五大厂商营收季增16.5%，逼近171亿美元。\n",
        encoding="utf-8",
    )
    bundle = tmp_path / "industry_bundle"
    build_from_markdown(source, bundle)
    snapshot = load_document_intelligence(
        bundle, PROJECT_ROOT / "schemas" / "document_bundle.schema.json"
    )
    section_id = snapshot.section_order[0]
    paragraphs = [
        value
        for value in snapshot.ordered_block_ids
        if snapshot.blocks_by_id[value].get("type") == "paragraph"
    ]
    slide = _content_slide(section_id, paragraphs[0])
    slide.update(
        {
            "section": "行业格局",
            "title": "行业格局",
            "key_message": "企业级需求保持强劲。",
            "bullet_points": ["前五大厂商营收季增16.5%，逼近171亿美元。"],
        }
    )
    allowed = {("block", value) for value in paragraphs}

    changes = canonicalize_outline_from_bundle(
        {"slides": [slide]}, snapshot, allowed
    )
    issues = validate_outline_evidence({"slides": [slide]}, snapshot, allowed)

    assert {ref["id"] for ref in slide["evidence_refs"]} == set(paragraphs)
    assert changes["evidence_refs"] == 1
    assert not any(issue.code == "BUNDLE.UNGROUNDED_NUMBER" for issue in issues)


def test_bundle_canonicalization_removes_unavailable_figure_pages_and_null_optionals(
    tmp_path,
):
    source = tmp_path / "placeholders.md"
    source.write_text(
        "# 行业趋势\n\n![趋势图](chart:missing-chart)\n",
        encoding="utf-8",
    )
    bundle = tmp_path / "placeholder_bundle"
    build_from_markdown(source, bundle)
    snapshot = load_document_intelligence(
        bundle, PROJECT_ROOT / "schemas" / "document_bundle.schema.json"
    )
    figure_id = next(iter(snapshot.figures_by_id))
    outline = {
        "slides": [
            {
                "slide_id": "slide_001",
                "page_role": "content",
                "slide_type": "figure_page",
                "section_ref": snapshot.section_order[0],
                "evidence_refs": [{"kind": "figure", "id": figure_id}],
            },
            {
                "slide_id": "slide_002",
                "page_role": "closing",
                "slide_type": "closing",
                "section_ref": None,
                "evidence_refs": [],
            },
        ]
    }

    changes = canonicalize_outline_from_bundle(outline, snapshot)

    assert [slide["slide_id"] for slide in outline["slides"]] == ["slide_002"]
    assert "section_ref" not in outline["slides"][0]
    assert changes["figure_pages_removed"] == 1
    assert changes["null_fields"] == 1


def test_visual_candidate_requires_native_evidence(tmp_path):
    snapshot = _snapshot(tmp_path)
    section_id = snapshot.section_order[0]
    block_id = next(
        value
        for value in snapshot.ordered_block_ids
        if snapshot.blocks_by_id[value].get("section_id") == section_id
    )
    slide = _content_slide(section_id, block_id)
    slide["visual_candidates"] = [
        {
            "candidate_id": "visual_001",
            "type": "table",
            "description": "展示原文表格",
            "source_refs": ["src_fixture"],
        }
    ]
    issues = validate_outline_evidence({"slides": [slide]}, snapshot)
    assert any(
        issue.code == "BUNDLE.VISUAL_WITHOUT_NATIVE_EVIDENCE"
        for issue in issues
    )


def test_content_slide_visual_budget_is_enforced_during_llm_retry(tmp_path):
    snapshot = _snapshot(tmp_path)
    section_id = snapshot.section_order[0]
    block_id = next(
        value
        for value in snapshot.ordered_block_ids
        if snapshot.blocks_by_id[value].get("section_id") == section_id
    )
    slide = _content_slide(section_id, block_id)
    slide["visual_candidates"] = [
        {
            "candidate_id": f"visual_{index:03d}",
            "type": "chart",
            "description": "Evidence chart",
            "source_refs": ["src_fixture"],
            "evidence_refs": [{"kind": "block", "id": block_id}],
        }
        for index in range(1, 4)
    ]

    issues = validate_outline_evidence({"slides": [slide]}, snapshot)

    budget = [
        issue for issue in issues
        if issue.code == "LAYOUT.VISUAL_BUDGET_EXCEEDED"
    ]
    assert len(budget) == 1
    assert "maximum is 2" in budget[0].message

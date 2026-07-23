from __future__ import annotations

from pathlib import Path

from document_bundle.markdown import build_from_markdown
from document_intelligence import load_document_intelligence
from outline_generator.bundle_validation import validate_outline_evidence


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

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from document_intelligence import build_snapshot
from outline_generator.editorial import (
    legacy_outline_to_editorial_artifacts,
    normalize_report_map_assets,
    normalize_storyboard_shape,
    storyboard_to_outline,
    validate_report_map,
    validate_storyboard,
)
from tools.validate_outline import validate_outline


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _snapshot(tmp_path):
    block = {
        "id": "block-001",
        "page": 1,
        "type": "paragraph",
        "text_raw": "公司收入保持增长。",
        "bbox": None,
        "parser_order": 0,
        "reading_order": 0,
        "section_id": "section-001",
        "source_type": "test",
    }
    document = {
        "document": {
            "id": "report-001",
            "title": "测试研报",
            "page_count": 1,
            "source_sha256": "0" * 64,
            "source_file": "report.md",
            "source_format": "markdown",
        },
        "pages": [{"id": "page-001", "page": 1, "width": 100, "height": 100, "block_ids": ["block-001"]}],
        "blocks": [block],
        "sections": [{"id": "section-001", "level": 1, "title_block_id": "block-001", "parent_id": None, "child_section_ids": [], "content_block_ids": ["block-001"]}],
        "tables": [],
        "figures": [],
        "reading_order": ["block-001"],
    }
    return build_snapshot(document, tmp_path)


def _report_map():
    return {
        "schema_version": "1.0.0",
        "report_id": "report-001",
        "source_id": "src_report-001",
        "presentation_metadata": {
            "company": "测试公司",
            "company_name": "测试公司",
            "stock_code": "000001",
            "industry": "测试行业",
            "report_title": "测试研报",
            "report_date": "2026-07-26",
            "source_file": "report.md",
        },
        "sections": [{
            "section_ref": "section-001",
            "section_title": "公司收入保持增长。",
            "summary": "收入增长",
            "claims": [{
                "claim_id": "claim-001",
                "text": "公司收入保持增长",
                "evidence_refs": [{"kind": "block", "id": "block-001"}],
            }],
            "native_figures": [],
        }],
        "excluded_content": [],
    }


def _storyboard():
    return {
        "schema_version": "1.0.0",
        "report_id": "report-001",
        "slides": [{
            "story_id": "story-001",
            "page_role": "content",
            "slide_type": "company_overview",
            "section_ref": "section-001",
            "section_title": "公司收入保持增长。",
            "purpose": "说明收入趋势",
            "claim_ref": "claim-001",
            "claim": "公司收入保持增长",
            "headline": "收入延续增长趋势",
            "supporting_points": ["增长结论来自研报正文"],
            "evidence_refs": [{"kind": "block", "id": "block-001"}],
            "visual_candidates": [],
        }],
    }


def test_report_map_and_storyboard_validate_against_native_evidence(tmp_path):
    snapshot = _snapshot(tmp_path)

    assert validate_report_map(_report_map(), snapshot) == []
    assert validate_storyboard(_storyboard(), _report_map(), snapshot) == []


def test_storyboard_rejects_excluded_evidence(tmp_path):
    snapshot = _snapshot(tmp_path)
    report_map = _report_map()
    report_map["excluded_content"] = [{
        "evidence_ref": {"kind": "block", "id": "block-001"},
        "reason_code": "disclaimer",
        "reason": "免责声明",
    }]

    report_issues = validate_report_map(report_map, snapshot)
    story_issues = validate_storyboard(_storyboard(), report_map, snapshot)

    assert any(issue.code == "REPORT_MAP.EXCLUDED_EVIDENCE_USED" for issue in report_issues)
    assert any(issue.code == "STORYBOARD.EXCLUDED_EVIDENCE" for issue in story_issues)


def test_storyboard_adapter_uses_headline_for_display_and_claim_for_message():
    outline = storyboard_to_outline(_report_map(), _storyboard())
    slide = outline["slides"][0]

    assert slide["section_title"] == "公司收入保持增长。"
    assert slide["title"] == "收入延续增长趋势"
    assert slide["headline"] == "收入延续增长趋势"
    assert slide["key_message"] == "公司收入保持增长"
    assert slide["purpose"] == "说明收入趋势"

    schema = json.loads(
        (PROJECT_ROOT / "schemas/slide_outline.schema.json").read_text(encoding="utf-8")
    )
    assert not [issue for issue in validate_outline(outline, schema) if issue.severity == "error"]


def test_storyboard_rejects_duplicate_purpose(tmp_path):
    snapshot = _snapshot(tmp_path)
    storyboard = _storyboard()
    duplicate = deepcopy(storyboard["slides"][0])
    duplicate["story_id"] = "story-002"
    storyboard["slides"].append(duplicate)

    issues = validate_storyboard(storyboard, _report_map(), snapshot)

    assert any(issue.code == "STORYBOARD.DUPLICATE_PURPOSE" for issue in issues)


def test_storyboard_rejects_ungrounded_numbers_before_adaptation(tmp_path):
    snapshot = _snapshot(tmp_path)
    storyboard = _storyboard()
    storyboard["slides"][0]["supporting_points"] = ["收入规模达到800亿元"]

    issues = validate_storyboard(storyboard, _report_map(), snapshot)

    assert any(issue.code == "BUNDLE.UNGROUNDED_NUMBER" for issue in issues)


def test_report_map_rejects_ungrounded_claim_numbers(tmp_path):
    snapshot = _snapshot(tmp_path)
    report_map = _report_map()
    report_map["sections"][0]["claims"][0]["text"] = "收入达到800亿元"

    issues = validate_report_map(report_map, snapshot)

    assert any(issue.code == "BUNDLE.UNGROUNDED_NUMBER" for issue in issues)


def test_storyboard_shape_adds_null_claim_only_to_non_content_pages():
    storyboard = {
        "slides": [
            {"page_role": "title"},
            {"page_role": "content", "claim": "保留主张"},
        ]
    }

    normalize_storyboard_shape(storyboard)

    assert storyboard["slides"][0]["claim"] is None
    assert storyboard["slides"][1]["claim"] == "保留主张"


def test_storyboard_shape_keeps_claim_and_visual_evidence_on_slide():
    report_map = _report_map()
    report_map["sections"][0]["native_figures"] = ["figure-001"]
    storyboard = _storyboard()
    storyboard["slides"][0]["evidence_refs"] = []
    storyboard["slides"][0]["visual_candidates"] = [{
        "candidate_id": "visual-001",
        "type": "chart",
        "purpose": "展示原图",
        "evidence_refs": [{"kind": "figure", "id": "figure-001"}],
        "chart_intent": "line",
    }]

    normalize_storyboard_shape(storyboard, report_map)

    slide = storyboard["slides"][0]
    assert {tuple(item.values()) for item in slide["evidence_refs"]} == {
        ("block", "block-001"),
        ("figure", "figure-001"),
    }
    assert slide["visual_candidates"][0]["type"] == "image"
    assert "chart_intent" not in slide["visual_candidates"][0]


def test_storyboard_rejects_section_page_without_provenance(tmp_path):
    snapshot = _snapshot(tmp_path)
    storyboard = {
        "schema_version": "1.0.0",
        "report_id": "report-001",
        "slides": [{
            "story_id": "story-section",
            "page_role": "section",
            "slide_type": "summary",
            "purpose": "过渡到下一章节",
            "claim": None,
            "headline": "章节过渡",
            "supporting_points": [],
            "evidence_refs": [],
            "visual_candidates": [],
        }],
    }

    issues = validate_storyboard(storyboard, _report_map(), snapshot)

    assert any(issue.code == "BUNDLE.SLIDE_WITHOUT_SECTION" for issue in issues)


def test_storyboard_shape_caps_long_deck_and_rejects_numeric_rewrites():
    report_map = _report_map()
    report_map["sections"][0]["claims"][0]["text"] = "收入同比增长79.47%"
    content = []
    for index in range(30):
        slide = deepcopy(_storyboard()["slides"][0])
        slide["story_id"] = f"story-{index:03d}"
        slide["claim"] = "收入同比增长79.47%"
        slide["headline"] = "收入同比增长79%"
        slide["supporting_points"] = ["同比增长79%", "保持增长"]
        content.append(slide)
    storyboard = {
        "slides": [
            {"story_id": "title", "page_role": "title"},
            *content,
            {"story_id": "closing", "page_role": "closing"},
        ]
    }

    normalize_storyboard_shape(storyboard, report_map)

    assert len(storyboard["slides"]) == 24
    assert storyboard["slides"][0]["story_id"] == "title"
    assert storyboard["slides"][-1]["story_id"] == "closing"
    assert storyboard["slides"][1]["headline"] == "收入同比增长79.47%"
    assert storyboard["slides"][1]["supporting_points"] == ["保持增长"]


def test_report_map_asset_normalizer_drops_unavailable_registry_entries(tmp_path):
    snapshot = _snapshot(tmp_path)
    report_map = _report_map()
    report_map["sections"][0]["native_figures"] = ["fig-missing"]

    normalize_report_map_assets(report_map, snapshot)

    assert report_map["sections"][0]["native_figures"] == []


def test_report_map_asset_normalizer_drops_ungrounded_candidate_claims(tmp_path):
    snapshot = _snapshot(tmp_path)
    report_map = _report_map()
    report_map["sections"][0]["claims"][0]["text"] = "收入达到800亿元"

    normalize_report_map_assets(report_map, snapshot)

    assert report_map["sections"][0]["claims"] == []


def test_storyboard_shape_uses_first_claim_clause_for_long_headline():
    report_map = _report_map()
    claim = "预计2025-2027年营收65/73/82亿元，同比增长保持稳健，归母净利润持续提升。"
    report_map["sections"][0]["claims"][0]["text"] = claim
    storyboard = _storyboard()
    storyboard["slides"][0]["claim"] = claim
    storyboard["slides"][0]["headline"] = claim * 3

    normalize_storyboard_shape(storyboard, report_map)

    assert storyboard["slides"][0]["headline"] == "预计2025-2027年营收65/73/82亿元"
    assert len(storyboard["slides"][0]["headline"]) <= 80


def test_legacy_section_page_preserves_section_provenance(tmp_path):
    snapshot = _snapshot(tmp_path)
    outline = {
        "metadata": _report_map()["presentation_metadata"],
        "sources": [{"source_id": "src_report-001"}],
        "slides": [{
            "slide_id": "slide-001",
            "page_role": "section",
            "slide_type": "summary",
            "section_ref": "section-001",
            "section": "公司收入保持增长。",
            "title": "章节过渡",
            "key_message": "章节过渡",
            "bullet_points": [],
            "evidence_refs": [],
            "visual_candidates": [],
        }],
    }

    _, storyboard = legacy_outline_to_editorial_artifacts(outline, snapshot)

    assert storyboard["slides"][0]["section_ref"] == "section-001"
    assert storyboard["slides"][0]["section_title"] == "公司收入保持增长。"

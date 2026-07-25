from __future__ import annotations

import json
from pathlib import Path

from document_bundle.markdown import build_from_markdown
from document_intelligence import load_document_intelligence
from outline_generator.bundle_validation import validate_outline_evidence
from outline_generator.front_matter import (
    compact_front_matter_summary_slides,
    detect_front_matter_summary,
    summarize_front_matter_item,
)
from outline_generator.llm_understanding import build_slide_planning_messages


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _snapshot(tmp_path, *, with_highlights: bool = True):
    highlights = (
        """
➢ 核心观点一。公司具备平台优势。

➢ 核心观点二。行业空间持续扩大。

➢ 投资建议。公司盈利有望改善。

➢ 风险提示。市场需求可能波动。
"""
        if with_highlights
        else """
2026 年 7 月 23 日

分析师：示例研究员

邮箱：analyst@example.test
"""
    )
    source = tmp_path / "report.md"
    source.write_text(
        f"""# 示例公司动态报告
{highlights}
# 目录

1 公司概况 …… 3

# 1 公司概况

公司主营业务保持稳定。
""",
        encoding="utf-8",
    )
    bundle = tmp_path / "document_bundle"
    build_from_markdown(source, bundle)
    return load_document_intelligence(
        bundle,
        PROJECT_ROOT / "schemas" / "document_bundle.schema.json",
    )


def _valid_summary_outline(snapshot):
    summary = detect_front_matter_summary(snapshot)
    assert summary is not None
    return {
        "slides": [
            {"page_role": "title"},
            {
                "page_role": "content",
                "slide_type": "summary",
                "section_ref": summary.section_id,
                "title": summary.section_title,
                "key_message": "核心观点一。",
                "bullet_points": [
                    "核心观点二。行业空间持续扩大。",
                    "投资建议。公司盈利有望改善。",
                    "风险提示。市场需求可能波动。",
                ],
                "source_refs": ["src_report"],
                "evidence_refs": [
                    {"kind": "block", "id": block_id}
                    for block_id in summary.block_ids
                ],
                "visual_candidates": [],
            },
        ]
    }


def test_detects_marked_highlights_before_contents(tmp_path):
    snapshot = _snapshot(tmp_path)

    summary = detect_front_matter_summary(snapshot)

    assert summary is not None
    assert summary.section_id == snapshot.section_order[0]
    assert summary.toc_section_id == snapshot.section_order[1]
    assert len(summary.block_ids) == 4
    assert all(text.startswith("➢") for text in summary.item_texts)
    payload = summary.prompt_payload()
    assert payload["required"] is True
    assert payload["page_role"] == "content"
    assert payload["slide_type"] == "summary"
    assert [item["text"] for item in payload["items"]] == [
        "核心观点一。",
        "核心观点二。",
        "投资建议。公司盈利有望改善。",
        "风险提示。市场需求可能波动。",
    ]
    assert payload["display_constraint"]["max_total_body_chars"] == 480


def test_does_not_treat_cover_metadata_as_summary(tmp_path):
    assert detect_front_matter_summary(
        _snapshot(tmp_path, with_highlights=False)
    ) is None


def test_planning_payload_makes_front_summary_mandatory(tmp_path):
    snapshot = _snapshot(tmp_path)

    messages = build_slide_planning_messages(
        snapshot,
        [],
        {"type": "object"},
        {"examples": []},
        "system",
    )
    payload = json.loads(messages[1]["content"])

    assert payload["front_matter_summary"]["required"] is True
    assert payload["constraints"]["preserve_front_matter_summary"] is True
    assert "目录前摘要强制保留" in messages[0]["content"]
    assert "closing 页面不能替代摘要页" in messages[0]["content"]


def test_valid_front_summary_slide_covers_all_highlights(tmp_path):
    snapshot = _snapshot(tmp_path)

    assert validate_outline_evidence(
        _valid_summary_outline(snapshot), snapshot
    ) == []


def test_compacts_front_summary_without_dropping_evidence(tmp_path):
    snapshot = _snapshot(tmp_path)
    outline = _valid_summary_outline(snapshot)
    summary_slide = outline["slides"][1]
    original_refs = list(summary_slide["evidence_refs"])
    summary_slide["key_message"] = "模型生成的冗长摘要" * 20
    summary_slide["bullet_points"] = ["模型复制的原始长段落" * 100] * 3

    assert compact_front_matter_summary_slides(outline, snapshot) == 1
    body_chars = len(summary_slide["key_message"]) + sum(
        len(value) for value in summary_slide["bullet_points"]
    )
    assert body_chars <= 480
    assert summary_slide["evidence_refs"] == original_refs
    assert validate_outline_evidence(outline, snapshot) == []


def test_investment_summary_prefers_forecast_and_rating_sentence():
    text = (
        "➢ 投资建议：公司在多个新兴领域持续布局，长期成长空间广阔。"
        "预计公司2025-2027年归母净利润持续增长，维持“推荐”评级。"
    )

    assert summarize_front_matter_item(text) == (
        "投资建议：预计公司2025-2027年归母净利润持续增长，"
        "维持“推荐”评级。"
    )


def test_missing_front_summary_slide_is_rejected(tmp_path):
    snapshot = _snapshot(tmp_path)

    issues = validate_outline_evidence(
        {"slides": [{"page_role": "title"}]}, snapshot
    )

    assert any(
        issue.code == "BUNDLE.FRONT_SUMMARY_MISSING" for issue in issues
    )


def test_partial_front_summary_evidence_is_rejected(tmp_path):
    snapshot = _snapshot(tmp_path)
    outline = _valid_summary_outline(snapshot)
    outline["slides"][1]["evidence_refs"] = outline["slides"][1][
        "evidence_refs"
    ][:2]

    issues = validate_outline_evidence(outline, snapshot)

    missing = [
        issue
        for issue in issues
        if issue.code == "BUNDLE.FRONT_SUMMARY_EVIDENCE_MISSING"
    ]
    assert len(missing) == 2


def test_front_summary_must_precede_other_non_title_slides(tmp_path):
    snapshot = _snapshot(tmp_path)
    outline = _valid_summary_outline(snapshot)
    outline["slides"].insert(1, {"page_role": "section"})

    issues = validate_outline_evidence(outline, snapshot)

    assert any(
        issue.code == "BUNDLE.FRONT_SUMMARY_ORDER" for issue in issues
    )

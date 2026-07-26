from __future__ import annotations

from pathlib import Path

from document_intelligence import build_snapshot
from visualization_generator.candidate_detection import (
    locate_corpus_candidates,
    locate_visual_candidates,
)
from visualization_generator.contracts import CandidateTriggerCode
from visualization_generator.generate_visualizations import generate_visualizations
from visualization_generator.planning import build_candidate_report, plan_visualizations


def _block(identity: str, section_id: str, text: str, order: int) -> dict:
    return {
        "id": identity,
        "page": 1,
        "type": "paragraph",
        "text_raw": text,
        "bbox": None,
        "parser_order": order,
        "reading_order": order,
        "section_id": section_id,
        "source_type": "test",
    }


def _table(
    identity: str,
    section_id: str,
    *,
    columns: list[str],
    rows: list[list[str]],
    status: str = "complete",
) -> dict:
    return {
        "id": identity,
        "section_id": section_id,
        "caption_block_ids": [],
        "footnote_block_ids": [],
        "fragments": [],
        "structure_raw": {"format": "grid", "columns": columns, "rows": rows},
        "status": status,
        "issues": [],
        "continuation_block_ids": [],
        "source_block_id": None,
    }


def _snapshot(
    tmp_path: Path,
    blocks: list[dict],
    tables: list[dict] | None = None,
):
    tables = tables or []
    section_ids = list(
        dict.fromkeys(
            [
                *(str(block["section_id"]) for block in blocks),
                *(str(table["section_id"]) for table in tables),
            ]
        )
    )
    sections = []
    for section_id in section_ids:
        content_ids = [
            str(block["id"])
            for block in blocks
            if str(block["section_id"]) == section_id
        ]
        sections.append(
            {
                "id": section_id,
                "level": 1,
                "title_block_id": content_ids[0] if content_ids else None,
                "parent_id": None,
                "child_section_ids": [],
                "content_block_ids": content_ids,
            }
        )
    document = {
        "document": {
            "id": "report",
            "title": "Report",
            "page_count": 1,
            "source_sha256": "0" * 64,
            "source_file": "report.pdf",
            "source_format": "pdf",
        },
        "pages": [
            {
                "id": "p001",
                "page": 1,
                "width": 100,
                "height": 100,
                "block_ids": [str(block["id"]) for block in blocks],
            }
        ],
        "blocks": blocks,
        "sections": sections,
        "tables": tables,
        "figures": [],
        "reading_order": [str(block["id"]) for block in blocks],
    }
    return build_snapshot(document, tmp_path)


def _slide(
    *,
    evidence_refs: list[dict] | None = None,
    section_ref: str | None = None,
    visual_candidates: list[dict] | None = None,
) -> dict:
    result = {
        "slide_id": "slide_006",
        "page_role": "content",
        "slide_type": "industry_analysis",
        "title": "经营指标分析",
        "key_message": "经营指标保持增长",
        "source_refs": ["src_report"],
        "evidence_refs": evidence_refs or [],
        "visual_candidates": visual_candidates or [],
    }
    if section_ref is not None:
        result["section_ref"] = section_ref
    return result


def test_locates_a_stable_time_series_candidate_from_direct_block_evidence(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        [
            _block(
                "p001-b001",
                "sec-1",
                "2021年营业收入10亿元，2022年营业收入15亿元，2023年营业收入22亿元，2024年营业收入28亿元。",
                0,
            )
        ],
    )
    slide = _slide(evidence_refs=[{"kind": "block", "id": "p001-b001"}])

    first = locate_visual_candidates(slide, snapshot)
    second = locate_visual_candidates(slide, snapshot)

    assert first == second
    assert len(first) == 1
    candidate = first[0]
    assert candidate.candidate_id.startswith("cand_")
    assert candidate.chart_intent == "trend"
    assert candidate.evidence_refs == (("block", "p001-b001"),)
    assert CandidateTriggerCode.TIME_SERIES in candidate.trigger_ids
    assert CandidateTriggerCode.COMPARABLE_NUMBERS in candidate.trigger_ids


def test_locates_a_composition_only_when_percentages_share_a_total(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        [
            _block(
                "p001-b001",
                "sec-1",
                "2024年业务收入构成：专网占比45%、公网占比32%、智能制造占比23%。",
                0,
            )
        ],
    )

    candidates = locate_visual_candidates(
        _slide(evidence_refs=[{"kind": "block", "id": "p001-b001"}]),
        snapshot,
    )

    assert len(candidates) == 1
    assert candidates[0].chart_intent == "composition"
    assert CandidateTriggerCode.COMPOSITION in candidates[0].trigger_ids


def test_rejects_single_number_and_mixed_unit_blocks(tmp_path):
    single_snapshot = _snapshot(
        tmp_path / "single",
        [_block("p001-b001", "sec-1", "2024年营业收入为10亿元。", 0)],
    )
    mixed_snapshot = _snapshot(
        tmp_path / "mixed",
        [
            _block(
                "p001-b001",
                "sec-1",
                "2024年营业收入为10亿元，毛利率为20%。",
                0,
            )
        ],
    )
    slide = _slide(evidence_refs=[{"kind": "block", "id": "p001-b001"}])

    assert locate_visual_candidates(slide, single_snapshot) == []
    assert locate_visual_candidates(slide, mixed_snapshot) == []


def test_complete_table_with_labels_and_numeric_column_becomes_comparison_candidate(
    tmp_path,
):
    snapshot = _snapshot(
        tmp_path,
        [_block("p001-b001", "sec-1", "业务收入对比", 0)],
        [
            _table(
                "table-001",
                "sec-1",
                columns=["业务", "收入（亿元）"],
                rows=[["专网", "22.42"], ["公网", "15.81"], ["智能制造", "11.49"]],
            )
        ],
    )

    candidates = locate_visual_candidates(
        _slide(evidence_refs=[{"kind": "table", "id": "table-001"}]),
        snapshot,
    )

    assert len(candidates) == 1
    assert candidates[0].visual_type == "chart"
    assert candidates[0].chart_intent == "comparison"
    assert CandidateTriggerCode.COMPLETE_TABLE in candidates[0].trigger_ids


def test_complete_table_with_one_series_across_period_columns_becomes_trend(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        [_block("p001-b001", "sec-1", "营业收入趋势", 0)],
        [
            _table(
                "table-001",
                "sec-1",
                columns=["项目", "2021A", "2022A", "2023A", "2024A"],
                rows=[["营业收入", "10", "15", "22", "28"]],
            )
        ],
    )

    candidates = locate_visual_candidates(
        _slide(evidence_refs=[{"kind": "table", "id": "table-001"}]),
        snapshot,
    )

    assert len(candidates) == 1
    assert candidates[0].visual_type == "chart"
    assert candidates[0].chart_intent == "trend"


def test_table_with_different_column_units_downgrades_to_table(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        [_block("p001-b001", "sec-1", "业务指标", 0)],
        [
            _table(
                "table-001",
                "sec-1",
                columns=["业务", "收入", "毛利率"],
                rows=[["专网", "22.42亿元", "18.6%"], ["公网", "15.81亿元", "10.6%"]],
            )
        ],
    )

    candidates = locate_visual_candidates(
        _slide(evidence_refs=[{"kind": "table", "id": "table-001"}]),
        snapshot,
    )

    assert len(candidates) == 1
    assert candidates[0].visual_type == "table"
    assert candidates[0].chart_intent is None


def test_incomplete_table_is_not_a_candidate(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        [_block("p001-b001", "sec-1", "业务收入对比", 0)],
        [
            _table(
                "table-001",
                "sec-1",
                columns=["业务", "收入"],
                rows=[["专网", "22.42"], ["公网", "15.81"]],
                status="partial",
            )
        ],
    )

    assert locate_visual_candidates(
        _slide(evidence_refs=[{"kind": "table", "id": "table-001"}]),
        snapshot,
    ) == []


def test_expands_only_to_bounded_same_section_context(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        [
            _block("p001-b001", "sec-1", "本节讨论业务变化。", 0),
            _block(
                "p001-b002",
                "sec-1",
                "2021年营收10亿元，2022年营收15亿元，2023年营收22亿元，2024年营收28亿元。",
                1,
            ),
            _block(
                "p001-b003",
                "sec-2",
                "2021年利润1亿元，2022年利润2亿元，2023年利润3亿元。",
                2,
            ),
        ],
    )

    candidates = locate_visual_candidates(
        _slide(evidence_refs=[{"kind": "block", "id": "p001-b001"}]),
        snapshot,
    )

    assert {candidate.evidence_refs for candidate in candidates} == {
        (("block", "p001-b002"),)
    }


def test_does_not_search_the_document_without_slide_scope(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        [
            _block(
                "p001-b001",
                "sec-1",
                "2021年营收10亿元，2022年营收15亿元，2023年营收22亿元。",
                0,
            )
        ],
    )

    assert locate_visual_candidates(_slide(), snapshot) == []
    assert len(locate_corpus_candidates(snapshot)) == 1
    assert locate_corpus_candidates(snapshot)[0].slide_id is None


def test_planning_adds_active_candidate_when_outline_has_no_suggestion(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        [
            _block(
                "p001-b001",
                "sec-1",
                "2021年营收10亿元，2022年营收15亿元，2023年营收22亿元，2024年营收28亿元。",
                0,
            )
        ],
    )
    slide = _slide(evidence_refs=[{"kind": "block", "id": "p001-b001"}])

    plans = plan_visualizations({"slides": [slide]}, snapshot)

    assert len(plans) == 1
    assert plans[0].visualization_id.startswith("cand_")
    assert plans[0].chart_intent == "trend"
    assert plans[0].evidence_refs == (("block", "p001-b001"),)

    artifacts, issues = generate_visualizations({"slides": [slide]}, snapshot)
    assert issues == []
    assert artifacts[0].data["chart_type"] == "line"
    assert artifacts[0].data["sources"] == [{"kind": "block", "id": "p001-b001"}]


def test_shadow_mode_records_candidate_without_adding_visual_plan(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        [
            _block(
                "p001-b001",
                "sec-1",
                "2021年营收10亿元，2022年营收15亿元，2023年营收22亿元，2024年营收28亿元。",
                0,
            )
        ],
    )
    slide = _slide(evidence_refs=[{"kind": "block", "id": "p001-b001"}])
    outline = {"slides": [slide]}

    assert plan_visualizations(outline, snapshot, candidate_mode="shadow") == []
    report = build_candidate_report(outline, snapshot, candidate_mode="shadow")

    assert report["candidate_count"] == 1
    assert report["selected_count"] == 0
    assert report["candidates"][0]["selected"] is False
    assert report["candidates"][0]["decision_reason"] == "candidate_locator_shadow_only"


def test_explicit_outline_suggestion_wins_for_the_same_evidence(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        [
            _block(
                "p001-b001",
                "sec-1",
                "2021年营收10亿元，2022年营收15亿元，2023年营收22亿元。",
                0,
            )
        ],
    )
    slide = _slide(
        evidence_refs=[{"kind": "block", "id": "p001-b001"}],
        visual_candidates=[
            {
                "candidate_id": "visual_001",
                "type": "chart",
                "description": "营业收入增长趋势",
                "source_refs": ["src_report"],
            }
        ],
    )

    plans = plan_visualizations({"slides": [slide]}, snapshot)

    assert len(plans) == 1
    assert plans[0].visualization_id == "visual_001"
    assert plans[0].chart_intent == "trend"

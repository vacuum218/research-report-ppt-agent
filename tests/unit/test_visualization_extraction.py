from __future__ import annotations

from pathlib import Path

import pytest

from document_intelligence import build_snapshot
from visualization_generator.contracts import ExtractionProposal, ProposedSeries
from visualization_generator.extraction import (
    map_extraction_proposal,
    proposal_from_block,
    proposal_from_table,
)
from visualization_generator.generate_visualizations import generate_visualizations
from visualization_generator.numeric_facts import build_numeric_fact_ledger
from visualization_generator.planning import VisualizationPlan


def _snapshot(tmp_path: Path):
    blocks = [
        {
            "id": "p001-b001",
            "page": 1,
            "type": "paragraph",
            "text_raw": "2021年营业收入10亿元，2022年营业收入15亿元，2023年营业收入22亿元。",
            "bbox": None,
            "parser_order": 0,
            "reading_order": 0,
            "section_id": "sec-1",
            "source_type": "test",
        },
        {
            "id": "p001-b002",
            "page": 1,
            "type": "paragraph",
            "text_raw": "营业收入10亿元，营业收入15亿元，营业收入22亿元。",
            "bbox": None,
            "parser_order": 1,
            "reading_order": 1,
            "section_id": "sec-1",
            "source_type": "test",
        },
        {
            "id": "p001-b003",
            "page": 1,
            "type": "paragraph",
            "text_raw": "业务收入构成：专网占比45%、公网占比32%、智能制造占比23%。",
            "bbox": None,
            "parser_order": 2,
            "reading_order": 2,
            "section_id": "sec-1",
            "source_type": "test",
        },
    ]
    table = {
        "id": "table-001",
        "section_id": "sec-1",
        "caption_block_ids": [],
        "footnote_block_ids": [],
        "fragments": [],
        "structure_raw": {
            "format": "grid",
            "columns": ["项目", "2021A（亿元）", "2022A（亿元）", "2023A（亿元）"],
            "rows": [["营业收入", "10", "15", "22"], ["净利润", "1", "2", "3"]],
        },
        "status": "complete",
        "issues": [],
        "continuation_block_ids": [],
        "source_block_id": None,
    }
    composition_table = {
        **table,
        "id": "table-002",
        "structure_raw": {
            "format": "grid",
            "columns": ["业务", "收入（亿元）", "占比"],
            "rows": [
                ["专网", "10", "40%"],
                ["公网", "15", "60%"],
                ["**合计**", "**25**", "**100%**"],
            ],
        },
    }
    mixed_period_table = {
        **table,
        "id": "table-003",
        "structure_raw": {
            "format": "grid",
            "columns": [
                "业务",
                "2022收入（亿元）",
                "占比",
                "2023收入（亿元）",
                "占比",
                "毛利率（2023）",
            ],
            "rows": [
                ["专网", "10", "40%", "12", "42%", "18%"],
                ["公网", "15", "60%", "16", "58%", "11%"],
            ],
        },
    }
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
                "block_ids": [block["id"] for block in blocks],
            }
        ],
        "blocks": blocks,
        "sections": [
            {
                "id": "sec-1",
                "level": 1,
                "title_block_id": "p001-b001",
                "parent_id": None,
                "child_section_ids": [],
                "content_block_ids": [block["id"] for block in blocks],
            }
        ],
        "tables": [table, composition_table, mixed_period_table],
        "figures": [],
        "reading_order": [block["id"] for block in blocks],
    }
    return build_snapshot(document, tmp_path)


def _plan(kind: str, identity: str, *, intent: str = "trend") -> VisualizationPlan:
    return VisualizationPlan(
        slide_id="slide_006",
        visualization_id="cand_001",
        visual_type="chart",
        purpose="营业收入趋势",
        chart_intent=intent,
        data_requirement={},
        evidence_refs=((kind, identity),),
        source_refs=("src_report",),
    )


def test_rule_mapper_builds_block_proposal_with_fact_ids_only(tmp_path):
    snapshot = _snapshot(tmp_path)
    ledger = build_numeric_fact_ledger(snapshot)

    proposal = proposal_from_block(
        _plan("block", "p001-b001"),
        snapshot.blocks_by_id["p001-b001"],
        ledger,
    )

    assert proposal is not None
    assert proposal.chart_type == "column"
    assert proposal.category_labels == ("2021", "2022", "2023")
    assert all(
        fact_id.startswith("fact_")
        for series in proposal.series
        for fact_id in series.fact_ids
    )


def test_rule_mapper_builds_table_series_from_fact_coordinates(tmp_path):
    snapshot = _snapshot(tmp_path)
    ledger = build_numeric_fact_ledger(snapshot)

    proposal = proposal_from_table(
        _plan("table", "table-001"),
        snapshot.tables_by_id["table-001"],
        ledger,
    )

    assert proposal is not None
    assert proposal.category_labels == ("2021A", "2022A", "2023A")
    # Phase 1 never combines different metrics into one chart.
    assert [series.name for series in proposal.series] == ["营业收入"]
    assert all(len(series.fact_ids) == 3 for series in proposal.series)


def test_rule_mapper_builds_fact_only_composition_proposal(tmp_path):
    snapshot = _snapshot(tmp_path)
    ledger = build_numeric_fact_ledger(snapshot)
    plan = _plan("block", "p001-b003", intent="composition")

    proposal = proposal_from_block(
        plan,
        snapshot.blocks_by_id["p001-b003"],
        ledger,
    )

    assert proposal is not None
    assert proposal.chart_type == "pie"
    assert proposal.category_labels == ("专网", "公网", "智能制造")
    assert proposal.unit == "%"


def test_table_composition_rejects_only_two_categories(tmp_path):
    snapshot = _snapshot(tmp_path)
    ledger = build_numeric_fact_ledger(snapshot)
    plan = _plan("table", "table-002", intent="composition")

    proposal = proposal_from_table(
        plan,
        snapshot.tables_by_id["table-002"],
        ledger,
    )

    assert proposal is None


def test_short_table_trend_uses_column_instead_of_line(tmp_path):
    snapshot = _snapshot(tmp_path)
    ledger = build_numeric_fact_ledger(snapshot)
    plan = _plan("table", "table-003", intent="trend")

    proposal = proposal_from_table(
        plan,
        snapshot.tables_by_id["table-003"],
        ledger,
    )

    assert proposal is not None
    assert proposal.chart_type == "column"
    assert proposal.category_labels == ("2022", "2023")
    assert proposal.unit == "亿元"
    assert [series.name for series in proposal.series] == ["专网", "公网"]


def test_optional_adapter_receives_facts_only_after_rule_mapping_declines(tmp_path):
    snapshot = _snapshot(tmp_path)
    ledger = build_numeric_fact_ledger(snapshot)
    plan = _plan("block", "p001-b002", intent="comparison")
    facts = ledger.for_source("block", "p001-b002")

    class Adapter:
        called = False

        def propose(self, received_plan, received_facts):
            self.called = True
            assert received_plan.visualization_id == plan.visualization_id
            assert received_plan.evidence_refs == plan.evidence_refs
            assert received_facts == facts
            return ExtractionProposal(
                candidate_id=plan.visualization_id,
                chart_type="column",
                title=received_plan.purpose,
                unit="亿元",
                category_labels=("A", "B", "C"),
                series=(
                    ProposedSeries(
                        name="营业收入",
                        fact_ids=tuple(fact.fact_id for fact in received_facts),
                    ),
                ),
            )

    adapter = Adapter()
    proposal = map_extraction_proposal(
        plan,
        snapshot,
        ledger,
        llm_adapter=adapter,
    )

    assert adapter.called is True
    assert proposal is not None
    assert proposal.series[0].fact_ids == tuple(fact.fact_id for fact in facts)

    outline = {
        "slides": [
            {
                "slide_id": plan.slide_id,
                "page_role": "content",
                "slide_type": "industry_analysis",
                "title": "收入比较",
                "key_message": "收入比较",
                "source_refs": ["src_report"],
                "evidence_refs": [{"kind": "block", "id": "p001-b002"}],
                "visual_candidates": [
                    {
                        "candidate_id": plan.visualization_id,
                        "type": "chart",
                        "description": "收入比较",
                        "chart_intent": "comparison",
                        "source_refs": ["src_report"],
                    }
                ],
            }
        ]
    }
    artifacts, issues = generate_visualizations(
        outline,
        snapshot,
        llm_adapter=adapter,
    )
    assert issues == []
    assert artifacts[0].data["series"][0]["values"] == [10, 15, 22]
    assert artifacts[0].data["sources"] == [{"kind": "block", "id": "p001-b002"}]


def test_adapter_cannot_return_a_proposal_for_another_candidate(tmp_path):
    snapshot = _snapshot(tmp_path)
    ledger = build_numeric_fact_ledger(snapshot)
    plan = _plan("block", "p001-b002", intent="comparison")
    facts = ledger.for_source("block", "p001-b002")

    class Adapter:
        def propose(self, received_plan, received_facts):
            return ExtractionProposal(
                candidate_id="cand_other",
                chart_type="column",
                title="Invalid",
                unit="亿元",
                category_labels=("A", "B", "C"),
                series=(
                    ProposedSeries(
                        name="营业收入",
                        fact_ids=tuple(fact.fact_id for fact in facts),
                    ),
                ),
            )

    with pytest.raises(ValueError, match="candidate_id"):
        map_extraction_proposal(plan, snapshot, ledger, llm_adapter=Adapter())

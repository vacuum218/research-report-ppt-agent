from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_intelligence import build_snapshot
from visualization_generator.contracts import ExtractionProposal, ProposedSeries
from visualization_generator.extraction import proposal_from_block
from visualization_generator.numeric_facts import build_numeric_fact_ledger
from visualization_generator.planning import VisualizationPlan
from visualization_generator.verification import (
    VisualizationVerificationError,
    assemble_verified_chart,
    assemble_verified_table,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _snapshot(tmp_path: Path):
    blocks = [
        {
            "id": "p001-b001",
            "page": 1,
            "type": "paragraph",
            "text_raw": "2021年营业收入10亿元，2022年营业收入15亿元。",
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
            "text_raw": "营业收入10亿元，毛利率20%。",
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
            "text_raw": "业务构成：专网占比40%、公网占比30%、智能制造占比20%。",
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
            "columns": ["项目", "2022A（亿元）", "2023A（亿元）"],
            "rows": [["营业收入", "10", "15"], ["净利润", "1.2", "2.5"]],
        },
        "status": "complete",
        "issues": [],
        "continuation_block_ids": [],
        "source_block_id": None,
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
        "tables": [table],
        "figures": [],
        "reading_order": [block["id"] for block in blocks],
    }
    return build_snapshot(document, tmp_path)


def _plan(kind: str, identity: str) -> VisualizationPlan:
    return VisualizationPlan(
        slide_id="slide_006",
        visualization_id="cand_001",
        visual_type="chart" if kind == "block" else "table",
        purpose="营业收入趋势",
        chart_intent="trend" if kind == "block" else None,
        data_requirement={},
        evidence_refs=((kind, identity),),
        source_refs=("src_report",),
    )


def _schema():
    return json.loads(
        (PROJECT_ROOT / "schemas/visualization.schema.json").read_text(encoding="utf-8")
    )


def test_verifier_resolves_fact_ids_and_preserves_native_sources(tmp_path):
    snapshot = _snapshot(tmp_path)
    ledger = build_numeric_fact_ledger(snapshot)
    plan = _plan("block", "p001-b001")
    proposal = proposal_from_block(plan, snapshot.blocks_by_id["p001-b001"], ledger)
    assert proposal is not None

    data = assemble_verified_chart(plan, proposal, ledger, _schema())

    assert data["series"][0]["values"] == [10, 15]
    assert data["sources"] == [{"kind": "block", "id": "p001-b001"}]
    assert data["unit"] == "亿元"


def test_verifier_rejects_unknown_fact_id(tmp_path):
    snapshot = _snapshot(tmp_path)
    ledger = build_numeric_fact_ledger(snapshot)
    plan = _plan("block", "p001-b001")
    proposal = ExtractionProposal(
        candidate_id=plan.visualization_id,
        chart_type="line",
        title="营业收入趋势",
        unit="亿元",
        category_labels=("2021", "2022"),
        series=(
            ProposedSeries(
                name="营业收入",
                fact_ids=("fact_unknown_1", "fact_unknown_2"),
            ),
        ),
    )

    with pytest.raises(VisualizationVerificationError, match="unknown fact_id"):
        assemble_verified_chart(plan, proposal, ledger, _schema())


def test_verifier_rejects_mixed_fact_units(tmp_path):
    snapshot = _snapshot(tmp_path)
    ledger = build_numeric_fact_ledger(snapshot)
    plan = _plan("block", "p001-b002")
    facts = ledger.for_source("block", "p001-b002")
    proposal = ExtractionProposal(
        candidate_id=plan.visualization_id,
        chart_type="column",
        title="错误混合指标",
        unit="亿元",
        category_labels=("收入", "毛利率"),
        series=(
            ProposedSeries(
                name="混合指标",
                fact_ids=tuple(fact.fact_id for fact in facts),
            ),
        ),
    )

    with pytest.raises(VisualizationVerificationError, match="conflicting fact units"):
        assemble_verified_chart(plan, proposal, ledger, _schema())


def test_verifier_rejects_fact_outside_candidate_evidence(tmp_path):
    snapshot = _snapshot(tmp_path)
    ledger = build_numeric_fact_ledger(snapshot)
    plan = _plan("block", "p001-b001")
    outside_facts = ledger.for_source("block", "p001-b002")
    proposal = ExtractionProposal(
        candidate_id=plan.visualization_id,
        chart_type="column",
        title="越界数据",
        unit="",
        category_labels=("A", "B"),
        series=(
            ProposedSeries(
                name="Value",
                fact_ids=tuple(fact.fact_id for fact in outside_facts),
            ),
        ),
    )

    with pytest.raises(VisualizationVerificationError, match="outside"):
        assemble_verified_chart(plan, proposal, ledger, _schema())


def test_verifier_rejects_pie_values_that_do_not_share_a_100_percent_total(tmp_path):
    snapshot = _snapshot(tmp_path)
    ledger = build_numeric_fact_ledger(snapshot)
    plan = _plan("block", "p001-b003")
    facts = ledger.for_source("block", "p001-b003")
    proposal = ExtractionProposal(
        candidate_id=plan.visualization_id,
        chart_type="pie",
        title="业务构成",
        unit="%",
        category_labels=("专网", "公网", "智能制造"),
        series=(
            ProposedSeries(
                name="收入占比",
                fact_ids=tuple(fact.fact_id for fact in facts),
            ),
        ),
    )

    with pytest.raises(VisualizationVerificationError, match="approximately 100"):
        assemble_verified_chart(plan, proposal, ledger, _schema())


def test_verified_table_requires_a_fact_for_every_numeric_cell(tmp_path):
    snapshot = _snapshot(tmp_path)
    full_ledger = build_numeric_fact_ledger(snapshot)
    plan = _plan("table", "table-001")

    data = assemble_verified_table(
        plan,
        snapshot.tables_by_id["table-001"],
        full_ledger,
        _schema(),
    )
    assert data["rows"] == [["营业收入", 10, 15], ["净利润", 1.2, 2.5]]
    assert data["sources"] == [{"kind": "table", "id": "table-001"}]

    block_only_ledger = build_numeric_fact_ledger(
        snapshot,
        evidence_refs=(("block", "p001-b001"),),
    )
    with pytest.raises(VisualizationVerificationError, match="has no fact"):
        assemble_verified_table(
            plan,
            snapshot.tables_by_id["table-001"],
            block_only_ledger,
            _schema(),
        )

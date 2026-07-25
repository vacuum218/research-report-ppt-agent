from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from decimal import Decimal

import pytest

from visualization_generator.contracts import (
    CandidateRejectionCode,
    CandidateTriggerCode,
    ExtractionProposal,
    NumericFact,
    ProposedSeries,
    VisualCandidate,
)


def test_visual_candidate_is_frozen_data_free_and_uses_reason_codes():
    candidate = VisualCandidate(
        candidate_id="cand_001",
        slide_id="slide_006",
        visual_type="chart",
        chart_intent="trend",
        evidence_refs=(("block", "p001-b001"),),
        trigger_ids=(
            CandidateTriggerCode.COMPARABLE_NUMBERS,
            CandidateTriggerCode.TIME_SERIES,
        ),
        score=0.9,
        excerpt="2022年收入10亿元，2023年收入15亿元。",
    )

    assert {"values", "categories", "series", "rows", "columns"}.isdisjoint(
        field.name for field in fields(candidate)
    )
    with pytest.raises(FrozenInstanceError):
        candidate.score = 0.1


def test_visual_candidate_rejects_unknown_reason_code():
    with pytest.raises(ValueError, match="reason codes"):
        VisualCandidate(
            candidate_id="cand_001",
            slide_id=None,
            visual_type="chart",
            chart_intent="trend",
            evidence_refs=(("block", "p001-b001"),),
            trigger_ids=("sample_specific_rule",),
            score=0.9,
            excerpt="evidence",
        )


def test_block_numeric_fact_requires_an_exact_character_span():
    fact = NumericFact(
        fact_id="fact_block_001",
        source_kind="block",
        source_id="p001-b001",
        raw_value="15",
        normalized_value=Decimal("15"),
        unit="亿元",
        label="营业收入",
        period="2023",
        start=18,
        end=20,
    )

    assert fact.start == 18
    with pytest.raises(ValueError, match="start/end"):
        NumericFact(
            fact_id="fact_block_002",
            source_kind="block",
            source_id="p001-b001",
            raw_value="15",
            normalized_value=Decimal("15"),
            unit="亿元",
            label="营业收入",
            period="2023",
            start=None,
            end=None,
        )


def test_table_numeric_fact_requires_an_exact_cell_coordinate():
    fact = NumericFact(
        fact_id="fact_table_001",
        source_kind="table",
        source_id="table-001",
        raw_value="15",
        normalized_value=Decimal("15"),
        unit="亿元",
        label="营业收入",
        period="2023",
        start=None,
        end=None,
        row_index=1,
        column_index=2,
    )

    assert (fact.row_index, fact.column_index) == (1, 2)
    with pytest.raises(ValueError, match="row/column"):
        NumericFact(
            fact_id="fact_table_002",
            source_kind="table",
            source_id="table-001",
            raw_value="15",
            normalized_value=Decimal("15"),
            unit="亿元",
            label="营业收入",
            period="2023",
            start=None,
            end=None,
        )


def test_extraction_proposal_contains_fact_ids_instead_of_values():
    proposal = ExtractionProposal(
        candidate_id="cand_001",
        chart_type="line",
        title="营业收入趋势",
        unit="亿元",
        category_labels=("2022", "2023"),
        series=(
            ProposedSeries(
                name="营业收入",
                fact_ids=("fact_block_001", "fact_block_002"),
            ),
        ),
    )

    assert {"values", "rows", "columns"}.isdisjoint(
        field.name for field in fields(proposal)
    )
    assert proposal.series[0].fact_ids == ("fact_block_001", "fact_block_002")


def test_extraction_proposal_rejects_literal_values_and_length_mismatch():
    with pytest.raises(ValueError, match="fact_id"):
        ProposedSeries(name="营业收入", fact_ids=("15", "20"))

    with pytest.raises(ValueError, match="one fact_id"):
        ExtractionProposal(
            candidate_id="cand_001",
            chart_type="line",
            title="营业收入趋势",
            unit="亿元",
            category_labels=("2022", "2023"),
            series=(ProposedSeries(name="营业收入", fact_ids=("fact_block_001",)),),
        )


def test_reason_code_catalog_matches_the_frozen_t3_0_policy():
    assert {code.value for code in CandidateTriggerCode} == {
        "candidate.outline_suggestion",
        "candidate.complete_table",
        "candidate.comparable_numbers",
        "candidate.time_series",
        "candidate.category_comparison",
        "candidate.composition",
        "candidate.metric_keyword",
        "candidate.labels_colocated",
    }
    assert {code.value for code in CandidateRejectionCode} == {
        "reject.single_number",
        "reject.administrative_numbers_only",
        "reject.single_point_signal",
        "reject.mixed_metric_or_unit",
        "reject.incomplete_table",
        "reject.non_composition_percentages",
        "reject.missing_label",
        "reject.out_of_scope",
    }

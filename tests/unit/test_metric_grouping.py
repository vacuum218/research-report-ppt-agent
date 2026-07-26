from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from visualization_generator.contracts import ExtractionProposal, NumericFact, ProposedSeries
from visualization_generator.metric_grouping import MetricGroupError, build_metric_group
from visualization_generator.numeric_facts import _ledger
from visualization_generator.planning import VisualizationPlan


def _fact(identity: int, **changes) -> NumericFact:
    base = NumericFact(
        fact_id=f"fact_{identity:04x}",
        source_kind="table",
        source_id="table-001",
        raw_value=str(identity),
        normalized_value=Decimal(identity),
        unit="亿元",
        label="营业收入",
        period="2023A",
        start=None,
        end=None,
        row_index=0,
        column_index=identity,
        entity_id="company-1",
        entity_name="测试公司",
        metric_key="revenue",
        metric_label="营业收入",
        measure_kind="amount",
        unit_family="currency",
        unit_scale="100000000",
        currency="CNY",
        scope="consolidated",
        scenario="actual",
    )
    return replace(base, **changes)


def _plan(intent: str = "trend") -> VisualizationPlan:
    return VisualizationPlan(
        slide_id="slide_001",
        visualization_id="visual_001",
        visual_type="chart",
        purpose="营业收入趋势",
        chart_intent=intent,
        data_requirement={},
        evidence_refs=(("table", "table-001"),),
        source_refs=("src-1",),
    )


def _proposal(*facts: NumericFact, chart_type: str = "line") -> ExtractionProposal:
    return ExtractionProposal(
        candidate_id="visual_001",
        chart_type=chart_type,
        title="营业收入趋势",
        unit=facts[0].unit,
        category_labels=tuple(fact.period or fact.label or "" for fact in facts),
        series=(ProposedSeries("测试公司", tuple(fact.fact_id for fact in facts)),),
    )


def test_trend_accepts_one_historical_to_forecast_boundary():
    facts = (
        _fact(1, period="2023A"),
        _fact(2, period="2024A"),
        _fact(3, period="2025E", scenario="estimate"),
        _fact(4, period="2026E", scenario="estimate"),
    )

    group = build_metric_group(_plan(), _proposal(*facts), _ledger(facts))

    assert group.metric_key == "revenue"
    assert group.measure_kind == "amount"
    assert group.forecast_start_index == 2


def test_group_can_infer_one_unambiguous_metric_from_candidate_purpose():
    facts = (
        _fact(1, metric_key="unknown", metric_label="", label="家电"),
        _fact(2, period="2024A", metric_key="unknown", metric_label="", label="家电"),
    )

    group = build_metric_group(_plan(), _proposal(*facts), _ledger(facts))

    assert group.metric_key == "revenue"


def test_group_does_not_guess_from_a_multi_metric_purpose():
    facts = (
        _fact(1, metric_key="unknown", metric_label="", label="家电"),
        _fact(2, period="2024A", metric_key="unknown", metric_label="", label="家电"),
    )
    plan = replace(_plan(), purpose="营业收入与归母净利润趋势")

    with pytest.raises(MetricGroupError, match="reject.incomplete_metric_typing"):
        build_metric_group(plan, _proposal(*facts), _ledger(facts))


@pytest.mark.parametrize(
    ("changed", "code"),
    [
        ({"metric_key": "net_profit", "metric_label": "归母净利润"}, "reject.mixed_metric"),
        ({"measure_kind": "growth_rate", "unit_family": "percentage"}, "reject.mixed_measure_kind"),
        ({"unit": "万元", "unit_scale": "10000"}, "reject.mixed_unit_scale"),
        ({"currency": "USD"}, "reject.mixed_currency"),
    ],
)
def test_group_rejects_incompatible_metric_dimensions(changed, code):
    facts = (_fact(1), _fact(2, period="2024A", **changed))

    with pytest.raises(MetricGroupError, match=code):
        build_metric_group(_plan(), _proposal(*facts), _ledger(facts))


def test_trend_rejects_scope_mixing_inside_one_series():
    facts = (
        _fact(1, scope="segment", scope_label="家电"),
        _fact(2, period="2024A", scope="segment", scope_label="机器人"),
    )

    with pytest.raises(MetricGroupError, match="reject.mixed_scope"):
        build_metric_group(_plan(), _proposal(*facts), _ledger(facts))


def test_comparison_rejects_historical_and_forecast_scenarios():
    facts = (
        _fact(1, period="2025E", scenario="actual"),
        _fact(2, period="2025E", scenario="estimate"),
    )

    proposal = replace(
        _proposal(*facts, chart_type="bar"),
        category_labels=("公司甲", "公司乙"),
    )
    with pytest.raises(MetricGroupError, match="reject.mixed_scenario"):
        build_metric_group(
            _plan("comparison"),
            proposal,
            _ledger(facts),
        )


def test_trend_rejects_forecast_followed_by_actual():
    facts = (
        _fact(1, period="2023A"),
        _fact(2, period="2024E", scenario="estimate"),
        _fact(3, period="2025A", scenario="actual"),
    )

    with pytest.raises(MetricGroupError, match="reject.invalid_forecast_boundary"):
        build_metric_group(_plan(), _proposal(*facts), _ledger(facts))

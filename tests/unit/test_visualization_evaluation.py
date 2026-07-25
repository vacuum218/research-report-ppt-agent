from __future__ import annotations

import pytest

from tools.evaluate_visualization_extraction import evaluate, validate_gold
from tools.finalize_visualization_gold import baseline_predictions, finalize
from tools.merge_visualization_gold import select_balanced_records


def _fact(value: str, start: int) -> dict:
    return {
        "raw_value": value,
        "normalized_value": value,
        "unit": "亿元",
        "label": "营业收入",
        "period": "2023",
        "source_locator": {"start": start, "end": start + len(value)},
    }


def _expected(intent: str, fact: dict) -> dict:
    return {
        "visual_type": "chart",
        "chart_intent": intent,
        "chart_type": "line" if intent == "trend" else "column",
        "title": "营业收入",
        "unit": "亿元",
        "categories": ["2023"],
        "series": [{"name": "营业收入", "facts": [fact]}],
        "sources": [{"kind": "block", "id": "block-001"}],
    }


def _gold_record(index: int, *, positive: bool) -> dict:
    return {
        "sample_id": f"week3_{index:03d}",
        "document_id": f"report_{index % 3}",
        "source": {"kind": "block", "id": f"block-{index:03d}"},
        "review_status": "approved",
        "should_visualize": positive,
        "expected": _expected("trend", _fact("10", 5)) if positive else None,
        "rejection_code": None if positive else "reject.single_number",
    }


def test_gold_validation_requires_manual_approval_and_boolean_decisions():
    records = [_gold_record(index, positive=index < 10) for index in range(20)]
    assert validate_gold(records) == []

    records[0]["review_status"] = "pending"
    records[1]["should_visualize"] = None
    errors = validate_gold(records)

    assert any("review_status" in error for error in errors)
    assert any("should_visualize" in error for error in errors)


def test_evaluator_reports_candidate_numeric_rejection_and_engineering_metrics():
    gold = [
        _gold_record(1, positive=True),
        _gold_record(2, positive=True),
        _gold_record(3, positive=False),
    ]
    unsupported_fact = _fact("99", 8)
    unsupported_fact["source_locator"] = None
    predictions = [
        {
            **gold[0],
            "schema_valid": True,
        },
        {
            **gold[1],
            "expected": _expected("comparison", unsupported_fact),
            "schema_valid": True,
        },
        {
            **gold[2],
            "schema_valid": False,
        },
    ]

    report = evaluate(gold, predictions)

    assert report["candidate"] == {
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
    }
    assert report["numeric_cells"]["tp"] == 1
    assert report["numeric_cells"]["fp"] == 1
    assert report["numeric_cells"]["fn"] == 1
    assert report["rejection"]["correct_rejection_rate"] == 1.0
    assert report["engineering"]["schema_pass_count"] == 2
    assert report["engineering"]["fabricated_numeric_cells"] == 1


def test_gold_finalizer_applies_acceptance_and_explicit_rejection_codes():
    positive = {
        **_gold_record(1, positive=True),
        "review_status": "pending",
        "should_visualize": None,
        "expected": None,
        "suggested": {
            "should_visualize": True,
            "expected": _expected("trend", _fact("10", 5)),
            "rejection_code": None,
        },
    }
    negative = {
        **_gold_record(2, positive=False),
        "review_status": "pending",
        "should_visualize": None,
        "rejection_code": None,
        "suggested": {
            "should_visualize": False,
            "expected": None,
            "rejection_code": "reject.single_number",
        },
    }

    records = finalize(
        [positive, negative],
        {
            "week3_001": "拒绝：指标列混入其他口径",
            "week3_002": "接受",
        },
        {"week3_001": "reject.mixed_metric_or_unit"},
    )

    assert records[0]["should_visualize"] is False
    assert records[0]["rejection_code"] == "reject.mixed_metric_or_unit"
    assert records[1]["rejection_code"] == "reject.single_number"
    assert all(record["review_status"] == "approved" for record in records)
    assert all("suggested" not in record for record in records)
    assert baseline_predictions([positive, negative])[0]["schema_valid"] is True


def test_gold_finalizer_rejects_unresolved_positive_reversal():
    record = {
        **_gold_record(1, positive=True),
        "suggested": {
            "should_visualize": True,
            "expected": _expected("trend", _fact("10", 5)),
            "rejection_code": None,
        },
    }

    with pytest.raises(ValueError, match="requires --rejection-code"):
        finalize([record], {"week3_001": "拒绝"}, {})


def test_balancer_keeps_false_positives_then_expands_negative_coverage():
    records = [
        _gold_record(1, positive=True),
        _gold_record(2, positive=False),
        _gold_record(3, positive=False),
        _gold_record(4, positive=False),
    ]
    records[2]["document_id"] = "new_report"
    records[2]["rejection_code"] = "reject.mixed_metric_or_unit"
    records[3]["rejection_code"] = "reject.single_point_signal"
    predictions = [
        {**record, "should_visualize": record["sample_id"] == "week3_002"}
        for record in records
    ]

    selected = select_balanced_records(records, predictions, negative_limit=2)

    assert [record["sample_id"] for record in selected] == [
        "week3_001",
        "week3_002",
        "week3_003",
    ]

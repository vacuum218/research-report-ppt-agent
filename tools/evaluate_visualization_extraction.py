"""Validate Week 3 gold annotations and evaluate prediction JSONL files."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = PROJECT_ROOT / "data/evaluation/visualization/week3_gold.jsonl"
_REJECTION_CODES = {
    "reject.single_number",
    "reject.administrative_numbers_only",
    "reject.single_point_signal",
    "reject.mixed_metric_or_unit",
    "reject.incomplete_table",
    "reject.non_composition_percentages",
    "reject.missing_label",
    "reject.out_of_scope",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: record must be an object")
        records.append(value)
    return records


def validate_gold(records: Sequence[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    sample_ids: set[str] = set()
    documents: set[str] = set()
    positive = 0
    negative = 0
    for index, record in enumerate(records, start=1):
        prefix = f"record {index}"
        sample_id = str(record.get("sample_id") or "")
        if not sample_id:
            errors.append(f"{prefix}: missing sample_id")
        elif sample_id in sample_ids:
            errors.append(f"{prefix}: duplicate sample_id {sample_id}")
        sample_ids.add(sample_id)
        document_id = str(record.get("document_id") or "")
        if not document_id:
            errors.append(f"{prefix}: missing document_id")
        else:
            documents.add(document_id)
        source = record.get("source")
        if (
            not isinstance(source, Mapping)
            or source.get("kind") not in {"block", "table"}
            or not source.get("id")
        ):
            errors.append(f"{prefix}: invalid source")
        if record.get("review_status") != "approved":
            errors.append(f"{prefix}: review_status must be approved")
        decision = record.get("should_visualize")
        if not isinstance(decision, bool):
            errors.append(f"{prefix}: should_visualize must be boolean")
            continue
        if decision:
            positive += 1
            expected = record.get("expected")
            if not isinstance(expected, Mapping):
                errors.append(f"{prefix}: positive sample requires expected")
            elif expected.get("visual_type") not in {"chart", "table"}:
                errors.append(f"{prefix}: invalid expected visual_type")
            if record.get("rejection_code") is not None:
                errors.append(f"{prefix}: positive sample cannot have rejection_code")
        else:
            negative += 1
            if record.get("expected") is not None:
                errors.append(f"{prefix}: negative sample expected must be null")
            if record.get("rejection_code") not in _REJECTION_CODES:
                errors.append(f"{prefix}: invalid rejection_code")
    if not 20 <= len(records) <= 30:
        errors.append("gold set must contain 20-30 evidence units")
    if len(documents) < 3:
        errors.append("gold set must cover at least three documents")
    if positive == 0 or negative == 0:
        errors.append("gold set must contain both positive and negative samples")
    return errors


def _prediction_map(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in records:
        sample_id = str(record.get("sample_id") or "")
        if not sample_id:
            raise ValueError("prediction record is missing sample_id")
        if sample_id in result:
            raise ValueError(f"duplicate prediction sample_id: {sample_id}")
        result[sample_id] = record
    return result


def _candidate_signature(record: Mapping[str, Any]) -> tuple[str, str | None] | None:
    if not record.get("should_visualize"):
        return None
    expected = record.get("expected")
    if not isinstance(expected, Mapping):
        return None
    return (
        str(expected.get("visual_type") or ""),
        str(expected.get("chart_intent")) if expected.get("chart_intent") is not None else None,
    )


def _fact_key(value: Mapping[str, Any]) -> str:
    locator = value.get("source_locator")
    payload = {
        "normalized_value": str(value.get("normalized_value")),
        "unit": str(value.get("unit") or ""),
        "label": value.get("label"),
        "period": value.get("period"),
        "source_locator": locator,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fact_records(expected: object) -> list[Mapping[str, Any]]:
    if not isinstance(expected, Mapping):
        return []
    values: list[Mapping[str, Any]] = []
    if expected.get("visual_type") == "chart":
        for series in expected.get("series", []):
            if isinstance(series, Mapping):
                values.extend(
                    fact
                    for fact in series.get("facts", [])
                    if isinstance(fact, Mapping)
                )
    elif expected.get("visual_type") == "table":
        values.extend(
            fact
            for fact in expected.get("numeric_facts", [])
            if isinstance(fact, Mapping)
        )
    return values


def _facts(expected: object) -> set[str]:
    return {_fact_key(value) for value in _fact_records(expected)}


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def evaluate(
    gold_records: Sequence[Mapping[str, Any]],
    prediction_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    predictions = _prediction_map(prediction_records)
    gold_positive = sum(bool(record.get("should_visualize")) for record in gold_records)
    predicted_positive = 0
    correct_candidates = 0
    correct_rejections = 0
    rejection_code_correct = 0
    structure_total = 0
    chart_type_correct = 0
    complete_objects = 0
    fact_tp = fact_fp = fact_fn = 0
    schema_pass = 0
    source_covered = 0
    fabricated = 0

    for gold in gold_records:
        sample_id = str(gold["sample_id"])
        prediction = predictions.get(
            sample_id,
            {"sample_id": sample_id, "should_visualize": False, "expected": None},
        )
        predicted_positive += bool(prediction.get("should_visualize"))
        gold_signature = _candidate_signature(gold)
        predicted_signature = _candidate_signature(prediction)
        matched = gold_signature is not None and gold_signature == predicted_signature
        if matched:
            correct_candidates += 1
            structure_total += 1
            gold_expected = gold.get("expected")
            predicted_expected = prediction.get("expected")
            if (
                isinstance(gold_expected, Mapping)
                and isinstance(predicted_expected, Mapping)
                and gold_expected.get("chart_type") == predicted_expected.get("chart_type")
            ):
                chart_type_correct += 1
            if gold_expected == predicted_expected:
                complete_objects += 1
        if not gold.get("should_visualize") and not prediction.get("should_visualize"):
            correct_rejections += 1
            if gold.get("rejection_code") == prediction.get("rejection_code"):
                rejection_code_correct += 1

        gold_facts = _facts(gold.get("expected"))
        predicted_facts = _facts(prediction.get("expected"))
        fact_tp += len(gold_facts & predicted_facts)
        fact_fp += len(predicted_facts - gold_facts)
        fact_fn += len(gold_facts - predicted_facts)
        if prediction.get("schema_valid") is True:
            schema_pass += 1
        fabricated += sum(
            not isinstance(fact.get("source_locator"), Mapping)
            for fact in _fact_records(prediction.get("expected"))
        )
        expected = prediction.get("expected")
        if (
            prediction.get("should_visualize")
            and isinstance(expected, Mapping)
            and isinstance(expected.get("sources"), list)
            and bool(expected.get("sources"))
        ):
            source_covered += 1

    precision = _ratio(correct_candidates, predicted_positive)
    recall = _ratio(correct_candidates, gold_positive)
    return {
        "counts": {
            "samples": len(gold_records),
            "gold_positive": gold_positive,
            "predicted_positive": predicted_positive,
            "correct_candidates": correct_candidates,
        },
        "candidate": {
            "precision": precision,
            "recall": recall,
            "f1": _ratio(2 * precision * recall, precision + recall),
        },
        "structure": {
            "chart_type_accuracy": _ratio(chart_type_correct, structure_total),
            "complete_object_accuracy": _ratio(complete_objects, gold_positive),
        },
        "numeric_cells": {
            "tp": fact_tp,
            "fp": fact_fp,
            "fn": fact_fn,
            "precision": _ratio(fact_tp, fact_tp + fact_fp),
            "recall": _ratio(fact_tp, fact_tp + fact_fn),
            "exact_match": _ratio(fact_tp, fact_tp + fact_fp + fact_fn),
        },
        "rejection": {
            "correct_rejection_rate": _ratio(
                correct_rejections,
                len(gold_records) - gold_positive,
            ),
            "reason_code_accuracy": _ratio(
                rejection_code_correct,
                len(gold_records) - gold_positive,
            ),
        },
        "engineering": {
            "schema_pass_count": schema_pass,
            "schema_pass_rate": _ratio(schema_pass, predicted_positive),
            "source_covered_count": source_covered,
            "source_coverage_rate": _ratio(source_covered, predicted_positive),
            "fabricated_numeric_cells": fabricated,
        },
    }


def _write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Week 3 gold and evaluate visualization predictions"
    )
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        gold = load_jsonl(args.gold)
        errors = validate_gold(gold)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 2
        print(
            f"Gold valid: samples={len(gold)}, "
            f"documents={len({item['document_id'] for item in gold})}"
        )
        if args.predictions is None:
            return 0
        predictions = load_jsonl(args.predictions)
        report = evaluate(gold, predictions)
        text = json.dumps(report, ensure_ascii=False, indent=2)
        print(text)
        if args.output is not None:
            _write_report(args.output, report)
            print(f"Created evaluation report: {args.output}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

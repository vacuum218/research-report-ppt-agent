"""Merge reviewed Week 3 batches and retain a deterministic negative subset."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_ROOT = PROJECT_ROOT / "data/evaluation/visualization"
DEFAULT_BASE_GOLD = EVALUATION_ROOT / "week3_initial_gold.jsonl"
DEFAULT_BASE_PREDICTIONS = (
    EVALUATION_ROOT / "week3_initial_baseline_predictions.jsonl"
)
DEFAULT_SUPPLEMENT_GOLD = (
    EVALUATION_ROOT / "week3_positive_supplement_gold.jsonl"
)
DEFAULT_SUPPLEMENT_PREDICTIONS = (
    EVALUATION_ROOT
    / "week3_positive_supplement_baseline_predictions.jsonl"
)
DEFAULT_OUTPUT = EVALUATION_ROOT / "week3_gold.jsonl"
DEFAULT_PREDICTIONS_OUTPUT = (
    EVALUATION_ROOT / "week3_baseline_predictions.jsonl"
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _record_map(
    records: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in records:
        sample_id = str(record.get("sample_id") or "")
        if not sample_id:
            raise ValueError(f"{label}: missing sample_id")
        if sample_id in result:
            raise ValueError(f"{label}: duplicate sample_id {sample_id}")
        result[sample_id] = record
    return result


def _source_key(record: Mapping[str, Any]) -> tuple[str, str, str]:
    source = record.get("source")
    if not isinstance(source, Mapping):
        raise ValueError(f"{record.get('sample_id')}: invalid source")
    return (
        str(record.get("document_id") or ""),
        str(source.get("kind") or ""),
        str(source.get("id") or ""),
    )


def select_balanced_records(
    records: Sequence[Mapping[str, Any]],
    predictions: Sequence[Mapping[str, Any]],
    *,
    negative_limit: int,
) -> list[dict[str, Any]]:
    """Keep every positive, then retain hard and coverage-increasing negatives."""

    if negative_limit < 1:
        raise ValueError("negative_limit must be positive")
    prediction_map = _record_map(predictions, label="predictions")
    positives = [dict(record) for record in records if record.get("should_visualize")]
    negatives = [dict(record) for record in records if not record.get("should_visualize")]
    if len(negatives) <= negative_limit:
        return sorted(positives + negatives, key=lambda item: str(item["sample_id"]))

    selected = sorted(
        (
            record
            for record in negatives
            if prediction_map.get(str(record["sample_id"]), {}).get(
                "should_visualize"
            )
        ),
        key=lambda item: str(item["sample_id"]),
    )
    if len(selected) > negative_limit:
        raise ValueError(
            "negative_limit is smaller than the frozen baseline false-positive set"
        )

    remaining = [
        record
        for record in negatives
        if str(record["sample_id"])
        not in {str(item["sample_id"]) for item in selected}
    ]
    while len(selected) < negative_limit:
        reason_counts: dict[str, int] = {}
        document_counts: dict[str, int] = {}
        selected_kinds: set[str] = set()
        for record in selected:
            reason = str(record.get("rejection_code") or "")
            document = str(record.get("document_id") or "")
            kind = _source_key(record)[1]
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            document_counts[document] = document_counts.get(document, 0) + 1
            selected_kinds.add(kind)

        def priority(record: Mapping[str, Any]) -> tuple[int, int, int, int, int, str]:
            reason = str(record.get("rejection_code") or "")
            document = str(record.get("document_id") or "")
            kind = _source_key(record)[1]
            return (
                -int(reason not in reason_counts),
                -int(document not in document_counts),
                -int(kind not in selected_kinds),
                reason_counts.get(reason, 0),
                document_counts.get(document, 0),
                str(record["sample_id"]),
            )

        chosen = min(remaining, key=priority)
        selected.append(chosen)
        remaining.remove(chosen)

    return sorted(positives + selected, key=lambda item: str(item["sample_id"]))


def merge_batches(
    base_gold: Sequence[Mapping[str, Any]],
    supplement_gold: Sequence[Mapping[str, Any]],
    base_predictions: Sequence[Mapping[str, Any]],
    supplement_predictions: Sequence[Mapping[str, Any]],
    *,
    negative_limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    gold = [dict(record) for record in (*base_gold, *supplement_gold)]
    predictions = [
        dict(record)
        for record in (*base_predictions, *supplement_predictions)
    ]
    _record_map(gold, label="gold")
    prediction_map = _record_map(predictions, label="predictions")

    source_keys: set[tuple[str, str, str]] = set()
    for record in gold:
        key = _source_key(record)
        if key in source_keys:
            raise ValueError(f"duplicate gold source: {key}")
        source_keys.add(key)

    balanced_gold = select_balanced_records(
        gold,
        predictions,
        negative_limit=negative_limit,
    )
    balanced_predictions = [
        dict(prediction_map[str(record["sample_id"])])
        for record in balanced_gold
    ]
    return balanced_gold, balanced_predictions


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".jsonl",
        prefix="week3_balanced_",
        dir=path.parent,
        delete=False,
    ) as handle:
        temporary_path = Path(handle.name)
        for record in records:
            json.dump(record, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
    try:
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge reviewed Week 3 gold batches and balance negatives"
    )
    parser.add_argument("--base-gold", type=Path, default=DEFAULT_BASE_GOLD)
    parser.add_argument(
        "--base-predictions",
        type=Path,
        default=DEFAULT_BASE_PREDICTIONS,
    )
    parser.add_argument(
        "--supplement-gold",
        type=Path,
        default=DEFAULT_SUPPLEMENT_GOLD,
    )
    parser.add_argument(
        "--supplement-predictions",
        type=Path,
        default=DEFAULT_SUPPLEMENT_PREDICTIONS,
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--predictions-output",
        type=Path,
        default=DEFAULT_PREDICTIONS_OUTPUT,
    )
    parser.add_argument("--negative-limit", type=int, default=12)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        gold, predictions = merge_batches(
            _load_jsonl(args.base_gold),
            _load_jsonl(args.supplement_gold),
            _load_jsonl(args.base_predictions),
            _load_jsonl(args.supplement_predictions),
            negative_limit=args.negative_limit,
        )
        _write_jsonl(args.output, gold)
        _write_jsonl(args.predictions_output, predictions)
        positive = sum(bool(record["should_visualize"]) for record in gold)
        kept_negatives = [
            str(record["sample_id"])
            for record in gold
            if not record["should_visualize"]
        ]
        print(f"Created balanced gold: {args.output}")
        print(f"Created aligned predictions: {args.predictions_output}")
        print(
            f"Distribution: positive={positive}, "
            f"negative={len(gold) - positive}, total={len(gold)}"
        )
        print(f"Retained negatives: {','.join(kept_negatives)}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

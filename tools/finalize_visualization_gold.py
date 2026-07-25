"""Apply an audited Markdown review checklist to the pending annotation draft."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DRAFT = (
    PROJECT_ROOT
    / "data/evaluation/visualization/week3_annotation_draft.jsonl"
)
DEFAULT_REVIEW = (
    PROJECT_ROOT
    / "data/evaluation/visualization/week3_annotation_review.md"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "data/evaluation/visualization/week3_gold.jsonl"
)
DEFAULT_PREDICTIONS_OUTPUT = (
    PROJECT_ROOT
    / "data/evaluation/visualization/week3_baseline_predictions.jsonl"
)
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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _review_decisions(path: Path) -> dict[str, str]:
    content = path.read_text(encoding="utf-8")
    sections = re.finditer(
        r"(?ms)^## (week3_\d+)\r?\n(.*?)(?=^## week3_|\Z)",
        content,
    )
    result: dict[str, str] = {}
    for section in sections:
        sample_id = section.group(1)
        decision_match = re.search(
            r"(?m)^- 审核结果：(?:\*\*)?([^*\r\n]+)(?:\*\*)?\s*$",
            section.group(2),
        )
        if decision_match is None:
            raise ValueError(f"{sample_id}: missing review decision")
        decision = decision_match.group(1).strip()
        if decision in {"待审核", "需讨论"}:
            raise ValueError(f"{sample_id}: unresolved review decision {decision}")
        result[sample_id] = decision
    return result


def _rejection_overrides(values: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(
                f"rejection override must be SAMPLE_ID=CODE: {value}"
            )
        sample_id, code = value.split("=", 1)
        if code not in _REJECTION_CODES:
            raise ValueError(f"unknown rejection code: {code}")
        result[sample_id] = code
    return result


def finalize(
    draft: Sequence[Mapping[str, Any]],
    decisions: Mapping[str, str],
    rejection_codes: Mapping[str, str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    draft_ids = {str(record.get("sample_id") or "") for record in draft}
    if set(decisions) != draft_ids:
        missing = sorted(draft_ids - set(decisions))
        extra = sorted(set(decisions) - draft_ids)
        raise ValueError(f"review/draft mismatch: missing={missing}, extra={extra}")
    for original in draft:
        record = dict(original)
        sample_id = str(record["sample_id"])
        suggested = record.get("suggested")
        if not isinstance(suggested, Mapping):
            raise ValueError(f"{sample_id}: missing suggested annotation")
        decision = decisions[sample_id]
        decision_kind = re.split(r"[:：]", decision, maxsplit=1)[0].strip()
        if decision_kind == "接受":
            record["should_visualize"] = bool(suggested["should_visualize"])
            record["expected"] = suggested.get("expected")
            record["rejection_code"] = suggested.get("rejection_code")
        elif decision_kind in {"拒绝", "改为拒绝"}:
            if not suggested.get("should_visualize"):
                raise ValueError(
                    f"{sample_id}: rejecting a negative suggestion requires an explicit positive annotation"
                )
            code = rejection_codes.get(sample_id)
            if code is None:
                raise ValueError(
                    f"{sample_id}: rejected positive suggestion requires --rejection-code"
                )
            record["should_visualize"] = False
            record["expected"] = None
            record["rejection_code"] = code
        elif decision_kind == "改为生成":
            raise ValueError(
                f"{sample_id}: changed-to-positive review requires a manually supplied expected object"
            )
        else:
            raise ValueError(f"{sample_id}: unsupported review decision {decision}")
        record["review_status"] = "approved"
        notes = str(record.get("notes") or "").strip()
        record["notes"] = (
            f"{notes}; manual_review={decision}".strip("; ")
        )
        record.pop("suggested", None)
        records.append(record)
    return records


def baseline_predictions(
    draft: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Freeze the pre-review system suggestions as unbiased baseline output."""

    result: list[dict[str, Any]] = []
    for record in draft:
        suggested = record.get("suggested")
        if not isinstance(suggested, Mapping):
            raise ValueError(
                f"{record.get('sample_id')}: missing suggested annotation"
            )
        should_visualize = bool(suggested.get("should_visualize"))
        result.append(
            {
                "sample_id": record["sample_id"],
                "source": record["source"],
                "should_visualize": should_visualize,
                "expected": suggested.get("expected"),
                "rejection_code": suggested.get("rejection_code"),
                "schema_valid": True if should_visualize else None,
            }
        )
    return result


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".jsonl",
        prefix="week3_gold_",
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
        description="Finalize manually reviewed Week 3 visualization gold"
    )
    parser.add_argument("--draft", type=Path, default=DEFAULT_DRAFT)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--predictions-output",
        type=Path,
        default=DEFAULT_PREDICTIONS_OUTPUT,
    )
    parser.add_argument(
        "--rejection-code",
        action="append",
        default=[],
        metavar="SAMPLE_ID=CODE",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        draft = _load_jsonl(args.draft)
        records = finalize(
            draft,
            _review_decisions(args.review),
            _rejection_overrides(args.rejection_code),
        )
        _write_jsonl(args.output, records)
        _write_jsonl(args.predictions_output, baseline_predictions(draft))
        positive = sum(record["should_visualize"] for record in records)
        print(f"Created approved gold: {args.output}")
        print(f"Created frozen baseline predictions: {args.predictions_output}")
        print(
            f"Distribution: positive={positive}, "
            f"negative={len(records) - positive}, total={len(records)}"
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

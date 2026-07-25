"""Prepare a second, high-confidence positive-candidate review batch."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from document_bundle.markdown import build_from_markdown
from document_intelligence import load_document_intelligence
from tools.prepare_visualization_annotations import (
    DEFAULT_SCHEMA,
    PreparedDocument,
    _evidence,
    _positive_expected,
    _relative,
    _round_robin,
    _section_id,
    _write_jsonl,
    _write_review,
)
from visualization_generator.candidate_detection import locate_corpus_candidates
from visualization_generator.contracts import (
    CandidateTriggerCode,
    VisualCandidate,
)
from visualization_generator.numeric_facts import build_numeric_fact_ledger


DEFAULT_EXCLUDE = (
    PROJECT_ROOT
    / "data/evaluation/visualization/week3_annotation_draft.jsonl"
)
DEFAULT_SUPPLEMENT_REPORTS = (
    PROJECT_ROOT / "data/reports/agent/000333_2025-10-30.md",
    PROJECT_ROOT / "data/reports/agent/001309_2025-10-28.md",
    PROJECT_ROOT / "data/reports/agent/002444_2025-09-21.md",
    PROJECT_ROOT / "data/reports/agent/002544_2025-10-28.md",
    PROJECT_ROOT / "data/reports/agent/002821_2025-09-11.md",
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "data/evaluation/visualization/week3_positive_supplement_draft.jsonl"
)
DEFAULT_REVIEW_OUTPUT = (
    PROJECT_ROOT
    / "data/evaluation/visualization/week3_positive_supplement_review.md"
)
DEFAULT_PREDICTIONS_OUTPUT = (
    PROJECT_ROOT
    / "data/evaluation/visualization/week3_positive_supplement_baseline_predictions.jsonl"
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _source_key(record: Mapping[str, Any]) -> tuple[str, str, str]:
    source = record["source"]
    return (
        str(record["document_id"]),
        str(source["kind"]),
        str(source["id"]),
    )


def _candidate(
    document: PreparedDocument,
    table_id: str,
    *,
    visual_type: str,
    intent: str | None,
) -> VisualCandidate:
    return VisualCandidate(
        candidate_id=(
            f"supp_{document.document_id}_{table_id}_{intent or visual_type}"
        ),
        slide_id=None,
        visual_type=visual_type,
        chart_intent=intent,
        evidence_refs=(("table", table_id),),
        trigger_ids=(
            CandidateTriggerCode.COMPLETE_TABLE,
            CandidateTriggerCode.COMPARABLE_NUMBERS,
            CandidateTriggerCode.LABELS_COLOCATED,
        ),
        score=1.0,
        excerpt=f"{document.document_id} {table_id}",
    )


def _manual_table_records(
    documents: Sequence[PreparedDocument],
    schema: Mapping[str, Any],
    excluded: set[tuple[str, str, str]],
) -> dict[str, list[dict[str, Any]]]:
    """Create reviewable positives from complete tables, independent of Locator."""

    result: dict[str, list[dict[str, Any]]] = {}
    for document in documents:
        records: list[dict[str, Any]] = []
        for table_id, table in document.snapshot.tables_by_id.items():
            source_key = (document.document_id, "table", table_id)
            if source_key in excluded or table.get("status") != "complete":
                continue
            if len(document.ledger.for_source("table", table_id)) < 2:
                continue
            chosen: tuple[VisualCandidate, dict[str, Any]] | None = None
            for intent in ("composition", "trend"):
                candidate = _candidate(
                    document,
                    table_id,
                    visual_type="chart",
                    intent=intent,
                )
                expected = _positive_expected(
                    document,
                    candidate,
                    schema,
                )
                if expected is None:
                    continue
                if intent == "trend" and len(expected.get("categories", [])) < 3:
                    continue
                chosen = (candidate, expected)
                break
            if chosen is None:
                candidate = _candidate(
                    document,
                    table_id,
                    visual_type="table",
                    intent=None,
                )
                expected = _positive_expected(document, candidate, schema)
                if expected is not None:
                    chosen = (candidate, expected)
            if chosen is None:
                continue
            candidate, expected = chosen
            records.append(
                {
                    "document_id": document.document_id,
                    "document_source": _relative(document.source_path),
                    "source": {"kind": "table", "id": table_id},
                    "section_id": _section_id(
                        document.snapshot, "table", table_id
                    ),
                    "evidence": _evidence(
                        document.snapshot, "table", table_id
                    ),
                    "review_status": "pending",
                    "should_visualize": None,
                    "expected": None,
                    "rejection_code": None,
                    "suggested": {
                        "should_visualize": True,
                        "expected": expected,
                        "rejection_code": None,
                        "candidate": {
                            "candidate_id": candidate.candidate_id,
                            "trigger_ids": list(candidate.trigger_ids),
                            "score": candidate.score,
                        },
                    },
                    "selection_origin": "complete_table_supplement_scan",
                    "notes": "",
                }
            )
        result[document.document_id] = records
    return result


def _baseline_prediction(
    record: Mapping[str, Any],
    documents: Mapping[str, PreparedDocument],
    schema: Mapping[str, Any],
) -> dict[str, Any]:
    document = documents[str(record["document_id"])]
    source = record["source"]
    ref = (str(source["kind"]), str(source["id"]))
    detected = next(
        (
            candidate
            for candidate in document.candidates
            if candidate.evidence_refs == (ref,)
        ),
        None,
    )
    expected = (
        _positive_expected(document, detected, schema)
        if detected is not None
        else None
    )
    return {
        "sample_id": record["sample_id"],
        "source": record["source"],
        "should_visualize": expected is not None,
        "expected": expected,
        "rejection_code": None,
        "schema_valid": True if expected is not None else None,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare high-confidence positive supplements for Week 3 gold"
    )
    parser.add_argument(
        "--report",
        action="append",
        type=Path,
        dest="reports",
    )
    parser.add_argument("--exclude", type=Path, default=DEFAULT_EXCLUDE)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--review-output",
        type=Path,
        default=DEFAULT_REVIEW_OUTPUT,
    )
    parser.add_argument(
        "--predictions-output",
        type=Path,
        default=DEFAULT_PREDICTIONS_OUTPUT,
    )
    parser.add_argument("--count", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    reports = tuple(args.reports or DEFAULT_SUPPLEMENT_REPORTS)
    try:
        excluded = {_source_key(record) for record in _load_jsonl(args.exclude)}
        schema = json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="week3_positive_supplement_") as directory:
            root = Path(directory)
            documents: list[PreparedDocument] = []
            for report in reports:
                report = report.resolve()
                bundle = root / report.stem
                build_from_markdown(report, bundle)
                snapshot = load_document_intelligence(
                    bundle,
                    PROJECT_ROOT / "schemas/document_bundle.schema.json",
                )
                documents.append(
                    PreparedDocument(
                        document_id=report.stem,
                        source_path=report,
                        snapshot=snapshot,
                        ledger=build_numeric_fact_ledger(snapshot),
                        candidates=tuple(locate_corpus_candidates(snapshot)),
                    )
                )
            grouped = _manual_table_records(documents, schema, excluded)
            # Supplement from reports not used by the first frozen gold first.
            new_document_ids = {"001309_2025-10-28", "002444_2025-09-21"}
            prioritized = {
                document_id: records
                for document_id, records in grouped.items()
                if document_id in new_document_ids
            }
            selected = _round_robin(prioritized, args.count)
            if len(selected) < args.count:
                selected_keys = {_source_key(record) for record in selected}
                fallback = {
                    document_id: [
                        record
                        for record in records
                        if _source_key(record) not in selected_keys
                    ]
                    for document_id, records in grouped.items()
                }
                selected.extend(
                    _round_robin(fallback, args.count - len(selected))
                )
            if len(selected) < args.count:
                available = sum(len(records) for records in grouped.values())
                raise ValueError(
                    f"only {available} unused complete-table supplements are available"
                )
            for index, record in enumerate(selected, start=28):
                record["sample_id"] = f"week3_{index:03d}"
            _write_jsonl(args.output, selected)
            _write_review(args.review_output, selected)
            document_map = {
                document.document_id: document for document in documents
            }
            _write_jsonl(
                args.predictions_output,
                [
                    _baseline_prediction(record, document_map, schema)
                    for record in selected
                ],
            )
            print(f"Created supplement draft: {args.output}")
            print(f"Created supplement review: {args.review_output}")
            print(
                "Created frozen supplement predictions: "
                f"{args.predictions_output}"
            )
            print(f"Samples: {len(selected)}")
            for document_id in sorted({item["document_id"] for item in selected}):
                count = sum(item["document_id"] == document_id for item in selected)
                print(f"  {document_id}: {count}")
            print("This supplement is pending and has not been merged into gold.")
            return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

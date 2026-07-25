"""Create a deterministic, explicitly non-gold Week 3 annotation draft."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from document_bundle.markdown import build_from_markdown
from document_intelligence import load_document_intelligence
from document_intelligence.models import DocumentIntelligenceSnapshot
from visualization_generator.candidate_detection import locate_corpus_candidates
from visualization_generator.contracts import NumericFact, VisualCandidate
from visualization_generator.extraction import map_extraction_proposal
from visualization_generator.numeric_facts import (
    NumericFactLedger,
    build_numeric_fact_ledger,
    table_grid,
)
from visualization_generator.planning import VisualizationPlan
from visualization_generator.verification import (
    VisualizationVerificationError,
    assemble_verified_chart,
    assemble_verified_table,
)


DEFAULT_REPORTS = (
    PROJECT_ROOT / "data/reports/agent/000333_2025-10-30.md",
    PROJECT_ROOT / "data/reports/agent/002544_2025-10-28.md",
    PROJECT_ROOT / "data/reports/agent/002821_2025-09-11.md",
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "data/evaluation/visualization/week3_annotation_draft.jsonl"
)
DEFAULT_REVIEW_OUTPUT = (
    PROJECT_ROOT
    / "data/evaluation/visualization/week3_annotation_review.md"
)
DEFAULT_SCHEMA = PROJECT_ROOT / "schemas/visualization.schema.json"


@dataclass(frozen=True, slots=True)
class PreparedDocument:
    document_id: str
    source_path: Path
    snapshot: DocumentIntelligenceSnapshot
    ledger: NumericFactLedger
    candidates: tuple[VisualCandidate, ...]


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _fact_record(fact: NumericFact) -> dict[str, Any]:
    locator = (
        {"start": fact.start, "end": fact.end}
        if fact.source_kind == "block"
        else {
            "row_index": fact.row_index,
            "column_index": fact.column_index,
        }
    )
    return {
        "fact_id": fact.fact_id,
        "raw_value": fact.raw_value,
        "normalized_value": str(fact.normalized_value),
        "unit": fact.unit,
        "label": fact.label,
        "period": fact.period,
        "source_locator": locator,
    }


def _evidence(
    snapshot: DocumentIntelligenceSnapshot,
    kind: str,
    identity: str,
) -> dict[str, Any]:
    if kind == "block":
        return {
            "text": str(snapshot.blocks_by_id[identity].get("text_raw") or ""),
            "table": None,
        }
    columns, rows = table_grid(snapshot.tables_by_id[identity])
    return {
        "text": None,
        "table": {"columns": columns, "rows": rows},
    }


def _section_id(
    snapshot: DocumentIntelligenceSnapshot,
    kind: str,
    identity: str,
) -> str | None:
    evidence = snapshot.evidence(kind, identity)
    return evidence.section_id if evidence is not None else None


def _plan(
    document_id: str,
    candidate: VisualCandidate,
) -> VisualizationPlan:
    intent_label = {
        "trend": "趋势",
        "comparison": "比较",
        "composition": "构成",
        None: "数据",
    }[candidate.chart_intent]
    return VisualizationPlan(
        slide_id=f"slide_eval_{document_id}",
        visualization_id=candidate.candidate_id,
        visual_type=candidate.visual_type,
        purpose=f"{document_id} {intent_label}可视化",
        chart_intent=candidate.chart_intent,
        data_requirement={},
        evidence_refs=candidate.evidence_refs,
        source_refs=(f"src_{document_id}",),
    )


def _positive_expected(
    document: PreparedDocument,
    candidate: VisualCandidate,
    schema: Mapping[str, Any],
) -> dict[str, Any] | None:
    plan = _plan(document.document_id, candidate)
    if candidate.visual_type == "chart":
        proposal = map_extraction_proposal(
            plan,
            document.snapshot,
            document.ledger,
        )
        if proposal is None:
            return None
        try:
            visualization = assemble_verified_chart(
                plan,
                proposal,
                document.ledger,
                schema,
                allowed_sources=candidate.evidence_refs,
            )
        except VisualizationVerificationError:
            return None
        series = []
        for proposed_series in proposal.series:
            facts = [
                document.ledger.get(fact_id)
                for fact_id in proposed_series.fact_ids
            ]
            if any(fact is None for fact in facts):
                return None
            series.append(
                {
                    "name": proposed_series.name,
                    "facts": [
                        _fact_record(fact)
                        for fact in facts
                        if fact is not None
                    ],
                }
            )
        return {
            "visual_type": "chart",
            "chart_intent": candidate.chart_intent,
            "chart_type": visualization["chart_type"],
            "title": visualization["title"],
            "unit": visualization["unit"],
            "categories": visualization["categories"],
            "series": series,
            "sources": visualization["sources"],
        }

    kind, identity = candidate.evidence_refs[0]
    if kind != "table":
        return None
    try:
        visualization = assemble_verified_table(
            plan,
            document.snapshot.tables_by_id[identity],
            document.ledger,
            schema,
        )
    except VisualizationVerificationError:
        return None
    return {
        "visual_type": "table",
        "chart_intent": None,
        "title": visualization["title"],
        "columns": visualization["columns"],
        "rows": visualization["rows"],
        "numeric_facts": [
            _fact_record(fact)
            for fact in document.ledger.for_source("table", identity)
        ],
        "sources": visualization["sources"],
    }


def _rejection_suggestion(
    document: PreparedDocument,
    kind: str,
    identity: str,
) -> str:
    evidence = _evidence(document.snapshot, kind, identity)
    text = str(evidence.get("text") or "")
    if re.search(r"股票代码|证券代码|报告编号|发布日期|报告日期|第\s*\d+\s*页", text):
        return "reject.administrative_numbers_only"
    if kind == "table":
        table = document.snapshot.tables_by_id[identity]
        if table.get("status") != "complete":
            return "reject.incomplete_table"
    facts = document.ledger.for_source(kind, identity)
    if len(facts) <= 1:
        return "reject.single_number"
    units = {fact.unit for fact in facts if fact.unit}
    if (
        len(facts) >= 2
        and all(fact.unit == "%" for fact in facts)
        and not 95 <= sum(fact.normalized_value for fact in facts) <= 105
    ):
        return "reject.non_composition_percentages"
    if len(units) > 1:
        return "reject.mixed_metric_or_unit"
    if any(not fact.label and not fact.period for fact in facts):
        return "reject.missing_label"
    return "reject.single_point_signal"


def _positive_records(
    documents: Sequence[PreparedDocument],
    schema: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in documents:
        for candidate in document.candidates:
            expected = _positive_expected(document, candidate, schema)
            if expected is None:
                continue
            kind, identity = candidate.evidence_refs[0]
            result[document.document_id].append(
                {
                    "document_id": document.document_id,
                    "document_source": _relative(document.source_path),
                    "source": {"kind": kind, "id": identity},
                    "section_id": _section_id(
                        document.snapshot, kind, identity
                    ),
                    "evidence": _evidence(document.snapshot, kind, identity),
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
                    "notes": "",
                }
            )
    return result


def _negative_records(
    documents: Sequence[PreparedDocument],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in documents:
        positive_sources = {
            ref
            for candidate in document.candidates
            for ref in candidate.evidence_refs
        }
        refs: list[tuple[str, str]] = []
        for block_id in document.snapshot.ordered_block_ids:
            block = document.snapshot.blocks_by_id[block_id]
            text = str(block.get("text_raw") or "")
            if (
                ("block", block_id) not in positive_sources
                and re.search(r"\d", text)
                and str(block.get("type") or "")
                in {"paragraph", "blockquote", "list_item"}
                and not document.snapshot.block_table_ids.get(block_id)
            ):
                refs.append(("block", block_id))
        refs.extend(
            ("table", table_id)
            for table_id, table in document.snapshot.tables_by_id.items()
            if ("table", table_id) not in positive_sources
            and (
                table.get("status") != "complete"
                or len(document.ledger.for_source("table", table_id)) <= 1
            )
        )
        refs.sort(
            key=lambda ref: (
                0 if len(document.ledger.for_source(*ref)) > 0 else 1,
                ref,
            )
        )
        records: list[dict[str, Any]] = []
        for kind, identity in refs:
            records.append(
                {
                    "document_id": document.document_id,
                    "document_source": _relative(document.source_path),
                    "source": {"kind": kind, "id": identity},
                    "section_id": _section_id(
                        document.snapshot, kind, identity
                    ),
                    "evidence": _evidence(document.snapshot, kind, identity),
                    "review_status": "pending",
                    "should_visualize": None,
                    "expected": None,
                    "rejection_code": None,
                    "suggested": {
                        "should_visualize": False,
                        "expected": None,
                        "rejection_code": _rejection_suggestion(
                            document, kind, identity
                        ),
                        "candidate": None,
                    },
                    "notes": "",
                }
            )
        by_reason: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            by_reason[str(record["suggested"]["rejection_code"])].append(record)
        result[document.document_id].extend(
            _round_robin(by_reason, len(records))
        )
    return result


def _round_robin(
    grouped: Mapping[str, Sequence[dict[str, Any]]],
    count: int,
) -> list[dict[str, Any]]:
    keys = sorted(grouped)
    positions = {key: 0 for key in keys}
    result: list[dict[str, Any]] = []
    while len(result) < count:
        progressed = False
        for key in keys:
            index = positions[key]
            values = grouped[key]
            if index >= len(values):
                continue
            result.append(dict(values[index]))
            positions[key] += 1
            progressed = True
            if len(result) == count:
                break
        if not progressed:
            break
    return result


def _write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".jsonl",
        prefix="week3_annotations_",
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


def _review_summary(record: Mapping[str, Any]) -> str:
    suggested = record["suggested"]
    if not suggested["should_visualize"]:
        return f"不生成；原因 `{suggested['rejection_code']}`"
    expected = suggested["expected"]
    value = f"生成 `{expected['visual_type']}`"
    if expected.get("chart_intent"):
        value += f" / `{expected['chart_intent']}`"
    if expected.get("chart_type"):
        value += f" / `{expected['chart_type']}`"
    return value


def _write_review(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    lines = [
        "# Week 3 Visualization 预标注人工审核",
        "",
        "此文件是审核清单，不是 gold。每条记录请把“审核结果”改为：",
        "`接受`、`改为生成`、`改为拒绝` 或 `需讨论`，并在修改说明中写明更正。",
        "不要手工计算 span 或 table 坐标；只审核语义、指标关系、单位和是否应该可视化。",
        "",
    ]
    for record in records:
        source = record["source"]
        evidence = record["evidence"]
        lines.extend(
            [
                f"## {record['sample_id']}",
                "",
                f"- 报告：`{record['document_id']}`",
                f"- 来源：`{source['kind']}:{source['id']}`",
                f"- 自动建议：{_review_summary(record)}",
                "- 审核结果：**待审核**",
                "- 修改说明：",
                "",
            ]
        )
        if evidence.get("text") is not None:
            text = str(evidence["text"]).strip()
            lines.extend(["> " + line for line in text.splitlines()[:12]])
            lines.append("")
        else:
            table = evidence.get("table") or {}
            columns = [str(value).replace("|", "\\|") for value in table.get("columns", [])[:8]]
            rows = table.get("rows", [])[:8]
            if columns:
                lines.append("| " + " | ".join(columns) + " |")
                lines.append("| " + " | ".join("---" for _ in columns) + " |")
                for row in rows:
                    values = [
                        str(value).replace("|", "\\|")
                        for value in list(row)[: len(columns)]
                    ]
                    values += [""] * (len(columns) - len(values))
                    lines.append("| " + " | ".join(values) + " |")
                lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a pending Week 3 visualization annotation draft"
    )
    parser.add_argument(
        "--report",
        action="append",
        type=Path,
        dest="reports",
        help="Markdown report; repeat at least three times",
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--review-output",
        type=Path,
        default=DEFAULT_REVIEW_OUTPUT,
    )
    parser.add_argument("--positive-count", type=int, default=15)
    parser.add_argument("--negative-count", type=int, default=12)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    reports = tuple(args.reports or DEFAULT_REPORTS)
    if len(reports) < 3:
        print("ERROR: at least three reports are required", file=sys.stderr)
        return 2
    if args.positive_count < 1 or args.negative_count < 1:
        print("ERROR: positive and negative counts must be positive", file=sys.stderr)
        return 2
    schema = json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    try:
        with tempfile.TemporaryDirectory(prefix="week3_annotation_bundles_") as directory:
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
            positives = _round_robin(
                _positive_records(documents, schema),
                args.positive_count,
            )
            negatives = _round_robin(
                _negative_records(documents),
                args.negative_count,
            )
            if len(positives) < args.positive_count:
                raise ValueError(
                    f"only {len(positives)} verifiable positive samples are available"
                )
            if len(negatives) < args.negative_count:
                raise ValueError(
                    f"only {len(negatives)} negative samples are available"
                )
            records = [*positives, *negatives]
            for index, record in enumerate(records, start=1):
                record["sample_id"] = f"week3_{index:03d}"
            _write_jsonl(args.output, records)
            _write_review(args.review_output, records)
            print(f"Created pending annotation draft: {args.output}")
            print(f"Created manual review checklist: {args.review_output}")
            print(
                "Distribution: "
                f"positive={len(positives)}, negative={len(negatives)}, "
                f"documents={len({item['document_id'] for item in records})}"
            )
            for document_id in sorted({item["document_id"] for item in records}):
                count = sum(item["document_id"] == document_id for item in records)
                print(f"  {document_id}: {count}")
            print("This file is not gold until every record is manually reviewed.")
            return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

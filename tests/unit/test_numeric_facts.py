from __future__ import annotations

from decimal import Decimal

from document_intelligence import build_snapshot
from visualization_generator.numeric_facts import (
    block_numeric_facts,
    build_numeric_fact_ledger,
    table_numeric_facts,
)


def _block(text: str) -> dict:
    return {
        "id": "p001-b001",
        "page": 1,
        "type": "paragraph",
        "text_raw": text,
        "bbox": None,
        "parser_order": 0,
        "reading_order": 0,
        "section_id": "sec-1",
        "source_type": "test",
    }


def _table(status: str = "complete") -> dict:
    return {
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
        "status": status,
        "issues": [],
        "continuation_block_ids": [],
        "source_block_id": None,
    }


def _snapshot(tmp_path):
    block = _block("2022年营业收入10亿元，2023年营业收入15亿元。")
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
                "block_ids": [block["id"]],
            }
        ],
        "blocks": [block],
        "sections": [
            {
                "id": "sec-1",
                "level": 1,
                "title_block_id": block["id"],
                "parent_id": None,
                "child_section_ids": [],
                "content_block_ids": [block["id"]],
            }
        ],
        "tables": [_table()],
        "figures": [],
        "reading_order": [block["id"]],
    }
    return build_snapshot(document, tmp_path)


def test_block_facts_preserve_decimal_unit_period_and_exact_span():
    text = "2021年营业收入10亿元，2022年营业收入15.5亿元，2023年营业收入22亿元。"

    facts = block_numeric_facts(_block(text))

    assert [fact.normalized_value for fact in facts] == [
        Decimal("10"),
        Decimal("15.5"),
        Decimal("22"),
    ]
    assert [fact.unit for fact in facts] == ["亿元", "亿元", "亿元"]
    assert [fact.period for fact in facts] == ["2021", "2022", "2023"]
    assert all(text[fact.start : fact.end] == fact.raw_value for fact in facts)
    assert all(fact.fact_id.startswith("fact_") for fact in facts)


def test_block_facts_expand_year_range_and_propagate_shared_trailing_unit():
    text = "预计2025-2027年归母净利润分别为1.08/1.45/2.01亿元。"

    facts = block_numeric_facts(_block(text))

    assert [fact.normalized_value for fact in facts] == [
        Decimal("1.08"),
        Decimal("1.45"),
        Decimal("2.01"),
    ]
    assert [fact.period for fact in facts] == ["2025", "2026", "2027"]
    assert [fact.unit for fact in facts] == ["亿元", "亿元", "亿元"]


def test_table_facts_use_zero_based_cell_coordinates_and_header_units():
    facts = table_numeric_facts(_table())

    assert len(facts) == 4
    first = facts[0]
    assert first.normalized_value == Decimal("10")
    assert first.unit == "亿元"
    assert first.label == "营业收入"
    assert first.period == "2022A"
    assert (first.row_index, first.column_index) == (0, 1)
    assert first.start is None and first.end is None


def test_incomplete_table_does_not_register_numeric_facts():
    assert table_numeric_facts(_table(status="partial")) == ()


def test_fact_ledger_is_deterministic_and_indexes_sources_and_cells(tmp_path):
    snapshot = _snapshot(tmp_path)

    first = build_numeric_fact_ledger(snapshot)
    second = build_numeric_fact_ledger(snapshot)

    assert first.facts == second.facts
    assert len(first.for_source("block", "p001-b001")) == 2
    table_fact = first.table_cell("table-001", 1, 2)
    assert table_fact is not None
    assert first.get(table_fact.fact_id) is table_fact


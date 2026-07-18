#!/usr/bin/env python3
"""Unit tests for the T2.2 Markdown/plain-text report parser.

Run from the project root:
    python -m unittest discover -s tests -p "test_*.py" -v
"""

from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_parser_module():
    """Load parse_report.py from the recommended or legacy project location."""
    candidates = (PROJECT_ROOT / "document_parser" / "parse_report.py",)
    parser_path = next((path for path in candidates if path.is_file()), None)
    if parser_path is None:
        searched = "\n".join(f"  - {path}" for path in candidates)
        raise RuntimeError(f"Cannot find parse_report.py. Searched:\n{searched}")

    spec = importlib.util.spec_from_file_location("parse_report", parser_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load parser module: {parser_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parse_report = _load_parser_module()


class ParseReportFixtureTests(unittest.TestCase):
    """Acceptance-oriented tests covering more than three input structures."""

    def parse_fixture(self, filename: str, *, source_format: str = "auto"):
        return parse_report.parse_file(
            FIXTURES_DIR / filename,
            source_format=source_format,
        )

    @staticmethod
    def blocks_of_type(result, block_type: str):
        return [block for block in result["blocks"] if block["type"] == block_type]

    def test_markdown_headings_paragraphs_and_section_hierarchy(self):
        result = self.parse_fixture("heading_paragraph.md")
        headings = self.blocks_of_type(result, "heading")
        paragraphs = self.blocks_of_type(result, "paragraph")

        self.assertEqual([item["level"] for item in headings], [1, 2])
        self.assertEqual(headings[0]["text"], "示例公司2025年三季报")
        self.assertEqual(headings[1]["text"], "核心结论")
        self.assertEqual(headings[1]["parent_heading_id"], headings[0]["block_id"])
        self.assertEqual(paragraphs[0]["citations"], ["revenue_2025q3"])
        self.assertEqual(paragraphs[1]["parent_heading_id"], headings[1]["block_id"])
        self.assertEqual(result["document"]["source_format"], "markdown")

    def test_block_line_range_and_raw_text_are_preserved(self):
        result = self.parse_fixture("heading_paragraph.md")
        first_paragraph = self.blocks_of_type(result, "paragraph")[0]

        self.assertEqual(first_paragraph["line_start"], 3)
        self.assertEqual(first_paragraph["line_end"], 3)
        self.assertEqual(
            first_paragraph["raw_text"],
            "公司前三季度收入保持增长。[^cite_id:revenue_2025q3]",
        )

    def test_unordered_and_ordered_lists(self):
        result = self.parse_fixture("list_sample.md")
        lists = self.blocks_of_type(result, "list")

        self.assertEqual(len(lists), 2)
        self.assertFalse(lists[0]["ordered"])
        self.assertEqual([item["text"] for item in lists[0]["items"]], ["海外收入增长", "毛利率改善"])
        self.assertTrue(lists[1]["ordered"])
        self.assertEqual(lists[1]["start_number"], 1)
        self.assertEqual([item["marker"] for item in lists[1]["items"]], ["1.", "2."])

    def test_markdown_table_columns_alignment_and_rows(self):
        result = self.parse_fixture("table_sample.md")
        tables = self.blocks_of_type(result, "table")

        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertEqual(table["columns"], ["指标", "2024A", "2025E"])
        self.assertEqual(table["alignments"], ["left", "right", "center"])
        self.assertEqual(table["rows"][0], ["营业收入", "100", "120"])
        self.assertEqual(table["rows"][1], ["归母净利润", "12", "15"])

    def test_plain_text_numbered_headings(self):
        result = self.parse_fixture("plain_text_sample.txt")
        headings = self.blocks_of_type(result, "heading")

        self.assertEqual(result["document"]["source_format"], "plain_text")
        self.assertEqual([item["level"] for item in headings], [1, 2])
        self.assertEqual(headings[0]["text"], "第一章 公司概况")
        self.assertEqual(headings[1]["text"], "经营亮点")

    def test_statistics_match_generated_blocks(self):
        result = self.parse_fixture("table_sample.md")
        stats = result["statistics"]

        self.assertEqual(stats["block_count"], len(result["blocks"]))
        self.assertEqual(stats["heading_count"], 1)
        self.assertEqual(stats["table_count"], 1)
        self.assertEqual(stats["paragraph_count"], 0)


class ParseReportBoundaryTests(unittest.TestCase):
    def test_gb18030_input_is_detected(self):
        content = "第一章 公司概况\n\n公司经营保持稳定。\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report.txt"
            raw = content.encode("gb18030")
            path.write_bytes(raw)

            result = parse_report.parse_file(path)

        self.assertEqual(result["document"]["encoding"], "gb18030")
        self.assertEqual(result["document"]["source_hash_sha256"], hashlib.sha256(raw).hexdigest())

    def test_unknown_extension_requires_explicit_format(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report.data"
            path.write_text("# 标题\n", encoding="utf-8")

            with self.assertRaises(parse_report.ParseError):
                parse_report.parse_file(path)

    def test_unknown_extension_can_be_parsed_with_explicit_format(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report.data"
            path.write_text("# 标题\n", encoding="utf-8")

            result = parse_report.parse_file(path, source_format="markdown")

        self.assertEqual(result["blocks"][0]["type"], "heading")
        self.assertEqual(result["blocks"][0]["text"], "标题")


if __name__ == "__main__":
    unittest.main(verbosity=2)

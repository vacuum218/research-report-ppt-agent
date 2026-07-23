from __future__ import annotations

import fitz

from document_bundle.bundle import build_from_raw
from document_bundle.query import DocumentBundleQuery


def test_required_queries(tmp_path) -> None:
    pdf = tmp_path / "source.pdf"
    source = fitz.open()
    source.new_page(width=600, height=800)
    source.new_page(width=600, height=800)
    source.save(pdf)
    source.close()
    raw = __import__("pathlib").Path(__file__).parent / "fixtures" / "raw"
    bundle = tmp_path / "document_bundle"
    build_from_raw(pdf, raw, bundle, "fixture-id")
    query = DocumentBundleQuery(bundle)

    assert query.block("p001-b002")["text_raw"] == "原始测试段落。"
    assert len(query.page_blocks(1)) == 5
    assert query.section_blocks("sec-1")
    assert [block["id"] for block in query.ordered_blocks()] == query.document["reading_order"]
    assert len(query.paragraphs()) == 1
    assert len(query.tables()) == 1
    assert len(query.figures()) == 1
    assert query.source_location("p001-b002") == {"page": 1, "bbox": [30.0, 96.0, 540.0, 240.0]}
    assert query.unresolved() == []


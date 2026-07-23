from __future__ import annotations

import fitz

from document_bundle.bundle import build_from_raw


def test_validation_covers_frozen_structure_and_raw_files(tmp_path) -> None:
    pdf = tmp_path / "source.pdf"
    source = fitz.open()
    source.new_page(width=600, height=800)
    source.new_page(width=600, height=800)
    source.save(pdf)
    source.close()
    raw = __import__("pathlib").Path(__file__).parent / "fixtures" / "raw"
    bundle = tmp_path / "document_bundle"
    document, validation = build_from_raw(pdf, raw, bundle, "fixture-id")

    assert set(document) == {"document", "pages", "blocks", "sections", "tables", "figures", "reading_order"}
    assert validation["page_count"] == {"expected": 2, "actual": 2}
    assert validation["block_coverage"]["raw_block_count"] == 9
    assert validation["block_coverage"]["structured_block_count"] == 9
    assert validation["block_coverage"]["missing_block_ids"] == []
    assert validation["parser"]["fallback_used"] is False
    assert validation["issues"] == []


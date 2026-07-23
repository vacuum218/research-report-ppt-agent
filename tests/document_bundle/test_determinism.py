from __future__ import annotations

import fitz

from document_bundle.bundle import build_from_raw


def test_repeated_builds_are_byte_stable(tmp_path) -> None:
    pdf = tmp_path / "source.pdf"
    source = fitz.open()
    source.new_page(width=600, height=800)
    source.new_page(width=600, height=800)
    source.save(pdf)
    source.close()
    raw = __import__("pathlib").Path(__file__).parent / "fixtures" / "raw"
    first = tmp_path / "first" / "document_bundle"
    second = tmp_path / "second" / "document_bundle"

    build_from_raw(pdf, raw, first, "fixture-id")
    build_from_raw(pdf, raw, second, "fixture-id")

    for relative in (
        "document.json",
        "validation.json",
        "assets/figures/fig-001.png",
        "assets/tables/table-001-page-2.png",
    ):
        assert (first / relative).read_bytes() == (second / relative).read_bytes()


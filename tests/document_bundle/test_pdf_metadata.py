from __future__ import annotations

import hashlib

import fitz

from document_bundle.pdf_metadata import read_pdf_metadata


def test_pdf_sha_page_count_and_dimensions(tmp_path) -> None:
    path = tmp_path / "two-pages.pdf"
    document = fitz.open()
    document.new_page(width=600, height=800)
    document.new_page(width=500, height=700)
    document.save(path)
    document.close()

    metadata = read_pdf_metadata(path)
    assert metadata.page_count == 2
    assert [(page.width, page.height) for page in metadata.pages] == [(600.0, 800.0), (500.0, 700.0)]
    assert metadata.source_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


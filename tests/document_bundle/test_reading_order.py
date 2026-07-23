from __future__ import annotations

from document_bundle.transform.reading_order import assign_reading_order


def test_reading_order_is_explicit_and_does_not_replace_parser_order() -> None:
    blocks = [
        {"id": "a", "parser_order": 7, "reading_order": None},
        {"id": "b", "parser_order": 8, "reading_order": None},
    ]
    assert assign_reading_order(blocks) == ["a", "b"]
    assert [block["reading_order"] for block in blocks] == [0, 1]
    assert [block["parser_order"] for block in blocks] == [7, 8]


def test_caption_precedes_primary_asset_and_footnote_follows() -> None:
    blocks = [
        {"id": "table", "source_content_index": 1, "source_field": "table_body", "reading_order": None},
        {"id": "caption", "source_content_index": 1, "source_field": "table_caption", "reading_order": None},
        {"id": "footnote", "source_content_index": 1, "source_field": "table_footnote", "reading_order": None},
    ]
    assert assign_reading_order(blocks) == ["caption", "table", "footnote"]


def test_vector_figure_source_note_follows_all_visual_columns() -> None:
    blocks = [
        {"id": "caption", "page": 1, "type": "image_caption", "source_type": "text", "source_content_index": 1, "source_field": "text", "bbox": [10, 10, 90, 20]},
        {"id": "column-1", "page": 1, "type": "figure_text", "source_type": "text", "source_content_index": 2, "source_field": "text", "bbox": [10, 30, 30, 60]},
        {"id": "note", "page": 1, "type": "image_footnote", "source_type": "text", "source_content_index": 3, "source_field": "text", "bbox": [10, 90, 90, 100]},
        {"id": "column-2", "page": 1, "type": "figure_text", "source_type": "text", "source_content_index": 4, "source_field": "text", "bbox": [40, 30, 60, 60]},
    ]
    assert assign_reading_order(blocks) == ["caption", "column-1", "column-2", "note"]

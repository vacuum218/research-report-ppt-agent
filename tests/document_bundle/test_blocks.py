from __future__ import annotations

from pathlib import Path

from document_bundle.models import PDFPageMetadata
from document_bundle.transform.blocks import build_blocks, load_content_list


RAW = Path(__file__).parent / "fixtures" / "raw"


def test_blocks_preserve_all_readable_fields_and_stable_ids() -> None:
    items = load_content_list(RAW / "content_list.json")
    pages = (PDFPageMetadata(1, 600, 800), PDFPageMetadata(2, 600, 800))
    first = build_blocks(items, pages)
    second = build_blocks(items, pages)

    assert first.blocks == second.blocks
    assert first.raw_block_count == len(first.blocks) == 9
    assert [block["id"] for block in first.blocks] == [
        "p001-b001",
        "p001-b002",
        "p001-b003",
        "p001-b004",
        "p001-b005",
        "p002-b001",
        "p002-b002",
        "p002-b003",
        "p002-b004",
    ]
    assert first.blocks[0]["text_raw"] == "1 原始测试标题"
    assert first.blocks[3]["text_raw"] == "图 1 原始题注"
    assert first.blocks[6]["text_raw"] == "表 1 原始表题"
    assert first.blocks[0]["bbox"] == [30.0, 32.0, 480.0, 80.0]
    assert not first.issues


def test_chart_caption_and_footnote_are_not_omitted() -> None:
    items = [
        {
            "type": "chart",
            "content": "",
            "chart_caption": ["图1：原始图题"],
            "chart_footnote": ["资料来源：原始来源"],
            "img_path": "images/chart.jpg",
            "page_idx": 0,
            "bbox": [100, 100, 900, 700],
        }
    ]
    result = build_blocks(items, (PDFPageMetadata(1, 600, 800),))
    assert result.raw_block_count == 3
    assert [block["type"] for block in result.blocks] == [
        "figure",
        "chart_caption",
        "chart_footnote",
    ]
    assert [block["text_raw"] for block in result.blocks[1:]] == [
        "图1：原始图题",
        "资料来源：原始来源",
    ]


def test_vector_figure_text_is_not_mistaken_for_document_heading() -> None:
    items = [
        {"type": "text", "text": "图3：原始矢量图", "page_idx": 0, "bbox": [50, 100, 700, 130]},
        {"type": "text", "text": "图内标题", "text_level": 2, "page_idx": 0, "bbox": [100, 170, 400, 210]},
        {"type": "text", "text": "资料来源：原始来源", "page_idx": 0, "bbox": [50, 400, 500, 430]},
    ]
    result = build_blocks(items, (PDFPageMetadata(1, 600, 800),))
    assert [block["type"] for block in result.blocks] == [
        "image_caption",
        "figure_text",
        "image_footnote",
    ]

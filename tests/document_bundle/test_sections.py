from __future__ import annotations

from document_bundle.transform.sections import build_sections


def test_section_hierarchy_only_references_original_heading_blocks() -> None:
    blocks = [
        {"id": "p001-b001", "type": "heading", "text_raw": "1 原始一级标题", "text_level": 1, "section_id": None},
        {"id": "p001-b002", "type": "paragraph", "text_raw": "原文", "section_id": None},
        {"id": "p001-b003", "type": "heading", "text_raw": "1.1 原始二级标题", "text_level": 2, "section_id": None},
        {"id": "p001-b004", "type": "paragraph", "text_raw": "原文二", "section_id": None},
    ]
    sections = build_sections(blocks)
    assert [section["id"] for section in sections] == ["sec-1", "sec-1-1"]
    assert sections[1]["parent_id"] == "sec-1"
    assert sections[0]["title_block_id"] == "p001-b001"
    assert sections[0]["content_block_ids"] == ["p001-b001", "p001-b002", "p001-b003", "p001-b004"]
    assert blocks[-1]["section_id"] == "sec-1-1"


def test_non_numbered_figure_heading_does_not_create_section() -> None:
    blocks = [
        {"id": "a", "page": 3, "type": "heading", "text_raw": "1 原始章节", "text_level": 2, "section_id": None},
        {"id": "b", "page": 10, "type": "heading", "text_raw": "图内栏目标题", "text_level": 2, "section_id": None},
        {"id": "c", "page": 10, "type": "paragraph", "text_raw": "原文", "section_id": None},
    ]
    sections = build_sections(blocks)
    assert len(sections) == 1
    assert sections[0]["id"] == "sec-1"
    assert sections[0]["level"] == 1
    assert blocks[1]["section_id"] == "sec-1"

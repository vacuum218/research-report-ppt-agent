from __future__ import annotations

import json
import fitz

from document_bundle.bundle import build_from_raw


def write_raw(raw, content_list) -> None:
    raw.mkdir(parents=True)
    (raw / "content_list.json").write_text(
        json.dumps(content_list, ensure_ascii=False), encoding="utf-8"
    )
    (raw / "layout.json").write_text("{}", encoding="utf-8")
    (raw / "model.json").write_text("[]", encoding="utf-8")
    (raw / "document.md").write_text("原始 Markdown", encoding="utf-8")


def test_figure_and_table_are_rendered_at_stable_paths(tmp_path) -> None:
    pdf = tmp_path / "source.pdf"
    source = fitz.open()
    source.new_page(width=600, height=800)
    source.new_page(width=600, height=800)
    source.save(pdf)
    source.close()
    raw = __import__("pathlib").Path(__file__).parent / "fixtures" / "raw"
    bundle = tmp_path / "document_bundle"

    document, validation = build_from_raw(pdf, raw, bundle, "fixture-id")

    assert (bundle / "assets/figures/fig-001.png").is_file()
    assert (bundle / "assets/tables/table-001-page-2.png").is_file()
    assert document["figures"][0]["caption_block_id"] == "p001-b004"
    assert document["tables"][0]["title_block_id"] == "p002-b002"
    assert document["tables"][0]["structure_raw"]["content"].startswith("<table>")
    assert validation["status"] == "passed"


def test_chart_and_vector_figure_regions_are_rendered(tmp_path) -> None:
    pdf = tmp_path / "source.pdf"
    source = fitz.open()
    page = source.new_page(width=600, height=800)
    page.draw_rect(fitz.Rect(30, 300, 500, 500), color=(1, 0, 0))
    source.save(pdf)
    source.close()
    raw = tmp_path / "raw"
    write_raw(
        raw,
        [
            {
                "type": "chart",
                "content": "",
                "chart_caption": ["图1：原始图题"],
                "chart_footnote": ["资料来源：原始图表来源"],
                "img_path": "images/chart.jpg",
                "page_idx": 0,
                "bbox": [50, 50, 900, 250],
            },
            {"type": "text", "text": "图2：原始矢量图", "page_idx": 0, "bbox": [50, 300, 800, 330]},
            {"type": "text", "text": "矢量图内原文", "text_level": 2, "page_idx": 0, "bbox": [100, 400, 700, 500]},
            {"type": "text", "text": "资料来源：原始矢量来源", "page_idx": 0, "bbox": [50, 700, 700, 730]},
        ],
    )
    bundle = tmp_path / "document_bundle"
    document, validation = build_from_raw(pdf, raw, bundle, "fixture-id")
    assert len(document["figures"]) == 2
    assert document["figures"][1]["source"] == "pdf_vector_region_render"
    assert document["figures"][1]["caption_block_id"] == "p001-b004"
    assert (bundle / document["figures"][1]["asset_path"]).is_file()
    assert validation["status"] == "passed"


def test_cross_page_table_keeps_two_crops_without_inventing_structure(tmp_path) -> None:
    pdf = tmp_path / "source.pdf"
    source = fitz.open()
    source.new_page(width=600, height=800)
    source.new_page(width=600, height=800)
    source.save(pdf)
    source.close()
    raw = tmp_path / "raw"
    write_raw(
        raw,
        [
            {
                "type": "table",
                "table_caption": ["表1：原始跨页表"],
                "table_footnote": [],
                "table_body": "<table><tr><td>第一页原始结构</td></tr></table>",
                "page_idx": 0,
                "bbox": [50, 400, 900, 900],
            },
            {"type": "text", "text": "续行一", "page_idx": 1, "bbox": [150, 110, 300, 140]},
            {"type": "text", "text": "续行二", "page_idx": 1, "bbox": [350, 110, 600, 140]},
            {"type": "text", "text": "续行三", "page_idx": 1, "bbox": [650, 110, 850, 140]},
            {"type": "text", "text": "资料来源：原始来源", "page_idx": 1, "bbox": [50, 160, 600, 180]},
        ],
    )
    bundle = tmp_path / "document_bundle"
    document, validation = build_from_raw(pdf, raw, bundle, "fixture-id")
    table = document["tables"][0]
    assert [fragment["page"] for fragment in table["fragments"]] == [1, 2]
    assert table["status"] == "image_only"
    assert table["structure_raw"] is None
    assert len(table["continuation_block_ids"]) == 3
    assert (bundle / table["fragments"][1]["crop_path"]).is_file()
    assert validation["status"] == "needs_review"
    assert validation["tables"]["image_only"] == 1

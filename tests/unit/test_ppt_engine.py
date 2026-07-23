from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pptx.util import Inches

from ppt_engine.renderer import (
    RenderError,
    _clear_unbound_template_metrics,
    render_compiled_plan,
    render_presentation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load(relative: str):
    return json.loads((PROJECT_ROOT / relative).read_text(encoding="utf-8"))


def image_visualization(asset_path: str) -> dict:
    return {
        "type": "image",
        "title": "原始研报图片",
        "source": {"kind": "figure", "id": "fig-001"},
        "asset_path": asset_path,
        "source_refs": ["src_annual_2025"],
        "sources": [{"kind": "figure", "id": "fig-001"}],
    }


def write_test_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAQAAABeK7cBAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
    )


def test_outline_only_renderer_creates_reopenable_pptx(tmp_path):
    outline = load("examples/slide_outline_valid.json")
    layout_map = load("templates/template_layout_map.json")
    output = tmp_path / "outline-only.pptx"

    render_presentation(
        outline,
        layout_map,
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
        output,
    )

    presentation = Presentation(output)
    assert len(presentation.slides) == len(outline["slides"])
    assert presentation.slides[0].shapes[2].name == "cover_title"
    assert presentation.slides[0].element.cSld.find(qn("p:bg")) is not None
    visual_slide = presentation.slides[1]
    assert not any(shape.has_chart for shape in visual_slide.shapes)
    assert not any(shape.has_table for shape in visual_slide.shapes)


def test_outline_only_renderer_replaces_template_table_with_empty_anchor(tmp_path):
    outline = load("examples/generated/002544_2025-10-28_slide_outline.json")
    layout_map = load("templates/template_layout_map.json")
    output = tmp_path / "no-template-sample-data.pptx"

    render_presentation(
        outline,
        layout_map,
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
        output,
    )

    forecast_slide = Presentation(output).slides[6]
    assert not any(shape.has_table for shape in forecast_slide.shapes)
    assert any(shape.name == "forecast_table" for shape in forecast_slide.shapes)


def test_renderer_supports_chart_and_table_bindings(tmp_path):
    outline = load("examples/slide_outline_valid.json")
    layout_map = load("templates/template_layout_map.json")
    chart = load("examples/visualization_valid.json")
    table = load("examples/visualization_table_valid.json")
    output = tmp_path / "visuals.pptx"

    render_presentation(
        outline,
        layout_map,
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
        output,
        visualizations_by_slide={"slide_002": [chart, table]},
    )

    presentation = Presentation(output)
    visual_slide = presentation.slides[1]
    assert any(shape.has_chart for shape in visual_slide.shapes)
    rendered_chart = next(shape.chart for shape in visual_slide.shapes if shape.has_chart)
    assert all(
        0 <= int(axis_id.get("val")) <= 0x7FFFFFFF
        for axis_id in rendered_chart._chartSpace.xpath(".//c:axId | .//c:crossAx")
    )
    forecast_table = next(shape for shape in visual_slide.shapes if shape.name == "forecast_table")
    assert forecast_table.table.cell(0, 0).text == "项目"
    assert forecast_table.table.cell(1, 0).text == "营业收入"


def test_compiled_renderer_clears_unbound_template_example_metrics():
    presentation = Presentation(
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx"
    )
    slide = presentation.slides[2]

    _clear_unbound_template_metrics(slide, [])

    metric_shapes = [
        shape
        for shape in slide.shapes
        if shape.name.startswith("metric_") and shape.has_text_frame
    ]
    assert metric_shapes
    assert all(not shape.text.strip() for shape in metric_shapes)


def test_renderer_rejects_unknown_visualization_slide(tmp_path):
    outline = load("examples/slide_outline_valid.json")
    layout_map = load("templates/template_layout_map.json")
    chart = load("examples/visualization_valid.json")

    with pytest.raises(RenderError, match="unknown slide_id"):
        render_presentation(
            outline,
            layout_map,
            PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
            tmp_path / "invalid.pptx",
            visualizations_by_slide={"slide_missing": [chart]},
        )


def test_renderer_inserts_image_shape_from_safe_relative_path(tmp_path, monkeypatch):
    outline = load("examples/slide_outline_valid.json")
    layout_map = load("templates/template_layout_map.json")
    image_path = tmp_path / "assets" / "figures" / "fig-001.png"
    write_test_png(image_path)
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "image.pptx"

    render_presentation(
        outline,
        layout_map,
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
        output,
        visualizations_by_slide={
            "slide_002": [image_visualization("assets/figures/fig-001.png")]
        },
    )

    presentation = Presentation(output)
    pictures = [
        shape
        for shape in presentation.slides[1].shapes
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE
    ]
    assert len(pictures) == 1
    assert pictures[0].name == "image_fig-001"
    assert pictures[0].width > Inches(3)


def test_figure_page_uses_full_width_image_only_layout_and_asset_root(tmp_path):
    outline = load("examples/slide_outline_valid.json")
    layout_map = load("templates/template_layout_map.json")
    slide = outline["slides"][1]
    slide["slide_type"] = "figure_page"
    slide["title"] = "公司 PDT 星通站实现一站多能"
    slide["bullet_points"] = []
    slide["evidence_refs"] = [{"kind": "figure", "id": "fig-007"}]
    slide["visual_candidates"] = []
    bundle = tmp_path / "document_bundle"
    image_path = bundle / "assets" / "figures" / "fig-007.png"
    write_test_png(image_path)
    output = tmp_path / "figure-page.pptx"
    figure_image = image_visualization("assets/figures/fig-007.png")
    figure_image["source"]["id"] = "fig-007"
    figure_image["sources"][0]["id"] = "fig-007"

    render_presentation(
        outline,
        layout_map,
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
        output,
        visualizations_by_slide={
            "slide_002": [figure_image]
        },
        asset_root=bundle,
    )

    presentation = Presentation(output)
    pictures = [
        shape
        for shape in presentation.slides[1].shapes
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE
    ]
    assert len(pictures) == 1
    assert pictures[0].name == "image_fig-007"
    assert pictures[0].width > Inches(10)
    assert not {
        "logic_chart_panel",
        "logic_takeaway",
        "logic_conclusion",
    } & {shape.name for shape in presentation.slides[1].shapes}


def test_renderer_fails_when_image_asset_does_not_exist(tmp_path, monkeypatch):
    outline = load("examples/slide_outline_valid.json")
    layout_map = load("templates/template_layout_map.json")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RenderError, match="image asset does not exist"):
        render_presentation(
            outline,
            layout_map,
            PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
            tmp_path / "missing.pptx",
            visualizations_by_slide={
                "slide_002": [image_visualization("assets/figures/missing.png")]
            },
        )


def test_renderer_rejects_image_path_escape(tmp_path):
    outline = load("examples/slide_outline_valid.json")
    layout_map = load("templates/template_layout_map.json")

    with pytest.raises(RenderError, match="schema validation failed"):
        render_presentation(
            outline,
            layout_map,
            PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
            tmp_path / "escape.pptx",
            visualizations_by_slide={
                "slide_002": [image_visualization("../../outside.png")]
            },
        )


def test_compiled_renderer_executes_adaptive_canvas_with_image(tmp_path):
    template = PROJECT_ROOT / "templates/financial_report_template_v1.pptx"
    image_path = tmp_path / "assets" / "figures" / "fig-001.png"
    write_test_png(image_path)
    plan = {
        "schema_version": "2.0.0",
        "plan_id": "plan_0123456789abcdef",
        "source": {
            "outline_sha256": "a" * 64,
            "manifest_sha256": "b" * 64,
        },
        "template": {
            "profile_id": "financial-report-v1",
            "profile_sha256": "c" * 64,
            "file": template.name,
            "sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
        },
        "asset_root": str(tmp_path),
        "visualizations": [
            {
                "visualization_id": "visual_image",
                "slide_id": "slide_001",
                "visual_type": "image",
                "data": image_visualization("assets/figures/fig-001.png"),
            }
        ],
        "slides": [
            {
                "slide_id": "slide_001",
                "slide_mode": "adaptive_canvas",
                "abstract_layout_id": "visual_right_text_left",
                "base": {
                    "mode": "blank",
                    "slide_layout_index": 0,
                    "clear_placeholders": True,
                    "width_in": 13.333,
                    "height_in": 7.5,
                    "background_color": "FFFFFF",
                },
                "operations": [
                    {
                        "op": "add_text_box",
                        "element_id": "title",
                        "target": {
                            "bounds_in": {
                                "left": 0.8,
                                "top": 0.5,
                                "width": 11.7,
                                "height": 0.7,
                            }
                        },
                        "value": "Adaptive title",
                        "style": {
                            "font_family": "Microsoft YaHei",
                            "font_size_pt": 24,
                            "bold": True,
                            "color": "1F2937",
                        },
                    },
                    {
                        "op": "render_image",
                        "slot_id": "primary_visual",
                        "target": {
                            "bounds_in": {
                                "left": 6.8,
                                "top": 1.5,
                                "width": 5.7,
                                "height": 5.0,
                            }
                        },
                        "visualization_id": "visual_image",
                    },
                ],
            }
        ],
    }
    output = tmp_path / "adaptive.pptx"
    render_compiled_plan(plan, template_path=template, output_path=output)

    presentation = Presentation(output)
    assert len(presentation.slides) == 1
    assert any(
        shape.shape_type == MSO_SHAPE_TYPE.PICTURE
        for shape in presentation.slides[0].shapes
    )

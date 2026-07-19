from __future__ import annotations

import json
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.oxml.ns import qn

from ppt_engine.renderer import RenderError, render_presentation


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load(relative: str):
    return json.loads((PROJECT_ROOT / relative).read_text(encoding="utf-8"))


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
    forecast_table = next(shape for shape in visual_slide.shapes if shape.name == "forecast_table")
    assert forecast_table.table.cell(0, 0).text == "项目"
    assert forecast_table.table.cell(1, 0).text == "营业收入"


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

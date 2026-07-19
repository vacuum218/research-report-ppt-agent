from __future__ import annotations

import json
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.dml.color import RGBColor
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
    cover_title = next(
        shape for shape in presentation.slides[0].shapes if shape.name == "cover_title"
    )
    cover_run = cover_title.text_frame.paragraphs[0].runs[0]
    assert cover_run.font.color.rgb == RGBColor(0xFF, 0xFF, 0xFF)

    rendered_text = "\n".join(
        shape.text
        for slide in presentation.slides
        for shape in slide.shapes
        if getattr(shape, "has_text_frame", False)
    )
    assert "基本盘恢复" not in rendered_text
    assert "+18.4%" not in rendered_text


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


def test_formal_outline_clears_template_examples_and_limits_valuation_text(tmp_path):
    outline = load("examples/generated/002544_2025-10-28_slide_outline.json")
    layout_map = load("templates/template_layout_map.json")
    output = tmp_path / "formal-outline.pptx"

    render_presentation(
        outline,
        layout_map,
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
        output,
    )

    presentation = Presentation(output)
    rendered_text = "\n".join(
        shape.text
        for slide in presentation.slides
        for shape in slide.shapes
        if getattr(shape, "has_text_frame", False)
    )
    assert "[XX]亿元" not in rendered_text
    assert "行业规模指数（示例）" not in rendered_text

    for slide in presentation.slides:
        thesis = next((shape for shape in slide.shapes if shape.name == "thesis"), None)
        if thesis is not None:
            assert len(thesis.text) <= 45

    for slide_number in (8, 9):
        slide = presentation.slides[slide_number - 1]
        headline = next(shape for shape in slide.shapes if shape.name == "valuation_headline")
        bullets = next(shape for shape in slide.shapes if shape.name == "valuation_bullets")
        conclusion = next(
            shape for shape in slide.shapes if shape.name == "valuation_conclusion_text"
        )
        assert len(headline.text) <= 30
        assert all(len(paragraph.text) <= 30 for paragraph in bullets.text_frame.paragraphs)
        assert len(conclusion.text) <= 35


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

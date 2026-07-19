from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from visualization_generator.generate_visualizations import (
    bindings_from_artifacts,
    generate_visualizations,
    preflight_visualizations,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _slide(visual_type: str, description: str) -> dict:
    return {
        "slide_id": "slide_006",
        "page_role": "content",
        "slide_type": "industry_analysis" if visual_type == "chart" else "financial_forecast",
        "title": "收入增长趋势" if visual_type == "chart" else "盈利预测表",
        "key_message": "收入持续增长",
        "bullet_points": [],
        "source_refs": ["src_report"],
        "layout_hint": "chart" if visual_type == "chart" else "table",
        "visual_candidates": [
            {
                "candidate_id": "visual_001",
                "type": visual_type,
                "description": description,
                "source_refs": ["src_report"],
            }
        ],
    }


def _document() -> dict:
    return {
        "blocks": [
            {
                "block_id": "block_0001",
                "type": "table",
                "section_path": [{"title": "收入与盈利预测"}],
                "columns": ["项目", "2023A", "2024A", "2025E"],
                "rows": [
                    ["营业收入", "100", "120", "150"],
                    ["归母净利润", "10", "14", "20"],
                ],
            }
        ]
    }


def test_chart_candidate_generates_schema_valid_chart_from_document_table():
    outline = {"slides": [_slide("chart", "展示营业收入增长趋势")]}
    artifacts, issues = generate_visualizations(outline, _document())

    assert not issues
    assert len(artifacts) == 1
    chart = artifacts[0].data
    assert chart["chart_type"] == "line"
    assert chart["categories"] == ["2023A", "2024A", "2025E"]
    assert chart["series"][0] == {"name": "营业收入", "values": [100.0, 120.0, 150.0]}
    schema = json.loads((PROJECT_ROOT / "schemas/visualization.schema.json").read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(schema).iter_errors(chart))


def test_table_candidate_preserves_existing_table_data_and_schema():
    outline = {"slides": [_slide("table", "收入与盈利预测表")]}
    artifacts, issues = generate_visualizations(outline, _document())

    assert not issues
    table = artifacts[0].data
    assert table["columns"] == ["项目", "2023A", "2024A", "2025E"]
    assert table["rows"][0] == ["营业收入", 100, 120, 150]
    assert table["source_refs"] == ["src_report"]


def test_missing_traceable_data_is_reported_without_fabricating_visualization():
    outline = {"slides": [_slide("chart", "不存在的数据趋势")]}
    artifacts, issues = generate_visualizations(outline, {"blocks": []})

    assert artifacts == []
    assert issues[0].reason == "no_traceable_source_data"


def test_preflight_warns_for_missing_chart_and_clears_after_generation():
    outline = {"slides": [_slide("chart", "展示营业收入增长趋势")]}
    layout_map = json.loads(
        (PROJECT_ROOT / "templates/template_layout_map.json").read_text(encoding="utf-8")
    )

    warnings = preflight_visualizations(outline, layout_map, {})
    assert [(item.slide_id, item.required_visual, item.layout_id, item.reason) for item in warnings] == [
        ("slide_006", "chart", "industry_outlook", "no_chart_visualization_data")
    ]

    artifacts, _ = generate_visualizations(outline, _document())
    assert preflight_visualizations(outline, layout_map, bindings_from_artifacts(artifacts)) == []

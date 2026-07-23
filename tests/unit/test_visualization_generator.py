from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from document_intelligence import build_figure_inventory, build_snapshot
from outline_generator.bundle_validation import validate_outline_evidence
from visualization_generator.generate_visualizations import (
    bindings_from_artifacts,
    generate_visualizations,
    preflight_visualizations,
)
from visualization_generator.planning import VisualizationPlanningError, plan_visualizations


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _slide(visual_type: str | None, description: str, evidence_refs: list[dict]) -> dict:
    candidates = [] if visual_type is None else [
        {
            "candidate_id": "visual_001",
            "type": visual_type,
            "description": description,
            "source_refs": ["src_report"],
        }
    ]
    return {
        "slide_id": "slide_006",
        "page_role": "content",
        "slide_type": (
            "figure_page"
            if visual_type is None
            else "industry_analysis"
            if visual_type == "chart"
            else "financial_forecast"
        ),
        "title": "收入增长趋势" if visual_type == "chart" else "盈利预测表",
        "key_message": "收入持续增长",
        "bullet_points": [],
        "source_refs": ["src_report"],
        "evidence_refs": evidence_refs,
        "layout_hint": visual_type or "image",
        "visual_candidates": candidates,
    }


def _snapshot(tmp_path: Path, *, table_status: str = "complete"):
    figure_path = tmp_path / "assets" / "figures" / "fig-001.png"
    figure_path.parent.mkdir(parents=True)
    figure_path.write_bytes(b"png")
    table_crop = tmp_path / "assets" / "tables" / "table-001.png"
    table_crop.parent.mkdir(parents=True)
    table_crop.write_bytes(b"png")
    blocks = [
        {
            "id": "p001-b001",
            "page": 1,
            "type": "paragraph",
            "text_raw": "2021年收入10亿元，2022年收入15亿元，2023年收入22亿元。",
            "bbox": None,
            "parser_order": 0,
            "reading_order": 0,
            "section_id": "sec-1",
            "source_type": "test",
        },
        {
            "id": "p001-b002",
            "page": 1,
            "type": "table",
            "text_raw": "收入与盈利预测",
            "bbox": None,
            "parser_order": 1,
            "reading_order": 1,
            "section_id": "sec-1",
            "source_type": "test",
            "table_id": "table-001",
        },
    ]
    document = {
        "document": {"id": "report", "title": "Report", "page_count": 1, "source_sha256": "0" * 64, "source_file": "report.pdf", "source_format": "pdf"},
        "pages": [{"id": "p001", "page": 1, "width": 100, "height": 100, "block_ids": [item["id"] for item in blocks]}],
        "blocks": blocks,
        "sections": [{"id": "sec-1", "level": 1, "title_block_id": "p001-b001", "parent_id": None, "child_section_ids": [], "content_block_ids": [item["id"] for item in blocks]}],
        "tables": [{
            "id": "table-001",
            "section_id": "sec-1",
            "caption_block_ids": [],
            "footnote_block_ids": [],
            "fragments": [{"page": 1, "bbox": [0, 0, 10, 10], "crop_path": "assets/tables/table-001.png"}],
            "structure_raw": {"format": "grid", "columns": ["项目", "2021A", "2022A", "2023A"], "rows": [["营业收入", "10", "15", "22"], ["净利润", "1", "2", "3"]]},
            "status": table_status,
            "issues": [],
            "continuation_block_ids": [],
            "source_block_id": "p001-b002",
        }],
        "figures": [{"id": "fig-001", "page": 1, "section_id": "sec-1", "bbox": [0, 0, 10, 10], "asset_path": "assets/figures/fig-001.png", "source_block_id": "p001-b001", "caption_block_ids": ["p001-b001"]}],
        "reading_order": [item["id"] for item in blocks],
    }
    return build_snapshot(document, tmp_path)


def test_chart_candidate_generates_line_chart_from_native_bundle_table(tmp_path):
    snapshot = _snapshot(tmp_path)
    outline = {"slides": [_slide("chart", "展示营业收入增长趋势", [{"kind": "table", "id": "table-001"}])]}
    artifacts, issues = generate_visualizations(outline, snapshot)

    assert not issues
    chart = artifacts[0].data
    assert chart["chart_type"] == "line"
    assert chart["categories"] == ["2021A", "2022A", "2023A"]
    assert chart["series"][0] == {"name": "营业收入", "values": [10.0, 15.0, 22.0]}
    assert chart["sources"] == [{"kind": "table", "id": "table-001"}]


def test_chart_values_are_extracted_from_native_block(tmp_path):
    snapshot = _snapshot(tmp_path)
    outline = {"slides": [_slide("chart", "展示收入增长趋势", [{"kind": "block", "id": "p001-b001"}])]}
    artifacts, issues = generate_visualizations(outline, snapshot)

    assert not issues
    assert artifacts[0].data["series"][0]["values"] == [10.0, 15.0, 22.0]
    assert artifacts[0].data["sources"] == [{"kind": "block", "id": "p001-b001"}]


def test_table_candidate_preserves_complete_bundle_table(tmp_path):
    snapshot = _snapshot(tmp_path)
    outline = {"slides": [_slide("table", "收入与盈利预测表", [{"kind": "table", "id": "table-001"}])]}
    artifacts, issues = generate_visualizations(outline, snapshot)

    assert not issues
    assert artifacts[0].data["columns"] == ["项目", "2021A", "2022A", "2023A"]
    assert artifacts[0].data["rows"][0] == ["营业收入", 10, 15, 22]


def test_table_candidate_reconciles_an_unambiguous_same_section_table(tmp_path):
    snapshot = _snapshot(tmp_path)
    outline = {
        "slides": [
            _slide(
                "table",
                "收入与盈利预测表",
                [{"kind": "block", "id": "p001-b001"}],
            )
        ]
    }
    artifacts, issues = generate_visualizations(outline, snapshot)

    assert not issues
    assert artifacts[0].data["sources"] == [{"kind": "table", "id": "table-001"}]


def test_image_uses_existing_bundle_figure_asset(tmp_path):
    snapshot = _snapshot(tmp_path)
    outline = {"slides": [_slide(None, "展示原始研报图片", [{"kind": "figure", "id": "fig-001"}])]}
    artifacts, issues = generate_visualizations(outline, snapshot)

    assert not issues
    assert artifacts[0].data["type"] == "image"
    assert artifacts[0].data["source"] == {"kind": "figure", "id": "fig-001"}
    assert artifacts[0].data["asset_path"] == "assets/figures/fig-001.png"


def test_figure_inventory_resolves_context_asset_and_order(tmp_path):
    snapshot = _snapshot(tmp_path)

    inventory = build_figure_inventory(snapshot)

    assert inventory[0]["figure_id"] == "fig-001"
    assert inventory[0]["section_id"] == "sec-1"
    assert inventory[0]["available"] is True
    assert inventory[0]["selectable"] is True
    assert inventory[0]["order"] == 1
    assert inventory[0]["caption"].startswith("2021年收入")


def test_figure_pages_must_follow_pdf_order(tmp_path):
    snapshot = _snapshot(tmp_path)
    second_path = tmp_path / "assets" / "figures" / "fig-002.png"
    second_path.write_bytes(b"png")
    document = dict(snapshot.document_json)
    document["figures"] = [
        dict(snapshot.figures_by_id["fig-001"], source_content_index=1),
        {
            **dict(snapshot.figures_by_id["fig-001"]),
            "id": "fig-002",
            "asset_path": "assets/figures/fig-002.png",
            "source_content_index": 2,
        },
    ]
    ordered_snapshot = build_snapshot(document, tmp_path)

    def figure_slide(identity):
        slide = _slide(None, identity, [{"kind": "figure", "id": identity}])
        slide["section_ref"] = "sec-1"
        return slide

    issues = validate_outline_evidence(
        {"slides": [figure_slide("fig-002"), figure_slide("fig-001")]},
        ordered_snapshot,
    )

    assert any(issue.code == "FIGURE.ORDER" for issue in issues)


def test_image_only_table_is_emitted_only_as_image(tmp_path):
    snapshot = _snapshot(tmp_path, table_status="image_only")
    outline = {"slides": [_slide("table", "原始表格", [{"kind": "table", "id": "table-001"}])]}
    artifacts, issues = generate_visualizations(outline, snapshot)

    assert not issues
    assert artifacts[0].data["type"] == "image"
    assert artifacts[0].data["source"] == {"kind": "table", "id": "table-001"}


def test_unknown_llm_evidence_fails_in_planning(tmp_path):
    snapshot = _snapshot(tmp_path)
    outline = {"slides": [_slide("chart", "不存在的数据", [{"kind": "table", "id": "table-999"}])]}

    with pytest.raises(VisualizationPlanningError, match="unknown table"):
        plan_visualizations(outline, snapshot)


def test_planning_rejects_llm_generated_values(tmp_path):
    snapshot = _snapshot(tmp_path)
    slide = _slide("chart", "收入趋势", [{"kind": "block", "id": "p001-b001"}])
    slide["visual_candidates"][0]["values"] = [999]

    with pytest.raises(VisualizationPlanningError, match="deterministic data fields"):
        plan_visualizations({"slides": [slide]}, snapshot)


def test_preflight_accepts_image_only_layout(tmp_path):
    snapshot = _snapshot(tmp_path)
    outline = {"slides": [_slide(None, "展示原始研报图片", [{"kind": "figure", "id": "fig-001"}])]}
    layout_map = json.loads((PROJECT_ROOT / "templates/template_layout_map.json").read_text(encoding="utf-8"))
    artifacts, _ = generate_visualizations(outline, snapshot)
    warnings = preflight_visualizations(outline, layout_map, bindings_from_artifacts(artifacts))

    assert warnings == []


def test_generated_chart_is_schema_valid(tmp_path):
    snapshot = _snapshot(tmp_path)
    outline = {"slides": [_slide("chart", "展示营业收入增长趋势", [{"kind": "table", "id": "table-001"}])]}
    artifacts, _ = generate_visualizations(outline, snapshot)
    schema = json.loads((PROJECT_ROOT / "schemas/visualization.schema.json").read_text(encoding="utf-8"))

    assert not list(Draft202012Validator(schema).iter_errors(artifacts[0].data))

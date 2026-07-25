from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ppt_engine.compiler import LayoutCompileError, compile_layout_plan
from tools.build_template_profile import build_template_profile
from visualization_generator.manifest import (
    canonical_sha256,
    load_visualization_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load(relative: str) -> dict:
    return json.loads((PROJECT_ROOT / relative).read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def compile_fixture(
    tmp_path: Path,
    *,
    outline: dict | None = None,
    table_visualization: dict | None = None,
) -> dict:
    outline = outline or load("examples/slide_outline_valid.json")
    profile = build_template_profile(
        load("templates/template_layout_map.json"),
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
    )
    chart = load("examples/visualization_valid.json")
    table = table_visualization or load(
        "examples/visualization_table_valid.json"
    )
    write_json(tmp_path / "chart.json", chart)
    write_json(tmp_path / "table.json", table)
    bundle = tmp_path / "bundle"
    bundle.mkdir(exist_ok=True)
    manifest = {
        "schema_version": "3.0.0",
        "outline_sha256": canonical_sha256(outline),
        "document_source_sha256": "a" * 64,
        "asset_root": str(bundle),
        "bindings": [
            {
                "slide_id": "slide_002",
                "visualization_id": "visual_chart",
                "visual_type": "chart",
                "sources": [{"kind": "table", "id": "table-001"}],
                "visualization_file": "chart.json",
            },
            {
                "slide_id": "slide_002",
                "visualization_id": "visual_table",
                "visual_type": "table",
                "sources": [{"kind": "table", "id": "table-001"}],
                "visualization_file": "table.json",
            },
        ],
    }
    write_json(tmp_path / "manifest.json", manifest)
    loaded = load_visualization_manifest(tmp_path / "manifest.json")
    return compile_layout_plan(outline, profile, loaded)


def test_compiler_emits_complete_deterministic_plan(tmp_path):
    first = compile_fixture(tmp_path)
    second = compile_fixture(tmp_path)

    assert first["plan_id"] == second["plan_id"]
    assert first["slides"][0]["layout_id"] == "cover"
    forecast = first["slides"][1]
    assert forecast["layout_id"] == "earnings_forecast"
    assert [operation["op"] for operation in forecast["operations"][-2:]] == [
        "render_table",
        "render_chart",
    ]
    assert {item["visualization_id"] for item in first["visualizations"]} == {
        "visual_chart",
        "visual_table",
    }


def test_compiler_rejects_table_that_exceeds_every_available_slot(tmp_path):
    table = load("examples/visualization_table_valid.json")
    table["rows"] = [
        [f"指标{index}", index, index + 1, index + 2]
        for index in range(19)
    ]

    with pytest.raises(LayoutCompileError, match=r"exceeds .*max_rows"):
        compile_fixture(tmp_path, table_visualization=table)


def test_compiler_rejects_manifest_for_different_outline(tmp_path):
    outline = load("examples/slide_outline_valid.json")
    profile = build_template_profile(
        load("templates/template_layout_map.json"),
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_json(
        tmp_path / "manifest.json",
        {
            "schema_version": "3.0.0",
            "outline_sha256": "b" * 64,
            "document_source_sha256": "a" * 64,
            "asset_root": str(bundle),
            "bindings": [],
        },
    )
    loaded = load_visualization_manifest(tmp_path / "manifest.json")

    with pytest.raises(LayoutCompileError, match="different Outline"):
        compile_layout_plan(outline, profile, loaded)


def test_compiler_does_not_require_semantic_mapping_when_structure_is_supported(tmp_path):
    outline = load("examples/slide_outline_valid.json")
    outline["slides"][1]["slide_type"] = "unknown_type"
    # Bypass Outline schema only to isolate the resolver boundary.
    profile = build_template_profile(
        load("templates/template_layout_map.json"),
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_json(
        tmp_path / "manifest.json",
        {
            "schema_version": "3.0.0",
            "outline_sha256": canonical_sha256(outline),
            "document_source_sha256": "a" * 64,
            "asset_root": str(bundle),
            "bindings": [],
        },
    )
    loaded = load_visualization_manifest(tmp_path / "manifest.json")
    permissive_outline_schema = {"type": "object"}

    plan = compile_layout_plan(
        outline,
        profile,
        loaded,
        outline_schema=permissive_outline_schema,
    )
    assert plan["slides"][1]["slide_mode"] in {
        "exact_template",
        "adaptive_canvas",
    }


def test_compiler_filters_layout_with_missing_required_visual(tmp_path):
    outline = load("examples/slide_outline_valid.json")
    profile = build_template_profile(
        load("templates/template_layout_map.json"),
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_json(
        tmp_path / "manifest.json",
        {
            "schema_version": "3.0.0",
            "outline_sha256": canonical_sha256(outline),
            "document_source_sha256": "a" * 64,
            "asset_root": str(bundle),
            "bindings": [],
        },
    )
    loaded = load_visualization_manifest(tmp_path / "manifest.json")

    # With no generated visualization, the outline falls back to the configured
    # text layout and remains compilable; force the table layout to test its
    # explicit capability requirement.
    changed = copy.deepcopy(profile)
    changed["layout_resolution"]["slide_type_defaults"]["financial_forecast"] = (
        "earnings_forecast"
    )
    plan = compile_layout_plan(outline, changed, loaded)
    forecast = plan["slides"][1]
    assert forecast.get("layout_id") != "earnings_forecast"
    assert not any(
        operation["op"] in {"render_chart", "render_table", "render_image"}
        for operation in forecast["operations"]
    )


def test_compiler_uses_adaptive_canvas_when_no_exact_layout_covers_content(tmp_path):
    outline = load("examples/slide_outline_valid.json")
    outline["slides"][1]["slide_type"] = "company_overview"
    profile = build_template_profile(
        load("templates/template_layout_map.json"),
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
    )
    image = load(
        "output/manual-002544/figure_aware_run/visualizations/"
        "slide_003__visual_001.json"
    )
    write_json(tmp_path / "image.json", image)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_json(
        tmp_path / "manifest.json",
        {
            "schema_version": "3.0.0",
            "outline_sha256": canonical_sha256(outline),
            "document_source_sha256": "a" * 64,
            "asset_root": str(bundle),
            "bindings": [
                {
                    "slide_id": "slide_002",
                    "visualization_id": "visual_image",
                    "visual_type": "image",
                    "sources": [{"kind": "table", "id": "table-002"}],
                    "visualization_file": "image.json",
                }
            ],
        },
    )
    plan = compile_layout_plan(
        outline,
        profile,
        load_visualization_manifest(tmp_path / "manifest.json"),
    )
    adaptive = plan["slides"][1]
    assert adaptive["slide_mode"] == "adaptive_canvas"
    assert adaptive["abstract_layout_id"] in {
        "visual_left_text_right",
        "visual_right_text_left",
    }
    assert {operation["op"] for operation in adaptive["operations"]} == {
        "add_text_box",
        "add_bullet_list",
        "render_image",
    }


def test_compiler_auto_paginates_text_without_dropping_visuals(tmp_path):
    outline = load("examples/slide_outline_valid.json")
    source_slide = outline["slides"][1]
    source_slide["key_message"] = "核心结论：" + "盈利能力持续改善。" * 18
    source_slide["bullet_points"] = [
        f"假设{index}：" + "收入与利润预测依据。" * 8
        for index in range(1, 6)
    ]

    plan = compile_fixture(tmp_path, outline=outline)
    source_pages = [
        slide
        for slide in plan["slides"]
        if slide["source_slide_id"] == "slide_002"
    ]

    assert len(source_pages) >= 2
    assert source_pages[0]["slide_id"] == "slide_002"
    assert source_pages[1]["slide_id"] == "slide_002__cont_02"
    assert [page["continuation_index"] for page in source_pages] == list(
        range(1, len(source_pages) + 1)
    )
    visual_ops = {
        "render_chart",
        "render_table",
        "render_image",
    }
    assert any(
        operation["op"] in visual_ops
        for operation in source_pages[0]["operations"]
    )
    assert all(
        operation["op"] not in visual_ops
        for page in source_pages[1:]
        for operation in page["operations"]
    )

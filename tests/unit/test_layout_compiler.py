from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ppt_engine.compiler import LayoutCompileError, compile_layout_plan
from ppt_engine.layout_resolver import LayoutResolutionError
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


def compile_fixture(tmp_path: Path, *, outline: dict | None = None) -> dict:
    outline = outline or load("examples/slide_outline_valid.json")
    profile = build_template_profile(
        load("templates/template_layout_map.json"),
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
    )
    chart = load("examples/visualization_valid.json")
    table = load("examples/visualization_table_valid.json")
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


def test_compiler_rejects_profile_fallback_resolution(tmp_path):
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

    with pytest.raises(LayoutResolutionError, match="no Template Profile layout rule"):
        compile_layout_plan(
            outline,
            profile,
            loaded,
            outline_schema=permissive_outline_schema,
        )


def test_compiler_rejects_missing_required_visual(tmp_path):
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
    with pytest.raises(LayoutCompileError, match="required chart slot"):
        compile_layout_plan(outline, changed, loaded)

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ppt_engine.compiled_plan import validate_compiled_plan


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def schema() -> dict:
    return json.loads(
        (PROJECT_ROOT / "schemas/compiled_layout_plan.schema.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture()
def plan() -> dict:
    return {
        "schema_version": "1.0.0",
        "plan_id": "plan_0123456789abcdef",
        "source": {
            "outline_sha256": "a" * 64,
            "manifest_sha256": "b" * 64,
        },
        "template": {
            "profile_id": "financial-report-v1",
            "profile_sha256": "c" * 64,
            "file": "template.pptx",
            "sha256": "d" * 64,
        },
        "asset_root": "bundle",
        "visualizations": [
            {
                "visualization_id": "visual_001",
                "slide_id": "slide_001",
                "visual_type": "chart",
                "data": {
                    "chart_type": "line",
                    "categories": ["2024", "2025"],
                    "series": [{"name": "收入", "values": [1, 2]}],
                },
            }
        ],
        "slides": [
            {
                "slide_id": "slide_001",
                "layout_id": "chart_text",
                "template_slide": 9,
                "operations": [
                    {
                        "op": "set_text",
                        "binding_id": "title",
                        "target": {"name": "title"},
                        "value": "收入增长",
                    },
                    {
                        "op": "render_chart",
                        "slot_id": "chart",
                        "target": {"name": "chart_panel"},
                        "visualization_id": "visual_001",
                    },
                ],
            }
        ],
    }


def test_valid_compiled_plan_passes(schema, plan):
    assert validate_compiled_plan(plan, schema) == []


def test_unknown_operation_fails(schema, plan):
    value = copy.deepcopy(plan)
    value["slides"][0]["operations"][0]["op"] = "guess_layout"
    assert validate_compiled_plan(value, schema)


def test_unknown_visualization_reference_fails(schema, plan):
    value = copy.deepcopy(plan)
    value["slides"][0]["operations"][1]["visualization_id"] = "visual_missing"
    assert any(
        "unknown visualization_id" in error
        for error in validate_compiled_plan(value, schema)
    )


def test_visualization_cannot_be_consumed_twice(schema, plan):
    value = copy.deepcopy(plan)
    value["slides"][0]["operations"].append(
        copy.deepcopy(value["slides"][0]["operations"][1])
    )
    assert any(
        "more than once" in error for error in validate_compiled_plan(value, schema)
    )


def test_visualization_type_must_match_operation(schema, plan):
    value = copy.deepcopy(plan)
    value["slides"][0]["operations"][1]["op"] = "render_table"
    assert any(
        "cannot consume" in error for error in validate_compiled_plan(value, schema)
    )


def test_unconsumed_visualization_fails(schema, plan):
    value = copy.deepcopy(plan)
    value["slides"][0]["operations"] = value["slides"][0]["operations"][:1]
    assert any(
        "not consumed" in error for error in validate_compiled_plan(value, schema)
    )

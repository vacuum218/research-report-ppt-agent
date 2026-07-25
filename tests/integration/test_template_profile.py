from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from tools.build_template_profile import (
    build_template_profile,
    validate_template_profile,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load(relative: str) -> dict:
    return json.loads((PROJECT_ROOT / relative).read_text(encoding="utf-8"))


def test_canonical_layout_map_builds_schema_valid_template_profile():
    layout_map = load("templates/template_layout_map.json")
    schema = load("schemas/template_profile.schema.json")
    profile = build_template_profile(
        layout_map,
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
    )

    Draft202012Validator(schema).validate(profile)
    assert validate_template_profile(profile, schema) == []
    assert set(profile["layouts"]) == set(layout_map["layouts"])
    assert "fallback_layout" not in profile["layout_resolution"]
    assert profile["template"]["sha256"]


def test_profile_exposes_only_explicit_visual_slots():
    profile = build_template_profile(
        load("templates/template_layout_map.json"),
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
    )

    image_layout = profile["layouts"]["image_only_layout"]
    assert image_layout["slots"] == [
        {
            "slot_id": "image",
            "kind": "image",
            "operation": "render_image",
            "required": True,
            "target": {
                "bounds_in": {
                    "left": 0.75,
                    "top": 1.35,
                    "width": 11.83,
                    "height": 5.2,
                }
            },
            "capacity": {"max_items": 1},
        }
    ]
    assert not profile["layouts"]["executive_summary"]["slots"]


def test_profile_matches_current_renderer_capability_boundary():
    profile = build_template_profile(
        load("templates/template_layout_map.json"),
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
    )

    assert [slot["kind"] for slot in profile["layouts"]["business_structure"]["slots"]] == [
        "chart",
        "chart",
    ]
    assert [slot["kind"] for slot in profile["layouts"]["earnings_forecast"]["slots"]] == [
        "table",
        "chart",
    ]
    assert not profile["layouts"]["competitive_landscape"]["slots"]


def test_adaptive_style_tokens_are_induced_from_template_shapes():
    profile = build_template_profile(
        load("templates/template_layout_map.json"),
        PROJECT_ROOT / "templates/financial_report_template_v1.pptx",
    )

    styles = profile["adaptive_canvas"]["style_tokens"]
    assert styles["slide_title"]["font_family"] == "Microsoft YaHei"
    assert styles["slide_title"]["font_size_pt"] == 27.0
    assert styles["slide_title"]["color"] == "102A43"
    assert styles["key_message"]["font_size_pt"] == 16.0
    assert styles["body_text"]["font_size_pt"] >= 14.0
    assert styles["table"]["font_family"] == styles["body_text"]["font_family"]
    assert styles["primary_visual"]["series_colors"][:3] == [
        "2F75B5",
        "ED7D31",
        "70AD47",
    ]
    assert styles["primary_visual"]["legend_position"] == "bottom"
    assert styles["primary_visual"]["gap_width"] == 65
    assert styles["table"]["header_fill"] == "102A43"
    assert styles["table"]["stripe_fill"] == "F5F7FA"
    assert styles["table"]["max_rows"] == 18
    assert styles["table"]["max_columns"] == 8

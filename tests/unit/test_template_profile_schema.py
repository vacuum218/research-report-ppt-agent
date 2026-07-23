from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def validator() -> Draft202012Validator:
    schema = json.loads(
        (PROJECT_ROOT / "schemas/template_profile.schema.json").read_text(
            encoding="utf-8"
        )
    )
    return Draft202012Validator(schema)


@pytest.fixture()
def profile() -> dict:
    return {
        "schema_version": "1.0.0",
        "profile_id": "financial-report-v1",
        "template": {
            "file": "financial_report_template_v1.pptx",
            "sha256": "a" * 64,
            "slide_count": 16,
            "width_in": 13.3333,
            "height_in": 7.5,
        },
        "supported_operations": [
            "set_text",
            "render_chart",
            "render_image",
        ],
        "layout_resolution": {
            "page_role_overrides": {"title": "cover"},
            "semantic_visual_rules": [],
            "slide_type_defaults": {"summary": "summary"},
        },
        "layouts": {
            "summary": {
                "template_slide": 3,
                "description": "summary",
                "bindings": [
                    {
                        "binding_id": "title",
                        "kind": "text",
                        "operation": "set_text",
                        "source": "slide.title",
                        "required": True,
                        "target": {"name": "title"},
                    }
                ],
                "slots": [
                    {
                        "slot_id": "chart",
                        "kind": "chart",
                        "operation": "render_chart",
                        "required": False,
                        "target": {"name": "chart_panel"},
                        "capacity": {"max_items": 1},
                    },
                    {
                        "slot_id": "image",
                        "kind": "image",
                        "operation": "render_image",
                        "required": False,
                        "target": {
                            "bounds_in": {
                                "left": 1,
                                "top": 1,
                                "width": 5,
                                "height": 4,
                            }
                        },
                        "capacity": {"max_items": 1},
                    },
                ],
            }
        },
    }


def assert_invalid(validator: Draft202012Validator, value: dict) -> None:
    assert list(validator.iter_errors(value))


def test_valid_template_profile_passes(validator, profile):
    validator.validate(profile)


def test_profile_rejects_fallback_layout(validator, profile):
    value = copy.deepcopy(profile)
    value["layout_resolution"]["fallback_layout"] = "summary"
    assert_invalid(validator, value)


def test_visual_slot_requires_explicit_target(validator, profile):
    value = copy.deepcopy(profile)
    del value["layouts"]["summary"]["slots"][0]["target"]
    assert_invalid(validator, value)


def test_slot_operation_must_match_kind(validator, profile):
    value = copy.deepcopy(profile)
    value["layouts"]["summary"]["slots"][0]["operation"] = "render_image"
    assert_invalid(validator, value)


def test_profile_rejects_unknown_operation(validator, profile):
    value = copy.deepcopy(profile)
    value["supported_operations"].append("guess_image_position")
    assert_invalid(validator, value)


def test_repeated_binding_requires_explicit_targets(validator, profile):
    value = copy.deepcopy(profile)
    value["layouts"]["summary"]["bindings"][0].update(
        {
            "kind": "repeated_text",
            "operation": "set_repeated_text",
        }
    )
    value["layouts"]["summary"]["bindings"][0].pop("target")
    assert_invalid(validator, value)

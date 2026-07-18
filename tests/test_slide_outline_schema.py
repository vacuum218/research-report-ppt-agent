import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "slide_outline.schema.json"
EXAMPLE_PATH = PROJECT_ROOT / "examples" / "slide_outline_valid.json"


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def valid_outline():
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator(schema):
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def assert_invalid(validator, instance):
    assert list(validator.iter_errors(instance))


def test_valid_outline_passes(validator, valid_outline):
    validator.validate(valid_outline)


@pytest.mark.parametrize(
    "missing_field",
    [
        "slide_id",
        "title",
        "slide_type",
        "page_role",
        "key_message",
        "bullet_points",
        "source_refs",
        "visual_candidates",
    ],
)
def test_missing_required_slide_field_fails(
    validator, valid_outline, missing_field
):
    instance = copy.deepcopy(valid_outline)
    del instance["slides"][1][missing_field]

    assert_invalid(validator, instance)


def test_invalid_slide_type_fails(validator, valid_outline):
    instance = copy.deepcopy(valid_outline)
    instance["slides"][1]["slide_type"] = "chart"

    assert_invalid(validator, instance)


def test_invalid_page_role_fails(validator, valid_outline):
    instance = copy.deepcopy(valid_outline)
    instance["slides"][1]["page_role"] = "two_column"

    assert_invalid(validator, instance)


@pytest.mark.parametrize(
    "invalid_source_refs",
    [
        "not-an-array",
        [{}],
        [{"text": "", "section": "盈利预测", "location": "第2段"}],
        [{"text": "有效原文", "section": "盈利预测"}],
    ],
)
def test_invalid_source_refs_structure_fails(
    validator, valid_outline, invalid_source_refs
):
    instance = copy.deepcopy(valid_outline)
    instance["slides"][1]["source_refs"] = invalid_source_refs

    assert_invalid(validator, instance)


def test_visual_candidate_extension_fields_are_allowed(
    validator, valid_outline
):
    instance = copy.deepcopy(valid_outline)
    candidate = instance["slides"][1]["visual_candidates"][0]
    candidate["future_extraction_status"] = "pending"
    candidate["future_options"] = {"show_labels": True}

    validator.validate(instance)

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "visualization.schema.json"
EXAMPLE_PATH = PROJECT_ROOT / "examples" / "visualization_valid.json"


@pytest.fixture(scope="module")
def validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.fixture(scope="module")
def valid_chart():
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def valid_table():
    return {
        "title": "盈利预测",
        "unit": "亿元",
        "columns": ["项目", "2025E", "2026E"],
        "rows": [["收入", 100, 120], ["归母净利润", 10, 13]],
        "source_refs": ["src_calc_forecast"],
    }


@pytest.fixture(scope="module")
def valid_image():
    return {
        "type": "image",
        "title": "公司产品图",
        "source": {"kind": "figure", "id": "fig-001"},
        "asset_path": "assets/figures/fig-001.png",
        "source_refs": ["src_report"],
        "sources": [{"kind": "figure", "id": "fig-001"}],
    }


def assert_invalid(validator, instance):
    assert list(validator.iter_errors(instance))


def test_valid_chart_passes(validator, valid_chart):
    validator.validate(valid_chart)


def test_valid_table_passes(validator, valid_table):
    validator.validate(valid_table)


def test_valid_image_passes(validator, valid_image):
    validator.validate(valid_image)


def test_image_rejects_parent_path(validator, valid_image):
    instance = copy.deepcopy(valid_image)
    instance["asset_path"] = "../outside.png"
    assert_invalid(validator, instance)


@pytest.mark.parametrize(
    "field",
    ["chart_type", "title", "unit", "categories", "series", "source_refs"],
)
def test_chart_missing_required_field_fails(validator, valid_chart, field):
    instance = copy.deepcopy(valid_chart)
    del instance[field]
    assert_invalid(validator, instance)


@pytest.mark.parametrize("field", ["title", "columns", "rows", "source_refs"])
def test_table_missing_required_field_fails(validator, valid_table, field):
    instance = copy.deepcopy(valid_table)
    del instance[field]
    assert_invalid(validator, instance)


@pytest.mark.parametrize(
    "invalid_source_refs",
    [
        [],
        "src_001",
        ["invalid_id"],
        ["src_001", "src_001"],
        [{"source_id": "src_001"}],
    ],
)
def test_invalid_source_refs_fail(
    validator, valid_chart, invalid_source_refs
):
    instance = copy.deepcopy(valid_chart)
    instance["source_refs"] = invalid_source_refs
    assert_invalid(validator, instance)


def test_chart_rejects_table_fields(validator, valid_chart):
    instance = copy.deepcopy(valid_chart)
    instance["columns"] = ["项目", "2025E"]
    assert_invalid(validator, instance)


def test_table_rejects_chart_fields(validator, valid_table):
    instance = copy.deepcopy(valid_table)
    instance["chart_type"] = "line"
    assert_invalid(validator, instance)

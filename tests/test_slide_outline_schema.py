import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "slide_outline.schema.json"
EXAMPLE_PATH = PROJECT_ROOT / "examples" / "slide_outline_valid.json"


@pytest.fixture(scope="module")
def valid_outline():
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def assert_invalid(validator, instance):
    assert list(validator.iter_errors(instance))


def test_valid_outline_and_metadata_pass(validator, valid_outline):
    validator.validate(valid_outline)


@pytest.mark.parametrize(
    "metadata_field",
    [
        "company",
        "company_name",
        "stock_code",
        "industry",
        "report_title",
        "report_date",
        "source_file",
    ],
)
def test_missing_metadata_field_fails(
    validator, valid_outline, metadata_field
):
    instance = copy.deepcopy(valid_outline)
    del instance["metadata"][metadata_field]
    assert_invalid(validator, instance)


def test_valid_sources_pass(validator, valid_outline):
    validator.validate(valid_outline)
    source_ids = [source["source_id"] for source in valid_outline["sources"]]
    assert len(source_ids) == len(set(source_ids))


@pytest.mark.parametrize(
    "invalid_source",
    [
        {},
        {"source_id": "invalid", "type": "annual_report", "title": "年报"},
        {"source_id": "src_001", "type": "unknown", "title": "未知来源"},
    ],
)
def test_invalid_source_fails(validator, valid_outline, invalid_source):
    instance = copy.deepcopy(valid_outline)
    instance["sources"] = [invalid_source]
    assert_invalid(validator, instance)


@pytest.mark.parametrize(
    "slide_type",
    [
        "company_overview",
        "industry_analysis",
        "business_model",
        "core_competitiveness",
        "financial_forecast",
        "valuation_analysis",
        "investment_risk",
        "summary",
    ],
)
def test_business_slide_types_pass(validator, valid_outline, slide_type):
    instance = copy.deepcopy(valid_outline)
    instance["slides"][1]["slide_type"] = slide_type
    validator.validate(instance)


@pytest.mark.parametrize("invalid_type", ["chart", "table", "two_column", "content"])
def test_layout_or_role_slide_type_fails(
    validator, valid_outline, invalid_type
):
    instance = copy.deepcopy(valid_outline)
    instance["slides"][1]["slide_type"] = invalid_type
    assert_invalid(validator, instance)


@pytest.mark.parametrize("page_role", ["title", "section", "content", "closing"])
def test_page_roles_pass(validator, valid_outline, page_role):
    instance = copy.deepcopy(valid_outline)
    instance["slides"][1]["page_role"] = page_role
    validator.validate(instance)


def test_invalid_page_role_fails(validator, valid_outline):
    instance = copy.deepcopy(valid_outline)
    instance["slides"][1]["page_role"] = "chart_page"
    assert_invalid(validator, instance)


def test_layout_hint_is_present_but_unrestricted(validator, valid_outline):
    instance = copy.deepcopy(valid_outline)
    assert "layout_hint" in instance["slides"][1]
    instance["slides"][1]["layout_hint"] = "future_semantic_layout_suggestion"
    validator.validate(instance)


@pytest.mark.parametrize(
    "invalid_source_refs",
    [
        "src_001",
        ["invalid_id"],
        ["src_001", "src_001"],
        [{"text": "不再允许内嵌原文"}],
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


@pytest.mark.parametrize(
    "forbidden_field",
    ["values", "categories", "series", "columns", "rows"],
)
def test_visual_candidate_rejects_visualization_data(
    validator, valid_outline, forbidden_field
):
    instance = copy.deepcopy(valid_outline)
    candidate = instance["slides"][1]["visual_candidates"][0]
    candidate[forbidden_field] = []
    assert_invalid(validator, instance)

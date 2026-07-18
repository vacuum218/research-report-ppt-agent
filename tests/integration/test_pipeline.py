from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from research_report_ppt.parsing import parse_file
from research_report_ppt.outline.generator import (
    build_messages,
    build_request,
    load_json,
    load_text,
)
from research_report_ppt.validation.outline import validate_outline
from research_report_ppt.validation.visualization import validate_visualization


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_parser_output_matches_parsed_document_schema():
    parsed = parse_file(PROJECT_ROOT / "tests" / "fixtures" / "table_sample.md")
    schema = load_json(
        PROJECT_ROOT / "schemas" / "parsed_document.schema.json",
        "parsed document schema",
    )

    Draft202012Validator(schema).validate(parsed)


def test_outline_prompt_uses_canonical_schema_and_semantic_boundary():
    parsed = parse_file(PROJECT_ROOT / "tests" / "fixtures" / "heading_paragraph.md")
    schema = load_json(
        PROJECT_ROOT / "schemas" / "slide_outline.schema.json",
        "outline schema",
    )
    examples = load_json(
        PROJECT_ROOT / "prompts" / "outline_few_shot_examples.json",
        "few-shot examples",
    )
    prompt = load_text(
        PROJECT_ROOT / "prompts" / "outline_system_prompt.md",
        "system prompt",
    )

    messages = build_messages(
        parsed,
        schema,
        examples,
        prompt,
        max_input_chars=20_000,
    )
    request = build_request(
        messages,
        model="test-model",
        max_tokens=1_000,
        thinking="disabled",
        reasoning_effort="low",
    )

    assert request["response_format"] == {"type": "json_object"}
    assert '"const":"1.0.0"' in messages[0]["content"]
    assert "不得输出 `layout_id`" in messages[0]["content"]


def test_canonical_example_passes_integrated_outline_validator():
    outline = json.loads(
        (PROJECT_ROOT / "examples" / "slide_outline_valid.json").read_text(
            encoding="utf-8"
        )
    )
    schema = json.loads(
        (PROJECT_ROOT / "schemas" / "slide_outline.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert validate_outline(outline, schema) == []


def test_integrated_validator_rejects_unknown_source_reference():
    outline = json.loads(
        (PROJECT_ROOT / "examples" / "slide_outline_valid.json").read_text(
            encoding="utf-8"
        )
    )
    schema = json.loads(
        (PROJECT_ROOT / "schemas" / "slide_outline.schema.json").read_text(
            encoding="utf-8"
        )
    )
    outline["slides"][1]["source_refs"] = ["src_missing"]

    issues = validate_outline(outline, schema)

    assert any(issue.code == "SOURCE.UNKNOWN_REFERENCE" for issue in issues)


def test_visualization_example_passes_integrated_validator():
    visualization = json.loads(
        (PROJECT_ROOT / "examples" / "visualization_valid.json").read_text(
            encoding="utf-8"
        )
    )
    schema = json.loads(
        (PROJECT_ROOT / "schemas" / "visualization.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert validate_visualization(visualization, schema) == []


def test_visualization_validator_rejects_series_length_mismatch():
    visualization = json.loads(
        (PROJECT_ROOT / "examples" / "visualization_valid.json").read_text(
            encoding="utf-8"
        )
    )
    schema = json.loads(
        (PROJECT_ROOT / "schemas" / "visualization.schema.json").read_text(
            encoding="utf-8"
        )
    )
    visualization["series"][0]["values"].pop()

    issues = validate_visualization(visualization, schema)

    assert any(issue.code == "CHART.LENGTH_MISMATCH" for issue in issues)

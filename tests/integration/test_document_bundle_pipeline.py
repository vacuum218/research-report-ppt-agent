from __future__ import annotations

import json
from pathlib import Path

import fitz
from jsonschema import Draft202012Validator

from document_bundle.bundle import build_from_raw
from document_bundle.markdown import build_from_markdown
from document_intelligence import generate_chunks, load_document_intelligence
from outline_generator.generate_outline import build_messages, load_json, load_text
from outline_generator.llm_understanding import preview_context_memory
from compat.structured_content.from_document_bundle import from_document_bundle, load_structured_content
from visualization_generator.generate_visualizations import generate_visualizations


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW = PROJECT_ROOT / "tests" / "document_bundle" / "fixtures" / "raw"


def _fixture_pdf(path: Path) -> None:
    document = fitz.open()
    document.new_page(width=600, height=800)
    document.new_page(width=600, height=800)
    document.save(path)
    document.close()


def test_pdf_bundle_drives_outline_context_directly(tmp_path):
    pdf = tmp_path / "fixture.pdf"
    _fixture_pdf(pdf)
    bundle = tmp_path / "document_bundle"
    document, validation = build_from_raw(pdf, RAW, bundle, "fixture-id")

    structured = from_document_bundle(document)
    schema = load_json(PROJECT_ROOT / "schemas" / "parsed_document.schema.json", "schema")
    Draft202012Validator(schema).validate(structured)
    assert validation["status"] == "passed"
    assert structured["document"]["source_format"] == "pdf"
    assert any(block["type"] == "table" and block["columns"] for block in structured["blocks"])

    outline_schema = load_json(PROJECT_ROOT / "schemas" / "slide_outline.schema.json", "outline schema")
    examples = load_json(PROJECT_ROOT / "prompts" / "outline_few_shot_examples.json", "few shot")
    prompt = load_text(PROJECT_ROOT / "prompts" / "outline_system_prompt.md", "prompt")
    snapshot = load_document_intelligence(bundle, PROJECT_ROOT / "schemas" / "document_bundle.schema.json")
    chunks = generate_chunks(snapshot, 20_000)
    messages = build_messages(
        snapshot,
        [preview_context_memory(chunk) for chunk in chunks],
        outline_schema,
        examples,
        prompt,
    )
    assert "runtime_context_memories" in messages[1]["content"]
    assert "parsed_document" not in messages[1]["content"]


def test_visualization_generator_accepts_document_bundle_directly(tmp_path):
    document, _ = build_from_markdown(
        PROJECT_ROOT / "tests" / "fixtures" / "table_sample.md",
        tmp_path / "document_bundle",
    )
    outline = {
        "slides": [
            {
                "slide_id": "slide_001",
                    "title": "年度指标",
                    "key_message": "收入利润",
                "section": "测试",
                "source_refs": ["src_fixture"],
                "visual_candidates": [
                    {
                        "candidate_id": "visual_001",
                        "type": "table",
                            "description": "年度 收入 利润",
                        "source_refs": ["src_fixture"],
                    }
                ],
            }
        ]
    }
    artifacts, issues = generate_visualizations(outline, document)
    assert not issues
    assert artifacts[0].data["columns"]


def test_markdown_builds_bundle_and_round_trips_to_structured_content(tmp_path):
    bundle = tmp_path / "document_bundle"
    document, validation = build_from_markdown(
        PROJECT_ROOT / "tests" / "fixtures" / "table_sample.md",
        bundle,
    )
    schema = json.loads((PROJECT_ROOT / "schemas" / "document_bundle.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(document)
    structured = load_structured_content(bundle)
    parsed_schema = json.loads((PROJECT_ROOT / "schemas" / "parsed_document.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(parsed_schema).validate(structured)
    assert validation["status"] == "passed"
    assert structured["statistics"]["table_count"] == 1
    assert (bundle / "raw" / "document.md").is_file()

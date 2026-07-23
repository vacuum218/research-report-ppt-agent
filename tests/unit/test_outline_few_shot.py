from __future__ import annotations

import json
from pathlib import Path

from document_bundle.markdown import build_from_markdown
from document_intelligence import load_document_intelligence
from outline_generator.few_shot import (
    CASE_LIBRARY_VERSION,
    detect_case_features,
    load_case_library,
    select_cases,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CASE_ROOT = PROJECT_ROOT / "prompts" / "outline_cases"
BUNDLE_SCHEMA = PROJECT_ROOT / "schemas" / "document_bundle.schema.json"


def _snapshot(tmp_path: Path, markdown: str):
    source = tmp_path / "source.md"
    source.write_text(markdown, encoding="utf-8")
    bundle = tmp_path / "document_bundle"
    build_from_markdown(source, bundle)
    return load_document_intelligence(bundle, BUNDLE_SCHEMA)


def test_case_directory_loads_schema_validated_unique_cases():
    library = load_case_library(CASE_ROOT)

    assert library["schema_version"] == CASE_LIBRARY_VERSION
    assert library["source_mode"] == "case_directory"
    assert library["max_selected_cases"] == 4
    case_ids = [case["id"] for case in library["cases"]]
    assert len(case_ids) == len(set(case_ids))
    assert {
        "source_title_fidelity",
        "numbered_topic_bullets",
        "original_figure_page",
        "financial_forecast_intent",
        "no_unsupported_valuation",
    }.issubset(case_ids)


def test_selector_detects_numbered_content_and_returns_stable_trace(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        (
            "# 1.1 公司业务布局\n\n"
            "公司以信息通信领域为核心战略布局新兴产业。"
            "1）公网通信业务。2）专网通信与智慧应用业务。3）智能制造业务。\n"
        ),
    )
    library = load_case_library(CASE_ROOT)

    first = select_cases(snapshot, library)
    second = select_cases(snapshot, library)

    assert first == second
    selected_ids = [
        item["case_id"] for item in first.trace["selected_cases"]
    ]
    assert selected_ids[:2] == [
        "source_title_fidelity",
        "numbered_topic_bullets",
    ]
    assert "has_numbered_paragraph" in first.trace["detected_features"]
    assert [
        case["id"] for case in first.prompt_payload["cases"]
    ] == selected_ids


def test_selector_does_not_inject_unmatched_financial_or_figure_cases(tmp_path):
    snapshot = _snapshot(
        tmp_path,
        "# 公司概况\n\n公司主要从事通信信息技术服务。\n",
    )
    selection = select_cases(snapshot, load_case_library(CASE_ROOT))

    selected_ids = {
        item["case_id"] for item in selection.trace["selected_cases"]
    }
    assert selected_ids == {"source_title_fidelity"}
    assert "financial_forecast_intent" not in selected_ids
    assert "original_figure_page" not in selected_ids
    assert "has_figures" not in detect_case_features(snapshot)


def test_legacy_monolithic_few_shot_file_remains_supported():
    legacy_path = PROJECT_ROOT / "prompts" / "outline_few_shot_examples.json"
    source = json.loads(legacy_path.read_text(encoding="utf-8"))
    library = load_case_library(legacy_path)

    assert library["source_mode"] == "legacy_file"
    assert len(library["cases"]) == len(source["examples"])
    assert library["max_selected_cases"] == len(source["examples"])

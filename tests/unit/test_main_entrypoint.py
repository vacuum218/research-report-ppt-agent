from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from document_bundle.markdown import build_from_markdown


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_main(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_top_level_help_lists_commands():
    result = run_main("--help")

    assert result.returncode == 0
    assert "generate-outline" in result.stdout
    assert "generate-visualizations" in result.stdout
    assert "validate-outline" in result.stdout
    assert "validate-layout-map" in result.stdout
    assert "render-ppt" in result.stdout
    assert "run-pipeline" in result.stdout


def test_render_command_warns_when_visual_candidate_has_no_data(tmp_path):
    result = run_main(
        "render-ppt",
        str(PROJECT_ROOT / "examples" / "slide_outline_valid.json"),
        "-o",
        str(tmp_path / "warning-demo.pptx"),
    )

    assert result.returncode == 0
    assert "[visualization-warning]" in result.stderr
    assert "slide_id=slide_002" in result.stderr
    assert "required_visual=chart" in result.stderr
    assert "layout_id=financial_review" in result.stderr
    assert "reason=no_chart_visualization_data" in result.stderr


def test_unknown_command_returns_nonzero():
    result = run_main("unknown-command")

    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_outline_dry_run_does_not_require_api_key(tmp_path):
    bundle = tmp_path / "document_bundle"
    request_path = tmp_path / "request.json"
    build_from_markdown(
        PROJECT_ROOT / "tests" / "fixtures" / "heading_paragraph.md",
        bundle,
    )

    result = run_main(
        "generate-outline",
        str(bundle),
        "--dry-run",
        "--request-output",
        str(request_path),
    )

    assert result.returncode == 0
    assert request_path.is_file()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["pipeline"] == "report_map_then_deck_storyboard_then_outline_adapter"
    assert request["context_mode"] == "direct"
    assert request["context_input_chars"] <= request["direct_planning_max_chars"]
    assert request["compression_requests"] == []
    planning_payload = json.loads(
        request["report_map_request"]["messages"][1]["content"]
    )
    assert planning_payload["runtime_context_memories"][0]["context_mode"] == "direct"
    assert planning_payload["runtime_context_memories"][0]["raw_context"]
    assert request["report_map_request"]["model"] == "deepseek-v4-pro"
    assert request["report_map_request"]["response_format"] == {"type": "json_object"}
    assert request["deck_storyboard_request"]["response_format"] == {"type": "json_object"}


def test_outline_dry_run_can_force_context_compression(tmp_path):
    bundle = tmp_path / "document_bundle"
    request_path = tmp_path / "request.json"
    build_from_markdown(
        PROJECT_ROOT / "tests" / "fixtures" / "heading_paragraph.md",
        bundle,
    )

    result = run_main(
        "generate-outline",
        str(bundle),
        "--direct-planning-max-chars",
        "0",
        "--dry-run",
        "--request-output",
        str(request_path),
    )

    assert result.returncode == 0
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["pipeline"] == "report_map_then_deck_storyboard_then_outline_adapter"
    assert request["context_mode"] == "compressed"
    assert request["compression_requests"]


def test_validation_command_keeps_summary_format():
    result = run_main(
        "validate-outline",
        str(PROJECT_ROOT / "examples" / "slide_outline_valid.json"),
        "--quiet",
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "VALID: 0 error(s), 0 warning(s)"

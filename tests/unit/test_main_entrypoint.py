from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from document_parser import parse_file


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
    parsed_path = tmp_path / "parsed.json"
    request_path = tmp_path / "request.json"
    parsed = parse_file(PROJECT_ROOT / "tests" / "fixtures" / "heading_paragraph.md")
    parsed_path.write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = run_main(
        "generate-outline",
        str(parsed_path),
        "--dry-run",
        "--request-output",
        str(request_path),
    )

    assert result.returncode == 0
    assert request_path.is_file()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["model"] == "deepseek-v4-pro"
    assert request["response_format"] == {"type": "json_object"}


def test_validation_command_keeps_summary_format():
    result = run_main(
        "validate-outline",
        str(PROJECT_ROOT / "examples" / "slide_outline_valid.json"),
        "--quiet",
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "VALID: 0 error(s), 0 warning(s)"

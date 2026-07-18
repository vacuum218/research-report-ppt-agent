from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from research_report_ppt.cli import build_parser, main
from research_report_ppt.parsing import parse_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "command",
    [
        "parse-report",
        "generate-outline",
        "inspect-template",
        "build-layout-map",
        "validate-outline",
        "validate-visualization",
        "parse-template",
    ],
)
def test_each_subcommand_has_real_help(command, capsys):
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args([command, "--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "usage:" in output
    assert "args" not in output


def test_top_level_source_checkout_help():
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "--help"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "generate-outline" in result.stdout


def test_invalid_cli_arguments_return_nonzero():
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "generate-outline"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "required" in result.stderr


def test_outline_dry_run_does_not_require_api_key(tmp_path, monkeypatch):
    parsed_path = tmp_path / "parsed.json"
    request_path = tmp_path / "request.json"
    parsed = parse_file(PROJECT_ROOT / "tests" / "fixtures" / "heading_paragraph.md")
    parsed_path.write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    result = main(
        [
            "generate-outline",
            str(parsed_path),
            "--dry-run",
            "--request-output",
            str(request_path),
        ]
    )

    assert result == 0
    assert request_path.is_file()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert request["model"] == "deepseek-v4-pro"
    assert request["response_format"] == {"type": "json_object"}


def test_validation_cli_keeps_summary_format(capsys):
    result = main(
        [
            "validate-outline",
            str(PROJECT_ROOT / "examples" / "slide_outline_valid.json"),
            "--quiet",
        ]
    )

    assert result == 0
    assert capsys.readouterr().out.strip() == "VALID: 0 error(s), 0 warning(s)"

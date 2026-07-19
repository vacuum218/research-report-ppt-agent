from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("from document_parser import parse_file; print(parse_file.__name__)", "parse_file"),
        (
            "from outline_generator import OutlineGenerationError; "
            "print(OutlineGenerationError.__name__)",
            "OutlineGenerationError",
        ),
        (
            "from ppt_template_parser import PPTTemplateParser; "
            "print(PPTTemplateParser.__name__)",
            "PPTTemplateParser",
        ),
        (
            "from tools.validate_outline import validate_outline; "
            "print(validate_outline.__name__)",
            "validate_outline",
        ),
        (
            "from ppt_engine import LayoutResolver; print(LayoutResolver.__name__)",
            "LayoutResolver",
        ),
    ],
)
def test_module_imports(statement, expected):
    result = subprocess.run(
        [sys.executable, "-c", statement],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == expected
    assert "deprecated" not in result.stderr


@pytest.mark.parametrize(
    "script",
    [
        "document_parser/parse_report.py",
        "outline_generator/generate_outline.py",
        "tools/validate_outline.py",
        "tools/validate_visualization.py",
        "tools/inspect_template.py",
        "tools/build_layout_map.py",
    ],
)
def test_module_scripts_expose_help(script):
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / script), "--help"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout

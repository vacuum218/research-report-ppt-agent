from __future__ import annotations

import re
from pathlib import Path

from research_report_ppt.paths import PATHS
from research_report_ppt.validation.outline import load_json, validate_outline


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_canonical_resource_paths_exist():
    assert PATHS.root == PROJECT_ROOT
    assert PATHS.parsed_document_schema.is_file()
    assert PATHS.slide_outline_schema.is_file()
    assert PATHS.visualization_schema.is_file()
    assert PATHS.outline_system_prompt.is_file()
    assert PATHS.outline_few_shot.is_file()
    assert PATHS.financial_template.is_file()


def test_declared_repository_directories_exist():
    for relative in (
        "src/research_report_ppt",
        "schemas",
        "prompts",
        "templates",
        "examples/generated",
        "data/reports/agent",
        "data/reports/human",
        "data/references",
        "docs/architecture",
        "docs/specs",
        "docs/planning",
        "docs/quality",
        "docs/reviews",
        "docs/delivery",
        "docs/archive",
        "tests/unit",
        "tests/integration",
        "tests/fixtures",
    ):
        assert (PROJECT_ROOT / relative).is_dir(), relative


def test_formal_outline_remains_valid():
    outline = load_json(
        PROJECT_ROOT
        / "examples"
        / "generated"
        / "002544_2025-10-28_slide_outline.json",
        "formal outline",
    )
    schema = load_json(PATHS.slide_outline_schema, "outline schema")

    assert validate_outline(outline, schema) == []


def test_critical_moved_paths_exist_and_old_paths_are_gone():
    assert (PROJECT_ROOT / "data/reports/agent/002544_2025-10-28.md").is_file()
    assert (
        PROJECT_ROOT
        / "docs/planning/研报PPT生成项目_周计划与任务跟踪.xlsx"
    ).is_file()
    assert (PROJECT_ROOT / "docs/specs/template_layout.md").is_file()
    assert not (PROJECT_ROOT / "测试研报").exists()
    assert not (PROJECT_ROOT / "reference").exists()


def test_local_markdown_links_resolve():
    markdown_files = [PROJECT_ROOT / "README.md", *sorted((PROJECT_ROOT / "docs").rglob("*.md"))]
    broken: list[str] = []

    for markdown_file in markdown_files:
        content = markdown_file.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(content):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_text = target.split("#", 1)[0]
            if not path_text:
                continue
            resolved = (markdown_file.parent / path_text).resolve()
            if not resolved.exists():
                broken.append(f"{markdown_file.relative_to(PROJECT_ROOT)} -> {target}")

    assert broken == []

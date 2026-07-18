"""Canonical repository resource paths.

The source checkout remains the authority for schemas, prompts, and templates.
Installed distributions can provide the same files below
``<sys.prefix>/share/research-report-ppt`` via ``pyproject.toml`` data-files.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


RESOURCE_ENV = "RESEARCH_REPORT_PPT_ROOT"


def _candidates() -> Iterable[Path]:
    configured = os.getenv(RESOURCE_ENV)
    if configured:
        yield Path(configured).expanduser()

    module_path = Path(__file__).resolve()
    yield from module_path.parents
    yield Path(sys.prefix) / "share" / "research-report-ppt"


def find_project_root() -> Path:
    """Return the first directory containing all canonical resource folders."""

    for candidate in _candidates():
        if all((candidate / name).is_dir() for name in ("schemas", "prompts", "templates")):
            return candidate.resolve()
    raise RuntimeError(
        "Cannot locate schemas/prompts/templates. Run from a source checkout or set "
        f"{RESOURCE_ENV} to the repository/resource root."
    )


@dataclass(frozen=True)
class ResourcePaths:
    root: Path

    @property
    def schemas(self) -> Path:
        return self.root / "schemas"

    @property
    def prompts(self) -> Path:
        return self.root / "prompts"

    @property
    def templates(self) -> Path:
        return self.root / "templates"

    @property
    def parsed_document_schema(self) -> Path:
        return self.schemas / "parsed_document.schema.json"

    @property
    def slide_outline_schema(self) -> Path:
        return self.schemas / "slide_outline.schema.json"

    @property
    def visualization_schema(self) -> Path:
        return self.schemas / "visualization.schema.json"

    @property
    def outline_system_prompt(self) -> Path:
        return self.prompts / "outline_system_prompt.md"

    @property
    def outline_few_shot(self) -> Path:
        return self.prompts / "outline_few_shot_examples.json"

    @property
    def financial_template(self) -> Path:
        return self.templates / "financial_report_template_v1.pptx"


PATHS = ResourcePaths(find_project_root())

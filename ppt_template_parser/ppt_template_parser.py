"""Compatibility wrapper for :mod:`research_report_ppt.templates.parser`."""

from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research_report_ppt.compat import warn_legacy
from research_report_ppt.templates.parser import PPTTemplateParser

warn_legacy("ppt_template_parser.ppt_template_parser", "research_report_ppt.templates.parser")

__all__ = ["PPTTemplateParser"]

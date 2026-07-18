"""Compatibility wrapper for :mod:`research_report_ppt.templates.theme`."""

from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research_report_ppt.compat import warn_legacy
from research_report_ppt.templates.theme import PPTThemeParser

warn_legacy("ppt_template_parser.theme_parser", "research_report_ppt.templates.theme")

__all__ = ["PPTThemeParser"]

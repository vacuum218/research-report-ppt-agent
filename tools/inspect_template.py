#!/usr/bin/env python3
"""Compatibility wrapper for template inspection."""

from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research_report_ppt.compat import legacy_main, legacy_parse_args, warn_legacy
from research_report_ppt.templates.inspection import *  # noqa: F403

warn_legacy("tools.inspect_template", "research_report_ppt.templates.inspection")


def parse_args(argv=None):
    return legacy_parse_args("inspect-template", argv)


def main(argv=None) -> int:
    return legacy_main("inspect-template", argv)


if __name__ == "__main__":
    raise SystemExit(main())

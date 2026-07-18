#!/usr/bin/env python3
"""Compatibility wrapper for :mod:`research_report_ppt.parsing.report`."""

from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research_report_ppt.compat import legacy_main, legacy_parse_args, warn_legacy
from research_report_ppt.parsing.report import *  # noqa: F403

warn_legacy("document_parser.parse_report", "research_report_ppt.parsing.report")


def parse_args(argv=None):
    return legacy_parse_args("parse-report", argv)


def main(argv=None) -> int:
    return legacy_main("parse-report", argv)


if __name__ == "__main__":
    raise SystemExit(main())

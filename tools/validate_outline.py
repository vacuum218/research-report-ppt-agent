#!/usr/bin/env python3
"""Compatibility wrapper for outline validation."""

from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research_report_ppt.compat import legacy_main, legacy_parse_args, warn_legacy
from research_report_ppt.validation.outline import *  # noqa: F403

warn_legacy("tools.validate_outline", "research_report_ppt.validation.outline")


def parse_args(argv=None):
    return legacy_parse_args("validate-outline", argv)


def main(argv=None) -> int:
    return legacy_main("validate-outline", argv)


if __name__ == "__main__":
    raise SystemExit(main())

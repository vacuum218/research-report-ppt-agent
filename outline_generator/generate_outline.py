#!/usr/bin/env python3
"""Compatibility wrapper for :mod:`research_report_ppt.outline.generator`."""

from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research_report_ppt.compat import legacy_main, legacy_parse_args, warn_legacy
from research_report_ppt.outline.generator import *  # noqa: F403

warn_legacy("outline_generator.generate_outline", "research_report_ppt.outline.generator")


def parse_args(argv=None):
    return legacy_parse_args("generate-outline", argv)


def main(argv=None) -> int:
    return legacy_main("generate-outline", argv)


if __name__ == "__main__":
    raise SystemExit(main())

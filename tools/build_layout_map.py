#!/usr/bin/env python3
"""Compatibility wrapper for semantic layout-map construction."""

from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research_report_ppt.compat import legacy_main, legacy_parse_args, warn_legacy
from research_report_ppt.templates.layout_map import *  # noqa: F403

warn_legacy("tools.build_layout_map", "research_report_ppt.templates.layout_map")


def parse_args(argv=None):
    return legacy_parse_args("build-layout-map", argv)


def main(argv=None) -> int:
    return legacy_main("build-layout-map", argv)


if __name__ == "__main__":
    raise SystemExit(main())

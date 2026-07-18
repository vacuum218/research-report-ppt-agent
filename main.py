#!/usr/bin/env python3
"""Backward-compatible source-checkout entry point."""

from __future__ import annotations

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from research_report_ppt.cli import build_parser, main  # noqa: E402

__all__ = ["build_parser", "main"]


if __name__ == "__main__":
    raise SystemExit(main())

"""Helpers for legacy module and script entry points."""

from __future__ import annotations

import warnings
import sys
from typing import Optional, Sequence


def warn_legacy(old_path: str, new_path: str) -> None:
    warnings.warn(
        f"{old_path} is deprecated and will be removed after Week 4; use {new_path}",
        DeprecationWarning,
        stacklevel=3,
    )


def legacy_main(
    command: str,
    argv: Optional[Sequence[str]] = None,
) -> int:
    from .cli import main

    forwarded = list(argv) if argv is not None else sys.argv[1:]
    return main([command, *forwarded])


def legacy_parse_args(
    command: str,
    argv: Optional[Sequence[str]] = None,
):
    from .cli import parse_command_args

    forwarded = list(argv) if argv is not None else sys.argv[1:]
    return parse_command_args(command, forwarded)

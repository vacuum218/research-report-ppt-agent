"""CLI validation for the semantic template Layout Map."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .layout_resolver import LayoutResolutionError, load_layout_map, validate_layout_map


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate template_layout_map.json")
    parser.add_argument("layout_map", type=Path)
    args = parser.parse_args(argv)
    try:
        errors = validate_layout_map(load_layout_map(args.layout_map))
    except LayoutResolutionError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    for error in errors:
        print(f"[ERROR] {error}")
    print(f"{'VALID' if not errors else 'INVALID'}: {len(errors)} error(s)")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

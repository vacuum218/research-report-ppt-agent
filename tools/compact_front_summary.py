"""Compact pre-contents summary text in an existing Slide Outline."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from document_intelligence import load_document_intelligence
from document_intelligence.loader import DocumentIntelligenceError
from outline_generator.front_matter import compact_front_matter_summary_slides


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_SCHEMA = PROJECT_ROOT / "schemas/document_bundle.schema.json"


def _load_outline(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Slide Outline root must be an object")
    return value


def _write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        prefix="outline_",
        dir=path.parent,
        delete=False,
    ) as handle:
        temporary_path = Path(handle.name)
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    try:
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compact an existing pre-contents summary without calling an LLM"
    )
    parser.add_argument("outline", type=Path)
    parser.add_argument("document", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument(
        "--bundle-schema",
        type=Path,
        default=DEFAULT_BUNDLE_SCHEMA,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        outline = _load_outline(args.outline)
        snapshot = load_document_intelligence(args.document, args.bundle_schema)
        changes = compact_front_matter_summary_slides(outline, snapshot)
        _write_atomic(args.output, outline)
        print(f"Compacted summary slides: {changes}")
        print(f"Created outline: {args.output}")
        return 0
    except (DocumentIntelligenceError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

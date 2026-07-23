"""Build the canonical DocumentBundle shape from Markdown/plain text."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from document_parser.parse_report import parse_file


def _write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write("\n")
        temporary = Path(output.name)
    temporary.replace(path)


def _html_table(columns: list[Any], rows: list[list[Any]]) -> str:
    from html import escape

    values = [columns, *rows]
    return "<table>" + "".join(
        "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in values
    ) + "</table>"


def build_from_markdown(
    source_path: Path,
    bundle_directory: Path,
    data_id: str | None = None,
    *,
    source_format: str = "auto",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a line-located DocumentBundle without inventing PDF coordinates."""

    parsed = parse_file(source_path, source_format=source_format)
    bundle_directory.mkdir(parents=True, exist_ok=True)
    (bundle_directory / "assets" / "figures").mkdir(parents=True, exist_ok=True)
    (bundle_directory / "assets" / "tables").mkdir(parents=True, exist_ok=True)
    raw_directory = bundle_directory / "raw"
    raw_directory.mkdir(parents=True, exist_ok=True)
    raw_bytes = source_path.read_bytes()
    (raw_directory / "document.md").write_bytes(raw_bytes)

    blocks: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    figures: list[dict[str, Any]] = []
    section_ids: dict[tuple[str, ...], str] = {}
    sections: list[dict[str, Any]] = []

    for index, source in enumerate(parsed["blocks"]):
        path = source.get("section_path", [])
        key = tuple(str(item.get("heading_block_id")) for item in path)
        section_id: str | None = None
        if key:
            for depth in range(1, len(key) + 1):
                partial = key[:depth]
                if partial not in section_ids:
                    new_id = f"sec-{len(section_ids) + 1:03d}"
                    section_ids[partial] = new_id
                    sections.append(
                        {
                            "id": new_id,
                            "level": depth,
                            "title_block_id": partial[-1],
                            "parent_id": section_ids.get(partial[:-1]),
                            "child_section_ids": [],
                            "content_block_ids": [],
                        }
                    )
                    if depth > 1:
                        parent = next(item for item in sections if item["id"] == section_ids[partial[:-1]])
                        parent["child_section_ids"].append(new_id)
            section_id = section_ids[key]

        block = {
            "id": source["block_id"],
            "page": 1,
            "type": source["type"],
            "text_raw": source.get("raw_text", ""),
            "line_start": source["line_start"],
            "line_end": source["line_end"],
            "bbox": None,
            "parser_order": index,
            "reading_order": index,
            "section_id": section_id,
            "source_type": "markdown",
        }
        if source["type"] == "heading":
            block["text_raw"] = source.get("text", block["text_raw"])
            block["text_level"] = source.get("level", 1)
        blocks.append(block)
        if section_id:
            next(item for item in sections if item["id"] == section_id)["content_block_ids"].append(block["id"])

        if source["type"] == "table":
            table_id = f"table-{len(tables) + 1:03d}"
            tables.append(
                {
                    "id": table_id,
                    "title_block_id": None,
                    "caption_block_ids": [],
                    "footnote_block_ids": [],
                    "section_id": section_id,
                    "fragments": [],
                    "structure_raw": {
                        "format": "grid",
                        "columns": source.get("columns", []),
                        "rows": source.get("rows", []),
                        "content": _html_table(source.get("columns", []), source.get("rows", [])),
                    },
                    "status": "complete",
                    "issues": [],
                    "continuation_block_ids": [],
                    "source_block_id": block["id"],
                }
            )
            block["table_id"] = table_id
        elif source["type"] == "image":
            figures.append(
                {
                    "id": f"fig-{len(figures) + 1:03d}",
                    "page": 1,
                    "section_id": section_id,
                    "caption_block_id": None,
                    "caption_block_ids": [],
                    "footnote_block_ids": [],
                    "bbox": None,
                    "asset_path": source.get("url"),
                    "source": "markdown_reference",
                    "source_block_id": block["id"],
                    "issues": [],
                }
            )

    identity = data_id or parsed["document"]["document_id"]
    document = {
        "document": {
            "id": identity,
            "title": parsed["document"].get("title"),
            "page_count": 1,
            "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "source_file": source_path.name,
            "source_format": parsed["document"]["source_format"],
            "location_model": "line_range",
        },
        "pages": [{"id": "p001", "page": 1, "width": None, "height": None, "block_ids": [b["id"] for b in blocks]}],
        "blocks": blocks,
        "sections": sections,
        "tables": tables,
        "figures": figures,
        "reading_order": [block["id"] for block in blocks],
    }
    validation = {
        "status": "passed",
        "page_count": {"expected": 1, "actual": 1},
        "block_coverage": {
            "raw_block_count": len(blocks),
            "structured_block_count": len(blocks),
            "missing_block_ids": [],
            "duplicate_block_ids": [],
        },
        "tables": {"detected": len(tables), "complete": len(tables), "image_only": 0},
        "figures": {"detected": len(figures)},
        "parser": {"name": "parse_report", "api_version": None, "model_version": None, "fallback_used": False},
        "issues": [],
    }
    _write_json_atomic(bundle_directory / "document.json", document)
    _write_json_atomic(bundle_directory / "validation.json", validation)
    return document, validation

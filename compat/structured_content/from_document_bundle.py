"""Deprecated adapter from DocumentBundle v0.1 to Parsed Document.

This module is deliberately deterministic.  It contains no LLM behavior and
does not summarize, rewrite, or invent source content.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from lxml import html


DOCUMENT_BUNDLE_FIELDS = {
    "document",
    "pages",
    "blocks",
    "sections",
    "tables",
    "figures",
    "reading_order",
}


def _is_bundle(value: Mapping[str, Any]) -> bool:
    return set(value) == DOCUMENT_BUNDLE_FIELDS


def _text(block: Mapping[str, Any]) -> str:
    return str(block.get("text_raw") or block.get("text") or "").strip()


def _section_paths(document: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    blocks = {str(block.get("id")): block for block in document.get("blocks", [])}
    sections = {str(section.get("id")): section for section in document.get("sections", [])}
    result: dict[str, list[dict[str, Any]]] = {}
    for section_id, section in sections.items():
        chain: list[Mapping[str, Any]] = []
        current: Mapping[str, Any] | None = section
        seen: set[str] = set()
        while current is not None:
            current_id = str(current.get("id"))
            if current_id in seen:
                break
            seen.add(current_id)
            chain.append(current)
            parent = current.get("parent_id")
            current = sections.get(str(parent)) if parent is not None else None
        path: list[dict[str, Any]] = []
        for item in reversed(chain):
            heading_id = str(item.get("title_block_id") or "")
            title = _text(blocks.get(heading_id, {}))
            if heading_id and title:
                path.append(
                    {
                        "level": max(1, min(6, int(item.get("level") or 1))),
                        "title": title,
                        "heading_block_id": heading_id,
                    }
                )
        result[section_id] = path
    return result


def _html_table(value: str) -> tuple[list[str], list[list[str]]]:
    if not value.strip():
        return [], []
    try:
        root = html.fromstring(value)
    except (ValueError, TypeError):
        return [], []
    rows = [
        [" ".join(cell.text_content().split()) for cell in row.xpath("./th|./td")]
        for row in root.xpath(".//tr")
    ]
    rows = [row for row in rows if row]
    return (rows[0], rows[1:]) if rows else ([], [])


def _table_lookup(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for table in document.get("tables", []):
        if not isinstance(table, Mapping):
            continue
        if isinstance(table.get("source_content_index"), int):
            result[f"source:{table['source_content_index']}"] = table
        if table.get("source_block_id"):
            result[f"block:{table['source_block_id']}"] = table
        if table.get("id"):
            result[f"table:{table['id']}"] = table
    return result


def _table_for_block(
    block: Mapping[str, Any], tables: Mapping[str, Mapping[str, Any]]
) -> Mapping[str, Any] | None:
    keys = []
    if isinstance(block.get("source_content_index"), int):
        keys.append(f"source:{block['source_content_index']}")
    keys.extend((f"block:{block.get('id')}", f"table:{block.get('table_id')}"))
    return next((tables[key] for key in keys if key in tables), None)


def _block_lookup(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(block.get("id")): block
        for block in document.get("blocks", [])
        if isinstance(block, Mapping) and block.get("id")
    }


def _caption(table: Mapping[str, Any], blocks: Mapping[str, Mapping[str, Any]]) -> str | None:
    values = [
        _text(blocks.get(str(block_id), {}))
        for block_id in table.get("caption_block_ids", [])
    ]
    text = " ".join(value for value in values if value)
    return text or None


def _note(table: Mapping[str, Any], blocks: Mapping[str, Mapping[str, Any]]) -> str | None:
    values = [
        _text(blocks.get(str(block_id), {}))
        for block_id in table.get("footnote_block_ids", [])
    ]
    text = " ".join(value for value in values if value)
    return text or None


def _table_content(
    source: Mapping[str, Any],
    table: Mapping[str, Any],
    blocks: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    structure = table.get("structure_raw") if isinstance(table, Mapping) else None
    columns: list[str] = []
    rows: list[list[str]] = []
    if isinstance(structure, Mapping) and structure.get("format") == "html":
        columns, rows = _html_table(str(structure.get("content") or ""))
    elif isinstance(structure, Mapping) and structure.get("format") == "grid":
        columns = [str(value) for value in structure.get("columns", [])]
        rows = [[str(cell) for cell in row] for row in structure.get("rows", [])]
    if not columns:
        return None
    normalized_rows = [
        (row + [""] * len(columns))[: len(columns)]
        for row in rows
    ]
    return {
        "block_id": str(source["id"]),
        "type": "table",
        "caption": _caption(table, blocks),
        "columns": columns,
        "alignments": ["none"] * len(columns),
        "rows": normalized_rows,
        "note": _note(table, blocks),
    }


def from_document_bundle(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return a schema-compatible, lossless-enough LLM/visualization input view."""

    if not _is_bundle(document):
        raise ValueError("Input is not a DocumentBundle v0.1 document.json object")
    metadata = document["document"]
    source_blocks = _block_lookup(document)
    sections = _section_paths(document)
    tables = _table_lookup(document)
    ordered_ids = [str(value) for value in document.get("reading_order", [])]
    ordered = [source_blocks[value] for value in ordered_ids if value in source_blocks]
    if len(ordered) != len(source_blocks):
        included = {str(block.get("id")) for block in ordered}
        ordered.extend(block for block_id, block in source_blocks.items() if block_id not in included)

    converted: list[dict[str, Any]] = []
    heading_by_section = {
        section_id: path[-1]["heading_block_id"]
        for section_id, path in sections.items()
        if path
    }
    for ordinal, block in enumerate(ordered, start=1):
        block_id = str(block["id"])
        block_type = str(block.get("type") or "paragraph")
        section_id = str(block.get("section_id") or "")
        base: dict[str, Any] = {
            "block_id": block_id,
            "type": "paragraph",
            "line_start": ordinal,
            "line_end": ordinal,
            "raw_text": _text(block),
            "section_path": sections.get(section_id, []),
            "parent_heading_id": heading_by_section.get(section_id),
            "citations": [],
        }
        if block_type == "heading":
            base.update(
                {
                    "type": "heading",
                    "text": _text(block) or block_id,
                    "level": max(1, min(6, int(block.get("text_level") or 1))),
                    "style": "plain_text",
                }
            )
        elif block_type == "table":
            table = _table_for_block(block, tables)
            content = _table_content(block, table or {}, source_blocks)
            if content:
                base.update(content)
            else:
                fragments = list((table or {}).get("fragments", []))
                url = str(fragments[0].get("crop_path")) if fragments else "unavailable://table"
                base.update(
                    {
                        "type": "image",
                        "alt_text": _caption(table or {}, source_blocks) or "Table image",
                        "url": url,
                        "title": _caption(table or {}, source_blocks),
                    }
                )
        elif block_type == "figure":
            figure = next(
                (
                    value
                    for value in document.get("figures", [])
                    if value.get("source_content_index") == block.get("source_content_index")
                ),
                None,
            )
            base.update(
                {
                    "type": "image",
                    "alt_text": "Figure",
                    "url": str((figure or {}).get("asset_path") or "unavailable://figure"),
                    "title": None,
                }
            )
        else:
            base["text"] = _text(block) or f"[{block_type}]"
        converted.append(base)

    counts = {name: 0 for name in (
        "heading", "paragraph", "list", "table", "image", "blockquote", "code", "horizontal_rule"
    )}
    for block in converted:
        counts[block["type"]] += 1
    return {
        "schema_version": "1.0",
        "parser": {
            "name": "document_bundle_adapter",
            "version": "1.0.0",
            "parsed_at": "1970-01-01T00:00:00+00:00",
            "options": {
                "plain_text_heading_detection": False,
                "preserve_code_blocks": True,
                "preserve_images": True,
                "merge_adjacent_paragraph_lines": False,
            },
        },
        "document": {
            "document_id": str(metadata.get("id") or "document"),
            "title": metadata.get("title"),
            "source_file": str(metadata.get("source_file") or f"{metadata.get('id', 'document')}.pdf"),
            "source_format": str(metadata.get("source_format") or "pdf"),
            "encoding": "binary" if metadata.get("source_format", "pdf") == "pdf" else "utf-8",
            "line_count": len(converted),
            "character_count": sum(len(str(block.get("raw_text") or "")) for block in converted),
            "source_hash_sha256": metadata.get("source_sha256"),
            "language": "zh-CN",
        },
        "blocks": converted,
        "statistics": {
            "block_count": len(converted),
            "heading_count": counts["heading"],
            "paragraph_count": counts["paragraph"],
            "list_count": counts["list"],
            "table_count": counts["table"],
            "image_count": counts["image"],
            "blockquote_count": counts["blockquote"],
            "code_count": counts["code"],
            "horizontal_rule_count": counts["horizontal_rule"],
        },
        "warnings": [],
    }


def ensure_structured_content(value: Mapping[str, Any]) -> dict[str, Any]:
    """Pass through legacy structured content or adapt a DocumentBundle."""

    return from_document_bundle(value) if _is_bundle(value) else dict(value)


def load_structured_content(path: Path) -> dict[str, Any]:
    document_path = path / "document.json" if path.is_dir() else path
    value = json.loads(document_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Structured content root must be an object: {document_path}")
    return ensure_structured_content(value)

from __future__ import annotations

from pathlib import Path

import pytest

from document_bundle.markdown import build_from_markdown
from document_intelligence import generate_chunks, load_document_intelligence
from outline_generator.llm_understanding import (
    ContextMemoryError,
    parse_context_memory,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = PROJECT_ROOT / "schemas" / "document_bundle.schema.json"


def _snapshot(tmp_path, fixture="table_sample.md"):
    bundle = tmp_path / "document_bundle"
    build_from_markdown(PROJECT_ROOT / "tests" / "fixtures" / fixture, bundle)
    return load_document_intelligence(bundle, SCHEMA)


def _keys(value):
    if isinstance(value, dict):
        yield from value
        for child in value.values():
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _keys(child)


def test_indexes_and_relationships_use_document_bundle_native_ids(tmp_path):
    snapshot = _snapshot(tmp_path)
    assert tuple(snapshot.blocks_by_id) == snapshot.ordered_block_ids
    table_id = next(iter(snapshot.tables_by_id))
    table_blocks = [
        block_id
        for block_id, ids in snapshot.block_table_ids.items()
        if table_id in ids
    ]
    assert table_blocks
    evidence = snapshot.evidence("table", table_id)
    assert evidence is not None
    assert evidence.id == table_id


def test_chunking_preserves_every_block_and_contains_no_semantic_outputs(tmp_path):
    snapshot = _snapshot(tmp_path, "heading_paragraph.md")
    chunks = generate_chunks(snapshot, max_chars=120)
    assert tuple(block_id for chunk in chunks for block_id in chunk.block_ids) == snapshot.ordered_block_ids
    prohibited = {"summary", "key_points", "importance", "slide_plan", "bullet_points"}
    assert not (set(key for chunk in chunks for key in _keys(dict(chunk.payload))) & prohibited)


def test_context_memory_reassembles_structure_and_evidence_from_chunk(tmp_path):
    chunk = generate_chunks(_snapshot(tmp_path), max_chars=20_000)[0]
    block_id = chunk.block_ids[0]
    memory = parse_context_memory(
        '{"chunk_id":"wrong","section_ref":"wrong","source_ref":"wrong",'
        '"summary":"Compressed source","key_points":["Point"],'
        '"important_insights":["Insight"]}',
        chunk,
    )
    assert memory["chunk_id"] == chunk.id
    assert memory["section_ref"] == chunk.section_id
    assert memory["evidence_refs"][0]["id"] == block_id
    assert "source_ref" not in memory


@pytest.mark.parametrize(
    "content",
    [
        "{not-json}",
        '{"key_points":[]}',
        '{"summary":"Summary"}',
        '{"summary":"Summary","key_points":[""]}',
    ],
)
def test_context_memory_rejects_invalid_semantic_output(tmp_path, content):
    chunk = generate_chunks(_snapshot(tmp_path), max_chars=20_000)[0]
    with pytest.raises(ContextMemoryError):
        parse_context_memory(content, chunk)


def test_document_intelligence_has_no_llm_or_outline_dependency():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((PROJECT_ROOT / "document_intelligence").glob("*.py"))
    )
    assert "outline_generator" not in source
    assert "structured_content" not in source
    assert "call_deepseek" not in source
    assert "openai" not in source.casefold()

"""Runtime-only LLM context compression and slide-planning prompts.

No context memory produced here is a persisted project data standard.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from document_intelligence.figures import build_figure_inventory
from document_intelligence.models import DocumentIntelligenceSnapshot, IntelligenceChunk


class ContextMemoryError(ValueError):
    pass


def build_context_compression_messages(chunk: IntelligenceChunk) -> list[dict[str, str]]:
    system = (
        "You compress the facts in exactly one research-report chunk into transient "
        "runtime memory for later slide planning. Do not create or reorder sections, "
        "add external facts, or produce a slide outline. The output JSON must contain "
        "only summary, key_points, and important_insights. Do not output chunk_id, "
        "section_id, section_ref, source_ref, source_refs, page_id, evidence_refs, or "
        "any other source document identifier. The application owns and reattaches "
        "all structural and provenance fields. Return exactly one JSON object and no "
        "explanatory text."
    )
    payload = {
        "task": "context_compression",
        "output_contract": {
            "summary": "A concise summary based only on this chunk",
            "key_points": ["A concrete key point from this chunk"],
            "important_insights": ["An important implication grounded in this chunk"],
        },
        "document_intelligence_chunk": dict(chunk.payload),
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def build_context_compression_correction_messages(
    original_messages: Sequence[Mapping[str, str]],
    *,
    previous_content: str,
    error: str,
) -> list[dict[str, str]]:
    """Ask the model to repair one invalid compression response."""

    correction = {
        "task": "correct_context_compression_output",
        "error": error,
        "instructions": (
            "Return a corrected JSON object containing only a non-empty summary, "
            "a key_points array of non-empty strings, and an important_insights "
            "array of non-empty strings. Do not return source document identifiers."
        ),
    }
    return [
        *[dict(message) for message in original_messages],
        {"role": "assistant", "content": previous_content[:50_000] or "{}"},
        {"role": "user", "content": json.dumps(correction, ensure_ascii=False)},
    ]


def parse_context_memory(content: str, chunk: IntelligenceChunk) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ContextMemoryError(
            f"Context Compression output is not valid JSON: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise ContextMemoryError("Context Compression output root must be an object")

    summary = value.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ContextMemoryError(
            "Context Compression output must contain a non-empty summary"
        )

    key_points = value.get("key_points")
    if not isinstance(key_points, list):
        raise ContextMemoryError(
            "Context Compression output must contain a key_points array"
        )
    normalized_key_points = [
        item.strip() for item in key_points if isinstance(item, str) and item.strip()
    ]
    if len(normalized_key_points) != len(key_points):
        raise ContextMemoryError(
            "Context Compression key_points must contain only non-empty strings"
        )

    important_insights = value.get("important_insights", [])
    if not isinstance(important_insights, list):
        raise ContextMemoryError(
            "Context Compression important_insights must be an array"
        )
    normalized_insights = [
        item.strip()
        for item in important_insights
        if isinstance(item, str) and item.strip()
    ]
    if len(normalized_insights) != len(important_insights):
        raise ContextMemoryError(
            "Context Compression important_insights must contain only non-empty strings"
        )

    evidence_refs = [
        {"kind": str(item["kind"]), "id": str(item["id"])}
        for item in chunk.payload.get("allowed_evidence_refs", [])
        if isinstance(item, Mapping) and "kind" in item and "id" in item
    ]
    return {
        "chunk_id": chunk.id,
        "section_ref": chunk.section_id,
        "summary": summary.strip(),
        "key_points": normalized_key_points,
        "important_insights": normalized_insights,
        "evidence_refs": evidence_refs,
    }


def preview_context_memory(chunk: IntelligenceChunk) -> dict[str, Any]:
    """Dry-run placeholder; never used as model-generated understanding."""

    return {
        "chunk_id": chunk.id,
        "section_ref": chunk.section_id,
        "summary": "",
        "key_points": [],
        "important_insights": [],
        "evidence_refs": [
            {"kind": str(item["kind"]), "id": str(item["id"])}
            for item in chunk.payload.get("allowed_evidence_refs", [])
            if isinstance(item, Mapping) and "kind" in item and "id" in item
        ],
        "preview_only": True,
    }


def build_direct_context_memory(chunk: IntelligenceChunk) -> dict[str, Any]:
    """Expose deterministic source context without an LLM compression pass."""

    return {
        "chunk_id": chunk.id,
        "section_ref": chunk.section_id,
        "context_mode": "direct",
        "raw_context": {
            key: chunk.payload[key]
            for key in ("section", "section_path", "blocks", "tables", "figures")
            if key in chunk.payload
        },
        "evidence_refs": [
            {"kind": str(item["kind"]), "id": str(item["id"])}
            for item in chunk.payload.get("allowed_evidence_refs", [])
            if isinstance(item, Mapping) and "kind" in item and "id" in item
        ],
    }


def _section_catalog(snapshot: DocumentIntelligenceSnapshot) -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for ordinal, section_id in enumerate(snapshot.section_order):
        section = snapshot.sections_by_id[section_id]
        title_block_id = str(section.get("title_block_id") or "")
        title_block = snapshot.blocks_by_id.get(title_block_id, {})
        catalog.append(
            {
                "ordinal": ordinal,
                "section_id": section_id,
                "parent_id": section.get("parent_id"),
                "level": section.get("level"),
                "title": title_block.get("text_raw", ""),
                "title_block_id": title_block_id,
            }
        )
    return catalog


def build_slide_planning_messages(
    snapshot: DocumentIntelligenceSnapshot,
    runtime_memories: Sequence[Mapping[str, Any]],
    schema: Mapping[str, Any],
    few_shot: Mapping[str, Any],
    system_prompt: str,
) -> list[dict[str, str]]:
    document_id = str(snapshot.metadata.get("id") or "document")
    source_id = "src_" + "".join(
        character if character.isalnum() or character in "_.-" else "_"
        for character in document_id
    ).strip("_.-")
    system_content = (
        system_prompt
        + "\n\n# 指令优先级（发生冲突时必须按此顺序执行）\n"
        + "1. slide_outline.schema.json JSON Schema。\n"
        + "2. 应用提供的 DocumentBundle、section_catalog、figure_inventory、"
        + "runtime_context_memories 与 evidence_refs。\n"
        + "3. 本 Prompt 的原文保真、来源、页面规划和 Figure 保真硬规则。\n"
        + "4. 当前请求 payload 中的 constraints。\n"
        + "5. Selected few-shot cases；case 仅用于说明规则，绝不能覆盖真实文档证据。\n"
        + "6. 一般写作习惯或模型偏好。\n"
        + "如果 case 示例与当前文档、Schema 或硬规则不一致，必须忽略 case 中冲突的部分。"
        + "\n\n# DocumentBundle 章节与证据约束\n"
        + "只能使用 section_catalog 中存在的 section_ref；不得新增章节或改变章节顺序。"
        + "所有带 section_ref 的 slide，其 title 必须逐字复制 section_catalog 对应条目的 title，"
        + "包括章节编号和标点；不得使用结论式标题或同义改写。"
        + "正文 key_message 优先保留证据中的第一句主旨句，后续信息才允许提炼为 bullet_points。"
        + "每个 content slide 必须提供 evidence_refs，且只能引用 runtime_context_memories 中的原生证据。"
        + "source_refs 仍必须引用 required_source_id。"
        + "\n\n# 原始 PDF Figure 保真迁移\n"
        + "figure_inventory 是应用程序根据 PDF 原始顺序生成的图片目录。"
        + "只选择 selectable=true 且能直接支撑研报重要观点的 figure；不得选择装饰图或无关图片。"
        + "每张被选择的 figure 必须生成一个独立 slide，page_role=content，"
        + "slide_type=figure_page，bullet_points=[]，visual_candidates=[]，"
        + "evidence_refs 只能包含该一个 figure。"
        + "figure_page 的 title 优先使用 caption，section_ref 必须等于 figure 的 section_id。"
        + "被选择的 figure_page 必须严格按照 figure_inventory.order 递增排列，"
        + "不得交换顺序、合并多图或在一页加入解释性正文。"
        + "\n\n# Selected few-shot 内容规划案例\n"
        + json.dumps(few_shot, ensure_ascii=False, separators=(",", ":"))
        + "\n\n# 必须遵循的 JSON Schema\n"
        + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        + "\n\n# Runtime context modes\n"
        + "Each runtime_context_memories entry is either direct deterministic source "
        + "context in raw_context or an LLM-compressed semantic memory. Treat "
        + "evidence_refs as application-owned provenance in both modes."
    )
    payload = {
        "task": "slide_planning_from_runtime_context",
        "required_source_id": source_id,
        "document": dict(snapshot.metadata),
        "section_catalog": _section_catalog(snapshot),
        "figure_inventory": build_figure_inventory(snapshot),
        "runtime_context_memories": [dict(memory) for memory in runtime_memories],
        "constraints": {
            "preserve_section_hierarchy": True,
            "preserve_section_order": True,
            "no_new_sections": True,
            "preserve_source_section_title_verbatim": True,
            "prefer_first_topic_sentence_verbatim": True,
            "content_slides_require_evidence": True,
            "figure_page_one_figure_only": True,
            "preserve_figure_order": True,
        },
    }
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]

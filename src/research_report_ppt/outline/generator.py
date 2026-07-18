#!/usr/bin/env python3
"""Generate a research-report PPT semantic outline with DeepSeek.

The script connects parsed-document JSON to the repository's canonical
``slide_outline.schema.json`` contract.
It uses the DeepSeek OpenAI-compatible Chat Completions endpoint and JSON mode.

Examples (run from the project root):
    research-report-ppt generate-outline \
      outputs/parsed_documents/002544_2025-10-28.json \
      -o outputs/outlines/002544_2025-10-28_outline.json

    research-report-ppt generate-outline INPUT.json --dry-run \
      --request-output output/outline_request_preview.json

Environment:
    DEEPSEEK_API_KEY   Required unless --dry-run is used.
    DEEPSEEK_BASE_URL  Optional; defaults to https://api.deepseek.com.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from research_report_ppt.validation.outline import (
    Issue,
    validate_outline as validate_outline_data,
)


DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL = "https://api.deepseek.com"
class OutlineGenerationError(RuntimeError):
    """Raised when prompt creation, API invocation, or validation fails."""


class DeepSeekAPIError(OutlineGenerationError):
    """Raised for an HTTP/network API failure with retry metadata."""

    def __init__(self, message: str, *, retryable: bool, status_code: Optional[int] = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


class OutlineResponseError(OutlineGenerationError):
    """Raised when the model response cannot be used as an outline."""

    def __init__(self, message: str, *, retryable: bool, content: str = ""):
        super().__init__(message)
        self.retryable = retryable
        self.content = content


class OutlineValidationError(OutlineGenerationError):
    """Raised when a generated outline violates the canonical contract."""

    def __init__(self, issues: Sequence[Issue], *, content: str):
        errors = [issue for issue in issues if issue.severity == "error"]
        summary = "\n".join(
            f"- {issue.code} {issue.path}: {issue.message}" for issue in errors[:20]
        )
        super().__init__(f"Generated outline failed validation:\n{summary}")
        self.issues = list(issues)
        self.content = content
        self.retryable = True


def load_json(path: Path, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OutlineGenerationError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise OutlineGenerationError(
            f"{label} is not valid JSON: {path}:{exc.lineno}:{exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise OutlineGenerationError(f"{label} root must be a JSON object: {path}")
    return value


def load_text(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise OutlineGenerationError(f"{label} not found: {path}") from exc


def validate_json_instance(
    instance: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    label: str,
) -> None:
    """Fail early when an input JSON object violates its canonical schema."""
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise OutlineGenerationError(f"{label} schema is invalid: {exc.message}") from exc

    errors = sorted(
        Draft202012Validator(schema).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    if not errors:
        return
    details = []
    for error in errors[:20]:
        path = "$" + "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}"
            for part in error.absolute_path
        )
        details.append(f"- {path}: {error.message}")
    raise OutlineGenerationError(
        f"{label} failed schema validation ({len(errors)} error(s)):\n"
        + "\n".join(details)
    )


def safe_identifier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_.-")
    return cleaned or "document"


def compact_block(block: Mapping[str, Any]) -> Dict[str, Any]:
    """Keep model-relevant fields while retaining exact evidence IDs."""
    result: Dict[str, Any] = {
        key: block[key]
        for key in ("block_id", "type", "line_start", "line_end", "citations")
        if key in block
    }
    section_path = block.get("section_path")
    if isinstance(section_path, list):
        result["section_path"] = [
            {"level": item.get("level"), "title": item.get("title")}
            for item in section_path
            if isinstance(item, Mapping)
        ]

    block_type = block.get("type")
    if block_type in {"heading", "paragraph", "blockquote", "code"}:
        result["text"] = block.get("text", block.get("raw_text", ""))
    elif block_type == "list":
        result["ordered"] = block.get("ordered")
        result["items"] = block.get("items", [])
    elif block_type == "table":
        for key in ("caption", "columns", "alignments", "rows", "note"):
            if key in block:
                result[key] = block[key]
    elif block_type == "image":
        for key in ("alt_text", "url", "title"):
            if key in block:
                result[key] = block[key]
    else:
        result["raw_text"] = block.get("raw_text", "")
    return result


def compact_document(document: Mapping[str, Any], max_input_chars: int) -> Dict[str, Any]:
    metadata = document.get("document")
    blocks = document.get("blocks")
    if not isinstance(metadata, Mapping) or not isinstance(blocks, list):
        raise OutlineGenerationError("Parsed document must contain document metadata and blocks")

    compacted: List[Dict[str, Any]] = []
    used = 0
    omitted = 0
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        item = compact_block(block)
        encoded = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        if compacted and used + len(encoded) > max_input_chars:
            omitted += 1
            continue
        compacted.append(item)
        used += len(encoded)

    return {
        "document": dict(metadata),
        "statistics": document.get("statistics", {}),
        "blocks": compacted,
        "input_selection": {
            "included_blocks": len(compacted),
            "omitted_blocks": omitted,
            "max_input_chars": max_input_chars,
        },
    }


def build_messages(
    parsed_document: Mapping[str, Any],
    schema: Mapping[str, Any],
    few_shot: Mapping[str, Any],
    system_prompt: str,
    *,
    max_input_chars: int,
) -> List[Dict[str, str]]:
    compacted = compact_document(parsed_document, max_input_chars)
    document_id = safe_identifier(str(compacted["document"].get("document_id", "document")))
    source_id = f"src_{document_id}"

    system_content = (
        system_prompt
        + "\n\n# Few-shot 内容规划示例\n"
        + json.dumps(few_shot, ensure_ascii=False, separators=(",", ":"))
        + "\n\n# 必须遵循的 JSON Schema\n"
        + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    )
    user_payload = {
        "task": "根据 parsed_document 生成完整的财报 PPT 大纲 JSON",
        "required_source_id": source_id,
        "parsed_document": compacted,
    }
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def build_request(
    messages: List[Dict[str, str]],
    *,
    model: str,
    max_tokens: int,
    thinking: str,
    reasoning_effort: str,
) -> Dict[str, Any]:
    request: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "max_tokens": max_tokens,
        "stream": False,
    }
    request["thinking"] = {"type": thinking}
    if thinking == "enabled":
        request["reasoning_effort"] = reasoning_effort
    return request


def call_deepseek(request_body: Mapping[str, Any], *, api_key: str, base_url: str, timeout: int) -> Dict[str, Any]:
    endpoint = base_url.rstrip("/") + "/chat/completions"
    http_request = urllib.request.Request(
        endpoint,
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(http_request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DeepSeekAPIError(
            f"DeepSeek API returned HTTP {exc.code}: {detail[:1000]}",
            retryable=exc.code == 429 or exc.code >= 500,
            status_code=exc.code,
        ) from exc
    except urllib.error.URLError as exc:
        raise DeepSeekAPIError(
            f"Cannot connect to DeepSeek API: {exc.reason}",
            retryable=True,
        ) from exc
    except json.JSONDecodeError as exc:
        raise DeepSeekAPIError(
            "DeepSeek API response is not valid JSON",
            retryable=True,
        ) from exc
    if not isinstance(payload, dict):
        raise DeepSeekAPIError(
            "DeepSeek API response root is not an object",
            retryable=True,
        )
    return payload


def extract_response_content(api_response: Mapping[str, Any]) -> str:
    try:
        choice = api_response["choices"][0]
        finish_reason = choice.get("finish_reason")
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OutlineResponseError(
            "DeepSeek response does not contain choices[0].message.content",
            retryable=True,
        ) from exc
    if finish_reason == "length":
        raise OutlineResponseError(
            "DeepSeek output was truncated; increase --max-tokens",
            retryable=False,
            content=content if isinstance(content, str) else "",
        )
    if not isinstance(content, str) or not content.strip():
        raise OutlineResponseError(
            "DeepSeek returned empty content; retry or adjust the prompt",
            retryable=True,
        )
    return content


def parse_outline_content(content: str) -> Dict[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise OutlineResponseError(
            f"Model content is not valid JSON: line {exc.lineno}, column {exc.colno}: {exc.msg}",
            retryable=True,
            content=content,
        ) from exc
    if not isinstance(value, dict):
        raise OutlineResponseError(
            "Generated outline root must be a JSON object",
            retryable=True,
            content=content,
        )
    return value


def extract_outline(api_response: Mapping[str, Any]) -> Dict[str, Any]:
    """Extract and parse the final JSON object from a DeepSeek response."""
    return parse_outline_content(extract_response_content(api_response))


def build_correction_messages(
    original_messages: Sequence[Mapping[str, str]],
    *,
    previous_content: str,
    errors: Sequence[str],
) -> List[Dict[str, str]]:
    """Build one corrective turn without changing the schema or source input."""
    error_text = "\n".join(f"- {item}" for item in errors[:20])
    return [
        *[dict(message) for message in original_messages],
        {
            "role": "assistant",
            "content": previous_content[:50_000] or "{}",
        },
        {
            "role": "user",
            "content": (
                "上一个输出无效。请只返回修正后的完整 JSON 对象，不要解释，"
                "不得改变或补造输入事实。需要修复的问题：\n"
                + error_text
            ),
        },
    ]


def generate_with_retries(
    messages: List[Dict[str, str]],
    schema: Mapping[str, Any],
    *,
    api_key: str,
    base_url: str,
    timeout: int,
    model: str,
    max_tokens: int,
    thinking: str,
    reasoning_effort: str,
    max_attempts: int,
    validate_output: bool = True,
) -> Tuple[Dict[str, Any], List[Issue], int]:
    """Call DeepSeek and retry only failures that can be corrected safely."""
    attempt_messages = list(messages)
    last_error: Optional[OutlineGenerationError] = None

    for attempt in range(1, max_attempts + 1):
        request_body = build_request(
            attempt_messages,
            model=model,
            max_tokens=max_tokens,
            thinking=thinking,
            reasoning_effort=reasoning_effort,
        )
        content = ""
        try:
            response = call_deepseek(
                request_body,
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
            )
            content = extract_response_content(response)
            outline = parse_outline_content(content)
            issues = validate_outline_data(outline, schema) if validate_output else []
            errors = [issue for issue in issues if issue.severity == "error"]
            if errors:
                raise OutlineValidationError(issues, content=content)
            return outline, issues, attempt
        except DeepSeekAPIError as exc:
            last_error = exc
            if not exc.retryable or attempt >= max_attempts:
                raise
            attempt_messages = list(messages)
        except OutlineResponseError as exc:
            last_error = exc
            if not exc.retryable or attempt >= max_attempts:
                raise
            attempt_messages = build_correction_messages(
                messages,
                previous_content=exc.content,
                errors=[str(exc)],
            )
        except OutlineValidationError as exc:
            last_error = exc
            if attempt >= max_attempts:
                raise
            attempt_messages = build_correction_messages(
                messages,
                previous_content=exc.content,
                errors=[
                    f"{issue.code} {issue.path}: {issue.message}"
                    for issue in exc.issues
                    if issue.severity == "error"
                ],
            )

    raise last_error or OutlineGenerationError("Outline generation failed")

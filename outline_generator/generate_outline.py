#!/usr/bin/env python3
"""Generate a research-report PPT semantic outline with DeepSeek.

The script connects parsed-document JSON to the repository's canonical
``slide_outline.schema.json`` contract.
It uses the DeepSeek OpenAI-compatible Chat Completions endpoint and JSON mode.

Examples (run from the project root):
    python -m outline_generator.generate_outline \
      outputs/parsed_documents/002544_2025-10-28.json \
      -o outputs/outlines/002544_2025-10-28_outline.json

    python -m outline_generator.generate_outline INPUT.json --dry-run \
      --request-output output/outline_request_preview.json

Environment:
    DEEPSEEK_API_KEY   Required unless --dry-run is used.
    DEEPSEEK_BASE_URL  Optional; defaults to https://api.deepseek.com.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL = "https://api.deepseek.com"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class OutlineGenerationError(RuntimeError):
    """Raised when prompt creation, API invocation, or validation fails."""


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
        raise OutlineGenerationError(f"DeepSeek API returned HTTP {exc.code}: {detail[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise OutlineGenerationError(f"Cannot connect to DeepSeek API: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise OutlineGenerationError("DeepSeek API response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise OutlineGenerationError("DeepSeek API response root is not an object")
    return payload


def extract_outline(api_response: Mapping[str, Any]) -> Dict[str, Any]:
    try:
        choice = api_response["choices"][0]
        finish_reason = choice.get("finish_reason")
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OutlineGenerationError("DeepSeek response does not contain choices[0].message.content") from exc
    if finish_reason == "length":
        raise OutlineGenerationError("DeepSeek output was truncated; increase --max-tokens")
    if not isinstance(content, str) or not content.strip():
        raise OutlineGenerationError("DeepSeek returned empty content; retry or adjust the prompt")
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise OutlineGenerationError(
            f"Model content is not valid JSON: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise OutlineGenerationError("Generated outline root must be a JSON object")
    return value


def find_validator(project_root: Path) -> Optional[Path]:
    candidates = (
        project_root / "tools" / "validate_outline.py",
        project_root / "validate_outline.py",
    )
    return next((path for path in candidates if path.is_file()), None)


def validate_outline(
    outline_path: Path,
    *,
    project_root: Path,
    schema_path: Path,
) -> None:
    validator = find_validator(project_root)
    if validator is None:
        raise OutlineGenerationError("Cannot find tools/validate_outline.py")
    command = [sys.executable, str(validator), str(outline_path), "--schema", str(schema_path)]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        details = (result.stdout + "\n" + result.stderr).strip()
        raise OutlineGenerationError(f"Generated outline failed validation:\n{details}")
    if result.stdout.strip():
        print(result.stdout.strip())


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a PPT outline JSON with DeepSeek V4")
    parser.add_argument("input", type=Path, help="T2.2 parsed-document JSON")
    parser.add_argument("-o", "--output", type=Path, help="Final outline JSON path")
    parser.add_argument(
        "--schema",
        type=Path,
        default=PROJECT_ROOT / "schemas" / "slide_outline.schema.json",
    )
    parser.add_argument(
        "--system-prompt",
        type=Path,
        default=PROJECT_ROOT / "prompts" / "outline_system_prompt.md",
    )
    parser.add_argument(
        "--few-shot",
        type=Path,
        default=PROJECT_ROOT / "prompts" / "outline_few_shot_examples.json",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--max-tokens", type=int, default=16000)
    parser.add_argument("--max-input-chars", type=int, default=180000)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--thinking", choices=["enabled", "disabled"], default="enabled")
    parser.add_argument("--reasoning-effort", choices=["low", "medium", "high", "max"], default="high")
    parser.add_argument("--dry-run", action="store_true", help="Build request JSON without calling DeepSeek")
    parser.add_argument("--request-output", type=Path, help="Optional path for the API request preview")
    parser.add_argument("--skip-validation", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    project_root = PROJECT_ROOT
    output = args.output or Path("output/outlines") / f"{args.input.stem}_outline.json"

    try:
        parsed_document = load_json(args.input, "Parsed document")
        schema = load_json(args.schema, "Outline schema")
        few_shot = load_json(args.few_shot, "Few-shot examples")
        system_prompt = load_text(args.system_prompt, "System prompt")
        messages = build_messages(
            parsed_document,
            schema,
            few_shot,
            system_prompt,
            max_input_chars=args.max_input_chars,
        )
        request_body = build_request(
            messages,
            model=args.model,
            max_tokens=args.max_tokens,
            thinking=args.thinking,
            reasoning_effort=args.reasoning_effort,
        )

        if args.request_output:
            args.request_output.parent.mkdir(parents=True, exist_ok=True)
            args.request_output.write_text(
                json.dumps(request_body, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Created request preview: {args.request_output}")

        if args.dry_run:
            print(f"Dry run OK: model={args.model}, messages={len(messages)}")
            return 0

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise OutlineGenerationError("DEEPSEEK_API_KEY is not set")
        response = call_deepseek(
            request_body,
            api_key=api_key,
            base_url=args.base_url,
            timeout=args.timeout,
        )
        outline = extract_outline(response)

        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix="outline_",
            dir=output.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(outline, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

        try:
            if not args.skip_validation:
                validate_outline(
                    temporary_path,
                    project_root=project_root,
                    schema_path=args.schema,
                )
            temporary_path.replace(output)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

        print(f"Created outline: {output}")
        print(f"Model: {args.model}")
        print(f"Slides: {len(outline.get('slides', []))}")
        return 0
    except (OutlineGenerationError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

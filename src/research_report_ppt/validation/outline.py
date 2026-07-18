#!/usr/bin/env python3
"""Validate a semantic slide outline against schema and cross-reference rules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    message: str


class InputError(RuntimeError):
    """Raised when an input or schema file cannot be loaded."""


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InputError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(
            f"{label} is not valid JSON: {path}:{exc.lineno}:{exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise InputError(f"{label} root must be an object: {path}")
    return value


def json_path(parts: Iterable[Any]) -> str:
    result = "$"
    for part in parts:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += f".{part}"
    return result


def duplicate_issues(
    values: Iterable[tuple[str, str]],
    *,
    code: str,
    label: str,
) -> list[Issue]:
    first_paths: dict[str, str] = {}
    issues: list[Issue] = []
    for value, path in values:
        if value in first_paths:
            issues.append(
                Issue(
                    "error",
                    code,
                    path,
                    f"duplicate {label} {value!r}; first declared at {first_paths[value]}",
                )
            )
        else:
            first_paths[value] = path
    return issues


def collect_source_refs(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "source_refs" and isinstance(child, list):
                for index, source_id in enumerate(child):
                    if isinstance(source_id, str):
                        yield source_id, f"{child_path}[{index}]"
            else:
                yield from collect_source_refs(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from collect_source_refs(child, f"{path}[{index}]")


def semantic_issues(outline: Mapping[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    sources = outline.get("sources", [])
    slides = outline.get("slides", [])

    source_entries = [
        (item["source_id"], f"$.sources[{index}].source_id")
        for index, item in enumerate(sources)
        if isinstance(item, Mapping) and isinstance(item.get("source_id"), str)
    ]
    issues.extend(
        duplicate_issues(source_entries, code="SOURCE.DUPLICATE_ID", label="source_id")
    )
    known_sources = {source_id for source_id, _ in source_entries}

    slide_entries = [
        (item["slide_id"], f"$.slides[{index}].slide_id")
        for index, item in enumerate(slides)
        if isinstance(item, Mapping) and isinstance(item.get("slide_id"), str)
    ]
    issues.extend(
        duplicate_issues(slide_entries, code="SLIDE.DUPLICATE_ID", label="slide_id")
    )

    candidate_entries = [
        (
            candidate["candidate_id"],
            f"$.slides[{slide_index}].visual_candidates[{candidate_index}].candidate_id",
        )
        for slide_index, slide in enumerate(slides)
        if isinstance(slide, Mapping)
        for candidate_index, candidate in enumerate(slide.get("visual_candidates", []))
        if isinstance(candidate, Mapping)
        and isinstance(candidate.get("candidate_id"), str)
    ]
    issues.extend(
        duplicate_issues(
            candidate_entries,
            code="VISUAL_CANDIDATE.DUPLICATE_ID",
            label="candidate_id",
        )
    )

    for source_id, path in collect_source_refs(outline.get("slides", []), "$.slides"):
        if source_id not in known_sources:
            issues.append(
                Issue(
                    "error",
                    "SOURCE.UNKNOWN_REFERENCE",
                    path,
                    f"source {source_id!r} is not declared in $.sources",
                )
            )

    for index, slide in enumerate(slides):
        if not isinstance(slide, Mapping):
            continue
        if slide.get("page_role") == "content" and not slide.get("source_refs"):
            issues.append(
                Issue(
                    "warning",
                    "SLIDE.CONTENT_WITHOUT_SOURCE",
                    f"$.slides[{index}].source_refs",
                    "content slide has no source reference",
                )
            )

    return issues


def validate_outline(
    outline: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> list[Issue]:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise InputError(f"invalid JSON Schema: {exc.message}") from exc

    validator = Draft202012Validator(schema)
    issues = [
        Issue(
            "error",
            "SCHEMA.INVALID",
            json_path(error.absolute_path),
            error.message,
        )
        for error in validator.iter_errors(outline)
    ]
    issues.extend(semantic_issues(outline))
    return sorted(issues, key=lambda item: (item.severity != "error", item.path, item.code))

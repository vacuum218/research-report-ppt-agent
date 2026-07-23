"""Loading and semantic validation for the Compiled Layout Plan contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPILED_PLAN_SCHEMA = PROJECT_ROOT / "schemas/compiled_layout_plan.schema.json"


class CompiledPlanError(ValueError):
    """Raised when a Compiled Layout Plan is structurally or semantically invalid."""


@dataclass(frozen=True, slots=True)
class LoadedCompiledPlan:
    path: Path | None
    data: Mapping[str, Any]
    visualizations_by_id: Mapping[str, Mapping[str, Any]]


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise CompiledPlanError(f"cannot load {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CompiledPlanError(f"{label} root must be an object")
    return value


def semantic_plan_errors(plan: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    slide_ids: set[str] = set()
    visualization_ids: set[str] = set()
    visualization_types: dict[str, str] = {}
    visualization_slides: dict[str, str] = {}
    for item in plan.get("visualizations", []):
        if not isinstance(item, Mapping):
            continue
        identity = str(item.get("visualization_id", ""))
        if identity in visualization_ids:
            errors.append(f"duplicate visualization_id: {identity!r}")
        visualization_ids.add(identity)
        visualization_types[identity] = str(item.get("visual_type", ""))
        visualization_slides[identity] = str(item.get("slide_id", ""))

    consumed: set[str] = set()
    expected_by_op = {
        "render_chart": "chart",
        "render_table": "table",
        "render_image": "image",
    }
    for slide in plan.get("slides", []):
        if not isinstance(slide, Mapping):
            continue
        slide_id = str(slide.get("slide_id", ""))
        if slide_id in slide_ids:
            errors.append(f"duplicate slide_id: {slide_id!r}")
        slide_ids.add(slide_id)
        for operation in slide.get("operations", []):
            if not isinstance(operation, Mapping):
                continue
            op = str(operation.get("op", ""))
            if op not in expected_by_op:
                continue
            identity = str(operation.get("visualization_id", ""))
            if identity not in visualization_ids:
                errors.append(
                    f"operation references unknown visualization_id: {identity!r}"
                )
                continue
            if identity in consumed:
                errors.append(f"visualization is consumed more than once: {identity!r}")
            consumed.add(identity)
            if visualization_slides[identity] != slide_id:
                errors.append(
                    f"visualization {identity!r} is bound to a different slide"
                )
            if visualization_types[identity] != expected_by_op[op]:
                errors.append(
                    f"operation {op!r} cannot consume "
                    f"{visualization_types[identity]!r} visualization {identity!r}"
                )
    unused = visualization_ids - consumed
    for identity in sorted(unused):
        errors.append(f"visualization is not consumed: {identity!r}")
    return errors


def validate_compiled_plan(
    plan: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> list[str]:
    schema_errors = sorted(
        Draft202012Validator(schema).iter_errors(plan),
        key=lambda error: list(error.absolute_path),
    )
    return [error.message for error in schema_errors] + semantic_plan_errors(plan)


def load_compiled_plan(
    path: Path,
    *,
    schema_path: Path = DEFAULT_COMPILED_PLAN_SCHEMA,
) -> LoadedCompiledPlan:
    plan_path = path.resolve()
    plan = _load_json(plan_path, "Compiled Layout Plan")
    schema = _load_json(schema_path, "Compiled Layout Plan schema")
    errors = validate_compiled_plan(plan, schema)
    if errors:
        raise CompiledPlanError("; ".join(errors))
    return LoadedCompiledPlan(
        plan_path,
        plan,
        {
            str(item["visualization_id"]): item
            for item in plan.get("visualizations", [])
            if isinstance(item, Mapping)
        },
    )

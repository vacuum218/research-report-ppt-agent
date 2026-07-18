#!/usr/bin/env python3
"""Validate a chart/table Visualization JSON and its dimensional consistency."""

from __future__ import annotations

from typing import Any, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .outline import InputError, Issue, json_path, load_json


def semantic_issues(visualization: Mapping[str, Any]) -> list[Issue]:
    issues: list[Issue] = []

    if "chart_type" in visualization:
        categories = visualization.get("categories")
        series = visualization.get("series")
        if isinstance(categories, list) and isinstance(series, list):
            for index, item in enumerate(series):
                if not isinstance(item, Mapping):
                    continue
                values = item.get("values")
                if isinstance(values, list) and len(values) != len(categories):
                    issues.append(
                        Issue(
                            "error",
                            "CHART.LENGTH_MISMATCH",
                            f"$.series[{index}].values",
                            f"has {len(values)} values but categories has {len(categories)}",
                        )
                    )
            forecast_index = visualization.get("forecast_start_index")
            if isinstance(forecast_index, int) and not (
                0 <= forecast_index < len(categories)
            ):
                issues.append(
                    Issue(
                        "error",
                        "CHART.INVALID_FORECAST_INDEX",
                        "$.forecast_start_index",
                        "must point to an existing category",
                    )
                )

    if "columns" in visualization:
        columns = visualization.get("columns")
        rows = visualization.get("rows")
        if isinstance(columns, list) and isinstance(rows, list):
            for index, row in enumerate(rows):
                if isinstance(row, list) and len(row) != len(columns):
                    issues.append(
                        Issue(
                            "error",
                            "TABLE.ROW_LENGTH_MISMATCH",
                            f"$.rows[{index}]",
                            f"has {len(row)} cells but columns has {len(columns)}",
                        )
                    )

    return issues


def validate_visualization(
    visualization: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> list[Issue]:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise InputError(f"invalid JSON Schema: {exc.message}") from exc

    issues = [
        Issue(
            "error",
            "SCHEMA.INVALID",
            json_path(error.absolute_path),
            error.message,
        )
        for error in Draft202012Validator(schema).iter_errors(visualization)
    ]
    issues.extend(semantic_issues(visualization))
    return sorted(issues, key=lambda item: (item.path, item.code))

"""Resolve semantic visual candidates into evidence-backed Visualization JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator

from ppt_engine.layout_resolver import load_layout_map, resolve_outline


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = PROJECT_ROOT / "schemas" / "visualization.schema.json"
DEFAULT_LAYOUT_MAP = PROJECT_ROOT / "templates" / "template_layout_map.json"
_CITATION_RE = re.compile(r"\[\^[^\]]+\]")
_MARKDOWN_RE = re.compile(r"[*_`~]+")
_NUMBER_RE = re.compile(r"^[+\-]?\d+(?:\.\d+)?$")
_PERIOD_RE = re.compile(r"((?:19|20)\d{2})(?:\u5e74|\u5e74\u672b|[AE])?")
_UNITS = ("\u4ebf\u5143", "\u4e07\u5143", "%", "\u500d", "\u9897")


@dataclass(frozen=True)
class GenerationIssue:
    slide_id: str
    candidate_id: str
    visual_type: str
    reason: str

    def format(self) -> str:
        return (
            "[visualization-warning]\n"
            f"slide_id={self.slide_id}\n"
            f"required_visual={self.visual_type}\n"
            f"candidate_id={self.candidate_id}\n"
            f"reason={self.reason}"
        )


@dataclass(frozen=True)
class VisualizationArtifact:
    slide_id: str
    candidate_id: str
    source_block_id: str
    data: dict[str, Any]


@dataclass(frozen=True)
class VisualizationCoverageWarning:
    slide_id: str
    required_visual: str
    layout_id: str
    reason: str

    def format(self) -> str:
        return (
            "[visualization-warning]\n"
            f"slide_id={self.slide_id}\n"
            f"required_visual={self.required_visual}\n"
            f"layout_id={self.layout_id}\n"
            f"reason={self.reason}"
        )


def _clean_text(value: Any) -> str:
    text = _CITATION_RE.sub("", str(value or ""))
    return _MARKDOWN_RE.sub("", text).strip()


def _cell_value(value: Any) -> str | int | float | None:
    text = _clean_text(value).replace(",", "")
    if not text or text in {"-", "--", "N/A", "n/a"}:
        return None
    if text.endswith("%"):
        return text
    if _NUMBER_RE.fullmatch(text):
        number = float(text)
        return int(number) if number.is_integer() else number
    return text


def _numeric_value(value: Any) -> float | None:
    text = _clean_text(value).replace(",", "").replace("~", "")
    for unit in _UNITS:
        text = text.replace(unit, "")
    match = re.search(r"[+\-]?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def _terms(text: str) -> set[str]:
    result = {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9]+", text)
        if len(token) >= 2
    }
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        result.update(chunk[index : index + 2] for index in range(len(chunk) - 1))
    return result


def _block_text(block: Mapping[str, Any]) -> str:
    sections = " ".join(
        str(item.get("title", ""))
        for item in block.get("section_path", [])
        if isinstance(item, Mapping)
    )
    if block.get("type") == "table":
        content = " ".join(
            [*(str(value) for value in block.get("columns", []))]
            + [str(cell) for row in block.get("rows", []) for cell in row]
        )
    else:
        content = str(block.get("text", block.get("raw_text", "")))
    return f"{sections} {content}"


def _relevance(query: str, block: Mapping[str, Any]) -> int:
    return len(_terms(query) & _terms(_block_text(block)))


def _query(slide: Mapping[str, Any], candidate: Mapping[str, Any]) -> str:
    return " ".join(
        str(value)
        for value in (
            candidate.get("description", ""),
            slide.get("title", ""),
            slide.get("key_message", ""),
            slide.get("section", ""),
        )
    )


def _source_refs(slide: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[str]:
    values = candidate.get("source_refs") or slide.get("source_refs") or []
    return list(dict.fromkeys(str(value) for value in values if isinstance(value, str)))


def _best_blocks(
    document: Mapping[str, Any], query: str, block_types: set[str]
) -> list[tuple[int, Mapping[str, Any]]]:
    scored = [
        (_relevance(query, block), block)
        for block in document.get("blocks", [])
        if isinstance(block, Mapping) and block.get("type") in block_types
    ]
    return sorted(scored, key=lambda item: item[0], reverse=True)


def _table_visualization(
    slide: Mapping[str, Any],
    candidate: Mapping[str, Any],
    document: Mapping[str, Any],
) -> tuple[dict[str, Any], str] | None:
    blocks = _best_blocks(document, _query(slide, candidate), {"table"})
    if not blocks or blocks[0][0] < 2:
        return None
    _, block = blocks[0]
    columns = [_clean_text(value) or "Item" for value in block.get("columns", [])][:6]
    rows = [
        [_cell_value(cell) for cell in row[: len(columns)]]
        for row in block.get("rows", [])[:8]
        if isinstance(row, list) and len(row) >= len(columns)
    ]
    refs = _source_refs(slide, candidate)
    if not columns or not rows or not refs:
        return None
    block_id = str(block.get("block_id", ""))
    return (
        {
            "title": str(candidate.get("description") or slide.get("title") or "Data table"),
            "columns": columns,
            "rows": rows,
            "source_refs": refs,
            "note": f"Extracted from Parsed Document block {block_id}",
        },
        block_id,
    )


def _infer_unit(text: str) -> str:
    return next((unit for unit in _UNITS if unit in text), "")


def _infer_chart_type(text: str, categories: Sequence[str]) -> str:
    trend_words = ("\u8d8b\u52bf", "\u589e\u957f", "\u53d8\u5316", "\u9884\u6d4b")
    if any(word in text for word in trend_words) or sum(bool(_PERIOD_RE.search(v)) for v in categories) >= 2:
        return "line"
    return "bar" if "\u5360\u6bd4" in text else "column"


def _chart_from_table(
    slide: Mapping[str, Any],
    candidate: Mapping[str, Any],
    block: Mapping[str, Any],
) -> dict[str, Any] | None:
    columns = [_clean_text(value) for value in block.get("columns", [])]
    rows = [row for row in block.get("rows", []) if isinstance(row, list)]
    query = _query(slide, candidate)
    period_indices = [index for index, value in enumerate(columns) if _PERIOD_RE.search(value)]
    categories: list[str] = []
    series: list[dict[str, Any]] = []

    if len(period_indices) >= 2:
        period_indices = period_indices[:8]
        categories = [columns[index] for index in period_indices]
        ranked_rows = sorted(
            rows,
            key=lambda row: len(_terms(query) & _terms(str(row[0]) if row else "")),
            reverse=True,
        )
        for row in ranked_rows:
            if not row:
                continue
            values = [_numeric_value(row[index]) if index < len(row) else None for index in period_indices]
            if sum(value is not None for value in values) >= 2:
                series.append({"name": _clean_text(row[0]) or "Series", "values": values})
            if len(series) == 3:
                break
    elif len(columns) >= 2:
        usable_rows = [row for row in rows[:8] if row]
        categories = [_clean_text(row[0]) for row in usable_rows]
        for column_index, column in enumerate(columns[1:4], start=1):
            values = [
                _numeric_value(row[column_index]) if column_index < len(row) else None
                for row in usable_rows
            ]
            if sum(value is not None for value in values) >= 2:
                series.append({"name": column or "Value", "values": values})

    refs = _source_refs(slide, candidate)
    if not categories or not series or not refs:
        return None
    block_id = str(block.get("block_id", ""))
    return {
        "chart_type": _infer_chart_type(query, categories),
        "title": str(candidate.get("description") or slide.get("title") or "Data chart"),
        "unit": _infer_unit(" ".join(columns) + " " + query),
        "categories": categories,
        "series": series,
        "source_refs": refs,
        "note": f"Extracted from Parsed Document block {block_id}",
    }


def _paragraph_pairs(text: str) -> tuple[list[str], list[float], str]:
    clean = _clean_text(text)
    unit_pattern = "|".join(re.escape(unit) for unit in _UNITS)
    time_pairs = re.findall(
        rf"((?:19|20)\d{{2}})(?:\u5e74|\u5e74\u672b|[AE])?[^,，。；]{{0,18}}?"
        rf"([+\-]?\d+(?:\.\d+)?)\s*({unit_pattern})",
        clean,
    )
    if len(time_pairs) >= 2:
        unit = time_pairs[0][2]
        pairs = [(year, float(value)) for year, value, item_unit in time_pairs if item_unit == unit]
        unique = list(dict.fromkeys(pairs))[:8]
        return [item[0] for item in unique], [item[1] for item in unique], unit

    parenthetical = re.findall(
        rf"([A-Za-z\u4e00-\u9fff]{{2,16}})[(（]([+\-]?\d+(?:\.\d+)?)\s*"
        rf"({unit_pattern})[)）]",
        clean,
    )
    if len(parenthetical) >= 2:
        unit = parenthetical[0][2]
        values = [item for item in parenthetical if item[2] == unit][:8]
        return [item[0][-12:] for item in values], [float(item[1]) for item in values], unit
    return [], [], ""


def _chart_visualization(
    slide: Mapping[str, Any],
    candidate: Mapping[str, Any],
    document: Mapping[str, Any],
) -> tuple[dict[str, Any], str] | None:
    query = _query(slide, candidate)
    for score, block in _best_blocks(document, query, {"table", "paragraph", "blockquote"}):
        if score < 2:
            break
        block_id = str(block.get("block_id", ""))
        if block.get("type") == "table":
            chart = _chart_from_table(slide, candidate, block)
            if chart is not None:
                return chart, block_id
            continue
        categories, values, unit = _paragraph_pairs(str(block.get("text", block.get("raw_text", ""))))
        refs = _source_refs(slide, candidate)
        if len(categories) >= 2 and refs:
            return (
                {
                    "chart_type": _infer_chart_type(query, categories),
                    "title": str(candidate.get("description") or slide.get("title") or "Data chart"),
                    "unit": unit,
                    "categories": categories,
                    "series": [{"name": str(slide.get("title") or "Value"), "values": values}],
                    "source_refs": refs,
                    "note": f"Extracted from Parsed Document block {block_id}",
                },
                block_id,
            )
    return None


def _validate_visualization(data: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    errors = list(Draft202012Validator(schema).iter_errors(data))
    if errors:
        raise ValueError(f"generated Visualization JSON is invalid: {errors[0].message}")


def generate_visualizations(
    outline: Mapping[str, Any],
    document: Mapping[str, Any],
    *,
    schema: Mapping[str, Any] | None = None,
) -> tuple[list[VisualizationArtifact], list[GenerationIssue]]:
    """Generate all traceable chart/table objects requested by an outline."""

    schema = schema or json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    artifacts: list[VisualizationArtifact] = []
    issues: list[GenerationIssue] = []
    for slide in outline.get("slides", []):
        if not isinstance(slide, Mapping):
            continue
        slide_id = str(slide.get("slide_id", ""))
        for candidate in slide.get("visual_candidates", []):
            if not isinstance(candidate, Mapping):
                continue
            candidate_id = str(candidate.get("candidate_id", ""))
            visual_type = str(candidate.get("type", ""))
            generated = (
                _chart_visualization(slide, candidate, document)
                if visual_type == "chart"
                else _table_visualization(slide, candidate, document)
                if visual_type == "table"
                else None
            )
            if generated is None:
                issues.append(
                    GenerationIssue(
                        slide_id,
                        candidate_id,
                        visual_type or "unknown",
                        "no_traceable_source_data",
                    )
                )
                continue
            data, block_id = generated
            _validate_visualization(data, schema)
            artifacts.append(VisualizationArtifact(slide_id, candidate_id, block_id, data))
    return artifacts, issues


def bindings_from_artifacts(
    artifacts: Iterable[VisualizationArtifact],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for artifact in artifacts:
        result.setdefault(artifact.slide_id, []).append(artifact.data)
    return result


def _visual_type(data: Mapping[str, Any]) -> str | None:
    if "chart_type" in data:
        return "chart"
    if "columns" in data:
        return "table"
    return None


def preflight_visualizations(
    outline: Mapping[str, Any],
    layout_map: Mapping[str, Any],
    bindings: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[VisualizationCoverageWarning]:
    """Report visual candidate/slot pairs with no bound Visualization JSON."""

    resolutions = {
        item.slide_id: item
        for item in resolve_outline(
            outline,
            visualizations_by_slide=bindings,
            layout_map=layout_map,
            debug=False,
        )
    }
    warnings: list[VisualizationCoverageWarning] = []
    for slide in outline.get("slides", []):
        if not isinstance(slide, Mapping):
            continue
        slide_id = str(slide.get("slide_id", ""))
        resolution = resolutions.get(slide_id)
        if resolution is None:
            continue
        fields = layout_map["layouts"][resolution.layout_id].get("fields", {})
        supported = {
            "chart" if spec.get("type") == "chart_slot" else "table"
            for spec in fields.values()
            if isinstance(spec, Mapping) and spec.get("type") in {"chart_slot", "table"}
        }
        requested = {
            str(candidate.get("type"))
            for candidate in slide.get("visual_candidates", [])
            if isinstance(candidate, Mapping) and candidate.get("type") in {"chart", "table"}
        }
        available = {
            visual_type
            for item in bindings.get(slide_id, [])
            if (visual_type := _visual_type(item)) is not None
        }
        for visual_type in sorted((requested & supported) - available):
            warnings.append(
                VisualizationCoverageWarning(
                    slide_id,
                    visual_type,
                    resolution.layout_id,
                    f"no_{visual_type}_visualization_data",
                )
            )
    return warnings


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} root must be an object")
    return value


def warn_for_render_args(argv: Sequence[str]) -> None:
    """Emit non-blocking coverage warnings before the Renderer CLI is entered."""

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("outline", type=Path)
    parser.add_argument("-o", "--output")
    parser.add_argument("--template")
    parser.add_argument("--layout-map", type=Path, default=DEFAULT_LAYOUT_MAP)
    parser.add_argument("--visualization", action="append", default=[])
    try:
        args, _ = parser.parse_known_args(argv)
        outline = _load_json(args.outline, "outline")
        layout_map = load_layout_map(args.layout_map)
        bindings: dict[str, list[dict[str, Any]]] = {}
        for item in args.visualization:
            if "=" not in item:
                continue
            slide_id, path = item.split("=", 1)
            bindings.setdefault(slide_id, []).append(_load_json(Path(path), "visualization"))
        for warning in preflight_visualizations(outline, layout_map, bindings):
            print(warning.format(), file=sys.stderr)
    except (OSError, ValueError):
        # The Renderer remains the authority for command/file validation.
        return


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_.-") or "visualization"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate schema-valid Visualization JSON from Outline candidates"
    )
    parser.add_argument("outline", type=Path, help="Slide Outline JSON")
    parser.add_argument("document", type=Path, help="Parsed Document JSON")
    parser.add_argument("-o", "--output-dir", type=Path, required=True)
    parser.add_argument("--layout-map", type=Path, default=DEFAULT_LAYOUT_MAP)
    args = parser.parse_args(argv)
    try:
        outline = _load_json(args.outline, "outline")
        document = _load_json(args.document, "parsed document")
        layout_map = load_layout_map(args.layout_map)
        artifacts, issues = generate_visualizations(outline, document)
        bindings = bindings_from_artifacts(artifacts)
        coverage = preflight_visualizations(outline, layout_map, bindings)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, Any] = {"schema_version": "1.0", "bindings": []}
        for artifact in artifacts:
            filename = f"{_safe_name(artifact.slide_id)}__{_safe_name(artifact.candidate_id)}.json"
            output = args.output_dir / filename
            output.write_text(
                json.dumps(artifact.data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest["bindings"].append(
                {
                    "slide_id": artifact.slide_id,
                    "candidate_id": artifact.candidate_id,
                    "source_block_id": artifact.source_block_id,
                    "visualization_file": filename,
                }
            )
            print(f"Created: {output}")
            print(f"Render argument: --visualization {artifact.slide_id}={output}")
        manifest_path = args.output_dir / "visualization_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Created manifest: {manifest_path}")
        for issue in issues:
            print(issue.format(), file=sys.stderr)
        for warning in coverage:
            print(warning.format(), file=sys.stderr)
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

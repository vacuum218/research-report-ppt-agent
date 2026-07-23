"""Render frozen Outline/Visualization/Layout Map contracts to a PPTX."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator
from pptx import Presentation

from tools.validate_outline import semantic_issues
from tools.validate_visualization import semantic_issues as visualization_semantic_issues

from .layout_resolver import LayoutResolutionError, load_layout_map, resolve_outline, validate_layout_map
from .slide_builder import SlideBuildError, duplicate_slide, populate_slide, remove_slide


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = PROJECT_ROOT / "templates" / "financial_report_template_v1.pptx"
DEFAULT_LAYOUT_MAP = PROJECT_ROOT / "templates" / "template_layout_map.json"
OUTLINE_SCHEMA = PROJECT_ROOT / "schemas" / "slide_outline.schema.json"
VISUALIZATION_SCHEMA = PROJECT_ROOT / "schemas" / "visualization.schema.json"


class RenderError(RuntimeError):
    """Raised when rendering cannot produce a valid PPTX."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise RenderError(f"cannot load {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RenderError(f"{label} root must be an object: {path}")
    return value


def _validate_instance(value: Mapping[str, Any], schema_path: Path, label: str) -> None:
    schema = _load_json(schema_path, f"{label} schema")
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.absolute_path))
    if errors:
        raise RenderError(f"{label} schema validation failed: {errors[0].message}")


def _load_visualizations(items: Sequence[str]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if "=" not in item:
            raise RenderError("--visualization must use slide_id=path.json")
        slide_id, raw_path = item.split("=", 1)
        if not slide_id or not raw_path:
            raise RenderError("--visualization must use slide_id=path.json")
        visualization = _load_json(Path(raw_path), "visualization")
        _validate_instance(visualization, VISUALIZATION_SCHEMA, "visualization")
        if visualization_semantic_issues(visualization):
            issue = visualization_semantic_issues(visualization)[0]
            raise RenderError(f"visualization semantic validation failed: {issue.message}")
        result.setdefault(slide_id, []).append(visualization)
    return result


def render_ppt(
    outline: Mapping[str, Any],
    *,
    template_path: Path = DEFAULT_TEMPLATE,
    layout_map_path: Path = DEFAULT_LAYOUT_MAP,
    visualizations_by_slide: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    asset_root: Path | None = None,
    output_path: Path,
) -> Path:
    """Render a semantic outline into a new PPTX using the supplied template."""

    _validate_instance(outline, OUTLINE_SCHEMA, "outline")
    outline_issues = [issue for issue in semantic_issues(outline) if issue.severity == "error"]
    if outline_issues:
        raise RenderError(f"outline semantic validation failed: {outline_issues[0].message}")
    layout_map = load_layout_map(layout_map_path)
    map_errors = validate_layout_map(layout_map)
    if map_errors:
        raise RenderError(f"layout map validation failed: {map_errors[0]}")
    visualizations_by_slide = visualizations_by_slide or {}
    outline_slide_ids = {
        str(slide.get("slide_id"))
        for slide in outline.get("slides", [])
        if isinstance(slide, Mapping)
    }
    unknown_slide_ids = set(visualizations_by_slide) - outline_slide_ids
    if unknown_slide_ids:
        raise RenderError(f"unknown slide_id: {sorted(unknown_slide_ids)[0]}")
    for slide_id, values in visualizations_by_slide.items():
        for visualization in values:
            _validate_instance(visualization, VISUALIZATION_SCHEMA, f"visualization for {slide_id}")
            issues = visualization_semantic_issues(visualization)
            if issues:
                raise RenderError(f"visualization semantic validation failed: {issues[0].message}")

    try:
        resolutions = resolve_outline(
            outline,
            visualizations_by_slide=visualizations_by_slide,
            layout_map=layout_map,
        )
        prs = Presentation(str(template_path))
    except (OSError, LayoutResolutionError) as exc:
        raise RenderError(str(exc)) from exc

    template_slide_count = len(prs.slides)
    slides = outline.get("slides", [])
    metadata = outline.get("metadata", {})
    try:
        for page_number, (outline_slide, resolution) in enumerate(zip(slides, resolutions), start=1):
            source = prs.slides[resolution.template_slide - 1]
            target = duplicate_slide(prs, source)
            layout = dict(layout_map["layouts"][resolution.layout_id])
            layout["layout_id"] = resolution.layout_id
            populate_slide(
                target,
                layout,
                outline_slide,
                metadata=metadata,
                visualizations=visualizations_by_slide.get(str(outline_slide.get("slide_id")), ()),
                page_number=page_number,
                asset_root=asset_root,
            )
        for index in range(template_slide_count - 1, -1, -1):
            remove_slide(prs, index)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(output_path))
    except (KeyError, IndexError, OSError, SlideBuildError, ValueError) as exc:
        raise RenderError(f"failed to render PPTX: {exc}") from exc
    return output_path


def render_presentation(
    outline: Mapping[str, Any],
    layout_map: Mapping[str, Any],
    template_path: Path,
    output_path: Path,
    *,
    visualizations_by_slide: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    asset_root: Path | None = None,
) -> Path:
    """Compatibility API used by integration callers and tests."""

    slide_ids = {
        str(slide.get("slide_id"))
        for slide in outline.get("slides", [])
        if isinstance(slide, Mapping)
    }
    visualizations_by_slide = visualizations_by_slide or {}
    unknown = set(visualizations_by_slide) - slide_ids
    if unknown:
        raise RenderError(f"unknown slide_id: {sorted(unknown)[0]}")

    _validate_instance(outline, OUTLINE_SCHEMA, "outline")
    map_errors = validate_layout_map(layout_map)
    if map_errors:
        raise RenderError(f"layout map validation failed: {map_errors[0]}")
    for slide_id, values in visualizations_by_slide.items():
        for visualization in values:
            _validate_instance(visualization, VISUALIZATION_SCHEMA, f"visualization for {slide_id}")
            issues = visualization_semantic_issues(visualization)
            if issues:
                raise RenderError(f"visualization semantic validation failed: {issues[0].message}")

    # Use a temporary in-memory path-independent rendering flow while preserving
    # the public positional signature established for T2.4.
    # This mirrors render_ppt but receives an already loaded Layout Map.
    from pptx import Presentation as _Presentation

    try:
        resolutions = resolve_outline(
            outline,
            visualizations_by_slide=visualizations_by_slide,
            layout_map=layout_map,
        )
        prs = _Presentation(str(template_path))
    except (OSError, LayoutResolutionError) as exc:
        raise RenderError(str(exc)) from exc
    template_slide_count = len(prs.slides)
    metadata = outline.get("metadata", {})
    try:
        for page_number, (outline_slide, resolution) in enumerate(
            zip(outline.get("slides", []), resolutions), start=1
        ):
            source = prs.slides[resolution.template_slide - 1]
            target = duplicate_slide(prs, source)
            layout = dict(layout_map["layouts"][resolution.layout_id])
            layout["layout_id"] = resolution.layout_id
            populate_slide(
                target,
                layout,
                outline_slide,
                metadata=metadata,
                visualizations=visualizations_by_slide.get(str(outline_slide.get("slide_id")), ()),
                page_number=page_number,
                asset_root=asset_root,
            )
        for index in range(template_slide_count - 1, -1, -1):
            remove_slide(prs, index)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(output_path))
    except (KeyError, IndexError, OSError, SlideBuildError, ValueError) as exc:
        raise RenderError(f"failed to render PPTX: {exc}") from exc
    return output_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Slide Outline JSON to a template-backed PPTX")
    parser.add_argument("outline", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--layout-map", type=Path, default=DEFAULT_LAYOUT_MAP)
    parser.add_argument(
        "--asset-root",
        type=Path,
        help="DocumentBundle directory used to resolve original figure asset paths",
    )
    parser.add_argument(
        "--visualization",
        action="append",
        default=[],
        metavar="SLIDE_ID=PATH",
        help="Bind one Visualization JSON object to a slide; repeat for multiple objects",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        outline = _load_json(args.outline, "outline")
        visualizations = _load_visualizations(args.visualization)
        output = render_ppt(
            outline,
            template_path=args.template,
            layout_map_path=args.layout_map,
            visualizations_by_slide=visualizations,
            asset_root=args.asset_root,
            output_path=args.output,
        )
    except RenderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Created: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

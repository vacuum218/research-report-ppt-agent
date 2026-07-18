#!/usr/bin/env python3
"""Build a semantic layout map from a PowerPoint object inventory.

The input file is produced by ``inspect_template.py``.  This script keeps only
the objects that a renderer needs to control and enriches each semantic field
with the object's shape id, path, type and bounds.

Usage:
    python build_layout_map.py template_objects.json \
        --output template_layout_map.json

No third-party dependencies are required.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SCHEMA_VERSION = "1.0"


class LayoutMapError(RuntimeError):
    """Raised when the inventory cannot satisfy the semantic specification."""


def text(target: str, *, required: bool = True, max_chars: Optional[int] = None,
         action: str = "set_text", **extra: Any) -> Dict[str, Any]:
    spec: Dict[str, Any] = {
        "type": "text",
        "action": action,
        "required": required,
        "target": target,
    }
    if max_chars is not None:
        spec["max_chars"] = max_chars
    spec.update(extra)
    return spec


def bullet_list(target: str, *, required: bool = True, min_items: int = 1,
                max_items: int = 4, max_chars_per_item: Optional[int] = None,
                **extra: Any) -> Dict[str, Any]:
    spec: Dict[str, Any] = {
        "type": "bullet_list",
        "action": "set_text",
        "required": required,
        "target": target,
        "min_items": min_items,
        "max_items": max_items,
    }
    if max_chars_per_item is not None:
        spec["max_chars_per_item"] = max_chars_per_item
    spec.update(extra)
    return spec


def repeated_group(targets: Sequence[Mapping[str, str]], *, required: bool = True,
                   min_items: int = 1, max_items: Optional[int] = None,
                   limits: Optional[Mapping[str, int]] = None,
                   action: str = "set_repeated_text", **extra: Any) -> Dict[str, Any]:
    spec: Dict[str, Any] = {
        "type": "repeated_group",
        "action": action,
        "required": required,
        "min_items": min_items,
        "max_items": max_items if max_items is not None else len(targets),
        "targets": [dict(item) for item in targets],
        "empty_item_action": "clear",
    }
    if limits:
        spec["limits"] = dict(limits)
    spec.update(extra)
    return spec


def chart_slot(anchor: str, title_target: str, *, required: bool = True,
               max_categories: int = 8, max_series: int = 3,
               title_max_chars: int = 18, **extra: Any) -> Dict[str, Any]:
    spec: Dict[str, Any] = {
        "type": "chart_slot",
        "action": "render_chart",
        "required": required,
        "anchor": anchor,
        "title_target": title_target,
        "replace_mode": "recreate",
        "max_categories": max_categories,
        "max_series": max_series,
        "title_max_chars": title_max_chars,
    }
    spec.update(extra)
    return spec


def table_slot(target: str, *, required: bool = True, max_rows: int,
               max_columns: int, overflow: str = "truncate_or_appendix",
               **extra: Any) -> Dict[str, Any]:
    spec: Dict[str, Any] = {
        "type": "table",
        "action": "fill_table",
        "required": required,
        "target": target,
        "max_rows": max_rows,
        "max_columns": max_columns,
        "preserve_style": True,
        "overflow": overflow,
    }
    spec.update(extra)
    return spec


def numbered_targets(prefix: str, count: int, fields: Sequence[str]) -> List[Dict[str, str]]:
    return [
        {field: f"{prefix}_{index}_{field}" for field in fields}
        for index in range(1, count + 1)
    ]


def lettered_targets(prefix: str, letters: Sequence[str], fields: Sequence[str]) -> List[Dict[str, str]]:
    return [
        {field: f"{prefix}_{letter}_{field}" for field in fields}
        for letter in letters
    ]


EXECUTIVE_METRICS = [
    {
        "value": "metric_2026E营收增速_value",
        "label": "metric_2026E营收增速_label",
        "note": "metric_2026E营收增速_note",
    },
    {
        "value": "metric_2026E毛利率_value",
        "label": "metric_2026E毛利率_label",
        "note": "metric_2026E毛利率_note",
    },
    {
        "value": "metric_未来利润CAGR_value",
        "label": "metric_未来利润CAGR_label",
        "note": "metric_未来利润CAGR_note",
    },
    {
        "value": "metric_2026E PE_value",
        "label": "metric_2026E PE_label",
        "note": "metric_2026E PE_note",
    },
]

FINANCIAL_METRICS = [
    {
        "value": "metric_2024A毛利率_value",
        "label": "metric_2024A毛利率_label",
        "note": "metric_2024A毛利率_note",
    },
    {
        "value": "metric_真实净利率中枢_value",
        "label": "metric_真实净利率中枢_label",
        "note": "metric_真实净利率中枢_note",
    },
    {
        "value": "metric_经营现金流_value",
        "label": "metric_经营现金流_label",
        "note": "metric_经营现金流_note",
    },
]


def standard_fields(*, source: bool = True) -> Dict[str, Dict[str, Any]]:
    fields: Dict[str, Dict[str, Any]] = {
        "title": text("title", max_chars=24),
        "page_number": {
            "type": "auto",
            "action": "set_page_number",
            "required": True,
            "target": "page_no",
        },
    }
    if source:
        fields["source_refs"] = {
            "type": "source_list",
            "action": "set_text",
            "required": False,
            "target": "source",
            "max_items": 3,
        }
    return fields


def layout_definitions() -> Dict[str, Dict[str, Any]]:
    """Return the curated semantic specification for all 16 template pages."""

    definitions: Dict[str, Dict[str, Any]] = {
        "cover": {
            "template_slide": 1,
            "description": "财报封面",
            "fields": {
                "cover_title": {
                    "type": "composite_text",
                    "action": "format_text",
                    "required": True,
                    "target": "cover_title",
                    "inputs": ["company_name", "report_title"],
                    "format": "{company_name}\n{report_title}",
                    "max_chars": 36,
                },
                "subtitle": text("cover_subtitle", required=False, max_chars=30),
                "cover_meta": {
                    "type": "composite_text",
                    "action": "format_text",
                    "required": True,
                    "target": "cover_meta",
                    "inputs": ["stock_code", "report_date", "presenter"],
                    "format": "{stock_code}  |  {report_date}  |  {presenter}",
                    "max_chars": 48,
                },
                "tag": text("cover_tag", required=False, max_chars=12),
            },
        },
        "agenda": {
            "template_slide": 2,
            "description": "报告目录",
            "fields": {
                **standard_fields(source=False),
                "items": repeated_group(
                    [
                        {
                            "number": f"agenda_no_{i}",
                            "title": f"agenda_title_{i}",
                            "description": f"agenda_desc_{i}",
                        }
                        for i in range(1, 7)
                    ],
                    min_items=3,
                    max_items=6,
                    limits={"number": 2, "title": 8, "description": 20},
                ),
            },
        },
        "executive_summary": {
            "template_slide": 3,
            "description": "核心结论、投资逻辑和关键指标",
            "fields": {
                **standard_fields(),
                "thesis": text("thesis", max_chars=45),
                "logics": repeated_group(
                    numbered_targets("logic", 3, ("title", "body")),
                    max_items=3,
                    limits={"title": 10, "body": 45},
                ),
                "metrics": repeated_group(
                    EXECUTIVE_METRICS,
                    max_items=4,
                    limits={"label": 12, "note": 15},
                ),
            },
        },
        "company_overview": {
            "template_slide": 4,
            "description": "公司定位、主营业务和规模",
            "fields": {
                **standard_fields(),
                "company_name": text("company_name", max_chars=12),
                "company_code": text("company_code", required=False, max_chars=12),
                "company_positioning": text("company_positioning", max_chars=90),
                "segments": repeated_group(
                    lettered_targets("business", ("a", "b", "c"), ("title", "body")),
                    max_items=3,
                    limits={"title": 10, "body": 45},
                ),
                "key_metric": repeated_group([
                    {
                        "value": "metric_年度营业收入_value",
                        "label": "metric_年度营业收入_label",
                        "note": "metric_年度营业收入_note",
                    }
                ], required=False, min_items=0, max_items=1,
                    limits={"label": 12, "note": 15}),
            },
        },
        "timeline": {
            "template_slide": 5,
            "description": "发展阶段、技术路线或战略演进",
            "fields": {
                **standard_fields(source=False),
                "milestones": repeated_group(
                    [
                        {
                            "stage": f"timeline_stage_{i}",
                            "title": f"timeline_title_{i}",
                            "description": f"timeline_body_{i}",
                        }
                        for i in range(1, 5)
                    ],
                    min_items=3,
                    max_items=4,
                    limits={"stage": 8, "title": 12, "description": 25},
                ),
                "takeaway": text("timeline_takeaway", required=False, max_chars=40),
            },
        },
        "business_structure": {
            "template_slide": 6,
            "description": "分业务收入、占比、毛利率或增速对比",
            "fields": {
                **standard_fields(),
                "chart_left": chart_slot("chart_left_panel", "chart_left_title"),
                "chart_right": chart_slot("chart_right_panel", "chart_right_title"),
            },
        },
        "industry_outlook": {
            "template_slide": 7,
            "description": "行业空间、渗透率、景气度或资本开支趋势",
            "fields": {
                **standard_fields(),
                "chart": chart_slot("industry_chart_panel", "industry_chart_title"),
                "drivers": repeated_group(
                    numbered_targets("driver", 3, ("title", "body")),
                    min_items=2,
                    max_items=3,
                    limits={"title": 8, "body": 35},
                ),
            },
        },
        "competitive_landscape": {
            "template_slide": 8,
            "description": "二维定位、竞争对比和护城河",
            "fields": {
                **standard_fields(),
                "matrix": {
                    "type": "matrix",
                    "action": "position_matrix_points",
                    "required": True,
                    "anchor": "matrix_panel",
                    "axis_targets": {
                        "x_axis": "matrix_x_label",
                        "y_axis": "matrix_y_label",
                    },
                    "point_targets": [
                        {"point": f"matrix_point_{i}", "label": f"matrix_label_{i}"}
                        for i in range(1, 5)
                    ],
                    "min_items": 3,
                    "max_items": 4,
                    "limits": {"x_axis": 12, "y_axis": 12, "label": 12},
                },
                "moats": repeated_group(
                    numbered_targets("moat", 3, ("title", "body")),
                    max_items=3,
                    limits={"title": 10, "body": 35},
                ),
            },
        },
        "chart_text": {
            "template_slide": 9,
            "description": "一张核心图表配解释与结论",
            "fields": {
                **standard_fields(),
                "chart": chart_slot("logic_chart_panel", "logic_chart_title"),
                "takeaway": text("logic_main_point", max_chars=25),
                "bullets": bullet_list("logic_bullets", min_items=2, max_items=4,
                                       max_chars_per_item=30),
                "conclusion": text("logic_conclusion_text", required=False, max_chars=35),
            },
        },
        "two_charts": {
            "template_slide": 10,
            "description": "两张相关图表共同支撑一个结论",
            "fields": {
                **standard_fields(),
                "chart_left": chart_slot("two_chart_left", "two_chart_left_title",
                                         title_max_chars=16),
                "chart_right": chart_slot("two_chart_right", "two_chart_right_title",
                                          title_max_chars=16),
                "conclusion": text("two_chart_conclusion", max_chars=45),
            },
        },
        "capability_map": {
            "template_slide": 11,
            "description": "能力、进展和商业兑现路径",
            "fields": {
                **standard_fields(),
                "stages": repeated_group(
                    numbered_targets("capability", 3, ("title", "body")),
                    max_items=3,
                    limits={"title": 12, "body": 70},
                ),
                "catalyst_path": bullet_list("catalyst_strip_body", min_items=3,
                                             max_items=5, max_chars_per_item=16),
            },
        },
        "financial_review": {
            "template_slide": 12,
            "description": "历史收入、利润率、现金流和经营质量",
            "fields": {
                **standard_fields(),
                "chart": chart_slot("financial_chart_panel", "financial_chart_title",
                                    max_categories=5, title_max_chars=20),
                "metrics": repeated_group(
                    FINANCIAL_METRICS,
                    max_items=3,
                    limits={"label": 12, "note": 18},
                ),
            },
        },
        "earnings_forecast": {
            "template_slide": 13,
            "description": "盈利预测表、趋势图和核心假设",
            "fields": {
                **standard_fields(),
                "source_refs": {
                    "type": "source_list",
                    "action": "set_text",
                    "required": True,
                    "target": "source",
                    "max_items": 3,
                },
                "note": text("forecast_note", required=False, max_chars=30),
                "table": table_slot("forecast_table", max_rows=7, max_columns=5),
                "chart": chart_slot("forecast_chart_panel", "forecast_chart_title",
                                    required=False),
                "assumptions": bullet_list("forecast_assumption", min_items=2,
                                           max_items=4, max_chars_per_item=22),
            },
        },
        "valuation": {
            "template_slide": 14,
            "description": "可比估值、历史估值或目标价值",
            "fields": {
                **standard_fields(),
                "chart": chart_slot("valuation_chart_panel", "valuation_chart_title"),
                "headline": text("valuation_headline", max_chars=30),
                "bullets": bullet_list("valuation_bullets", min_items=2,
                                       max_items=4, max_chars_per_item=30),
                "conclusion": text("valuation_conclusion_text", max_chars=35),
            },
        },
        "risk_catalyst": {
            "template_slide": 15,
            "description": "上行催化因素和结论失效条件",
            "fields": {
                **standard_fields(),
                "catalysts": repeated_group(
                    [{"number": f"catalyst_num_{i}", "text": f"catalyst_item_{i}"}
                     for i in range(1, 5)],
                    required=False,
                    min_items=0,
                    max_items=4,
                    limits={"text": 24},
                    auto_fields=["number"],
                ),
                "risks": repeated_group(
                    [{"number": f"risk_num_{i}", "text": f"risk_item_{i}"}
                     for i in range(1, 5)],
                    max_items=4,
                    limits={"text": 24},
                    auto_fields=["number"],
                ),
            },
        },
        "appendix": {
            "template_slide": 16,
            "description": "财务明细、统计口径和来源",
            "fields": {
                **standard_fields(),
                "source_refs": {
                    "type": "source_list",
                    "action": "set_text",
                    "required": True,
                    "target": "source",
                    "max_items": 5,
                },
                "table": table_slot("appendix_financial_table", max_rows=9,
                                    max_columns=5, overflow="new_slide"),
                "source_policy_title": text("appendix_sources_title", required=False,
                                            max_chars=12),
                "source_policy": text("appendix_sources", required=False, max_chars=80),
            },
        },
    }
    return definitions


def load_inventory(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LayoutMapError(f"Input file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LayoutMapError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise LayoutMapError("Inventory root must be a JSON object")
    if not isinstance(data.get("slides"), list):
        raise LayoutMapError("Inventory must contain a 'slides' array")
    return data


def object_summary(obj: Mapping[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "name": obj.get("name"),
        "shape_id": obj.get("shape_id"),
        "shape_type": obj.get("shape_type"),
        "path": obj.get("path"),
        "bounds_in": copy.deepcopy(obj.get("position_in")),
        "bounds_normalized": copy.deepcopy(obj.get("position_normalized")),
    }
    if obj.get("has_chart"):
        summary["chart"] = copy.deepcopy(obj.get("chart", {}))
    if obj.get("has_table"):
        summary["table"] = copy.deepcopy(obj.get("table", {}))
    return summary


def index_slide(slide: Mapping[str, Any]) -> Dict[str, List[Mapping[str, Any]]]:
    result: Dict[str, List[Mapping[str, Any]]] = {}
    for obj in slide.get("objects", []):
        name = obj.get("name")
        if isinstance(name, str):
            result.setdefault(name, []).append(obj)
    return result


def resolve_unique(name: str, index: Mapping[str, List[Mapping[str, Any]]], *,
                   context: str, errors: List[str], required: bool = True) -> Optional[Dict[str, Any]]:
    matches = index.get(name, [])
    if not matches:
        if required:
            errors.append(f"{context}: missing object '{name}'")
        return None
    if len(matches) > 1:
        errors.append(f"{context}: object name '{name}' is not unique ({len(matches)} matches)")
        return None
    return object_summary(matches[0])


def bounds(obj: Mapping[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    p = obj.get("position_in")
    if not isinstance(p, Mapping):
        return None
    try:
        return float(p["left"]), float(p["top"]), float(p["width"]), float(p["height"])
    except (KeyError, TypeError, ValueError):
        return None


def overlap_area(a: Tuple[float, float, float, float],
                 b: Tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    left = max(ax, bx)
    top = max(ay, by)
    return max(0.0, right - left) * max(0.0, bottom - top)


def match_template_chart(anchor_obj: Optional[Mapping[str, Any]],
                         chart_objects: Sequence[Mapping[str, Any]],
                         used_paths: set[str]) -> Optional[Dict[str, Any]]:
    if anchor_obj is None:
        return None
    anchor_bounds = bounds(anchor_obj)
    candidates: List[Tuple[float, Mapping[str, Any]]] = []
    for chart in chart_objects:
        path = str(chart.get("path", ""))
        if path in used_paths:
            continue
        chart_bounds = bounds(chart)
        score = overlap_area(anchor_bounds, chart_bounds) if anchor_bounds and chart_bounds else 0.0
        candidates.append((score, chart))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    score, chart = candidates[0]
    if score <= 0:
        return None
    used_paths.add(str(chart.get("path", "")))
    return object_summary(chart)


def resolve_field(field_name: str, field_spec: Mapping[str, Any],
                  index: Mapping[str, List[Mapping[str, Any]]],
                  chart_objects: Sequence[Mapping[str, Any]], used_chart_paths: set[str],
                  *, layout_id: str, warnings: List[str], errors: List[str]) -> Dict[str, Any]:
    resolved = copy.deepcopy(dict(field_spec))
    context = f"layout '{layout_id}', field '{field_name}'"
    required = bool(field_spec.get("required", True))
    field_type = field_spec.get("type")

    if field_type in {"text", "bullet_list", "source_list", "auto", "composite_text", "table"}:
        target_name = field_spec.get("target")
        if isinstance(target_name, str):
            target = resolve_unique(target_name, index, context=context, errors=errors, required=required)
            resolved["target"] = target
            if field_type == "table" and target and target.get("shape_type") != "TABLE":
                errors.append(f"{context}: target '{target_name}' is not a TABLE")

    elif field_type == "repeated_group":
        resolved_targets: List[Dict[str, Any]] = []
        for item_index, item in enumerate(field_spec.get("targets", []), start=1):
            resolved_item: Dict[str, Any] = {}
            for part_name, target_name in item.items():
                resolved_item[part_name] = resolve_unique(
                    target_name,
                    index,
                    context=f"{context}, item {item_index}.{part_name}",
                    errors=errors,
                    required=required,
                )
            resolved_targets.append(resolved_item)
        resolved["targets"] = resolved_targets

    elif field_type == "chart_slot":
        anchor_name = field_spec.get("anchor")
        title_name = field_spec.get("title_target")
        anchor_obj: Optional[Mapping[str, Any]] = None
        if isinstance(anchor_name, str):
            anchor_matches = index.get(anchor_name, [])
            if len(anchor_matches) == 1:
                anchor_obj = anchor_matches[0]
            resolved["anchor"] = resolve_unique(
                anchor_name, index, context=context, errors=errors, required=required
            )
        if isinstance(title_name, str):
            resolved["title_target"] = resolve_unique(
                title_name, index, context=context, errors=errors, required=required
            )
        resolved["template_chart"] = match_template_chart(
            anchor_obj, chart_objects, used_chart_paths
        )
        if resolved["template_chart"] is None:
            warnings.append(f"{context}: no overlapping template chart; anchor is still usable")

    elif field_type == "matrix":
        anchor_name = field_spec.get("anchor")
        if isinstance(anchor_name, str):
            resolved["anchor"] = resolve_unique(
                anchor_name, index, context=context, errors=errors, required=required
            )
        resolved_axes: Dict[str, Any] = {}
        for axis, target_name in field_spec.get("axis_targets", {}).items():
            resolved_axes[axis] = resolve_unique(
                target_name, index, context=f"{context}, axis {axis}", errors=errors,
                required=required
            )
        resolved["axis_targets"] = resolved_axes
        resolved_points: List[Dict[str, Any]] = []
        for item_index, item in enumerate(field_spec.get("point_targets", []), start=1):
            resolved_points.append({
                part: resolve_unique(
                    target_name, index,
                    context=f"{context}, point {item_index}.{part}",
                    errors=errors, required=required
                )
                for part, target_name in item.items()
            })
        resolved["point_targets"] = resolved_points

    else:
        errors.append(f"{context}: unsupported field type '{field_type}'")

    return resolved


def build_layout_map(inventory: Mapping[str, Any], *, strict: bool = True,
                     template_file: Optional[str] = None) -> Tuple[Dict[str, Any], List[str], List[str]]:
    definitions = layout_definitions()
    slides = inventory.get("slides", [])
    slide_by_number = {
        slide.get("slide_number"): slide
        for slide in slides
        if isinstance(slide, Mapping)
    }
    warnings: List[str] = []
    errors: List[str] = []
    layouts: Dict[str, Any] = {}

    for layout_id, definition in definitions.items():
        slide_number = definition["template_slide"]
        slide = slide_by_number.get(slide_number)
        if slide is None:
            errors.append(f"layout '{layout_id}': missing template slide {slide_number}")
            continue

        index = index_slide(slide)
        chart_objects = [obj for obj in slide.get("objects", []) if obj.get("has_chart")]
        used_chart_paths: set[str] = set()
        fields = {
            field_name: resolve_field(
                field_name,
                field_spec,
                index,
                chart_objects,
                used_chart_paths,
                layout_id=layout_id,
                warnings=warnings,
                errors=errors,
            )
            for field_name, field_spec in definition["fields"].items()
        }

        unused_charts = [
            object_summary(obj) for obj in chart_objects
            if str(obj.get("path", "")) not in used_chart_paths
        ]
        if unused_charts:
            warnings.append(
                f"layout '{layout_id}': {len(unused_charts)} template chart(s) were not matched"
            )

        layouts[layout_id] = {
            "template_slide": slide_number,
            "description": definition["description"],
            "fields": fields,
        }

    presentation = inventory.get("presentation", {})
    source_file = template_file or inventory.get("source_file") or "financial_report_template_v1.pptx"
    result: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "template_file": source_file,
        "presentation": {
            "slide_count": presentation.get("slide_count", len(slides)),
            "width_in": presentation.get("width_in"),
            "height_in": presentation.get("height_in"),
        },
        "rendering_policy": {
            "object_lookup": "name_then_shape_id",
            "chart_strategy": "recreate_inside_anchor",
            "preserve_decorative_objects": True,
            "clear_unused_repeated_items": True,
            "do_not_depend_on_source_path": True,
        },
        "layouts": layouts,
        "validation": {
            "layout_count": len(layouts),
            "warning_count": len(warnings),
            "error_count": len(errors),
            "warnings": warnings,
            "errors": errors,
        },
    }

    if strict and errors:
        raise LayoutMapError("\n".join(errors))
    return result, warnings, errors


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build template_layout_map.json from template_objects.json"
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the JSON file generated by inspect_template.py",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("template_layout_map.json"),
        help="Output path (default: template_layout_map.json)",
    )
    parser.add_argument(
        "--template-file",
        help="Override the PPTX filename stored in the output",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Write output even if required objects are missing",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation (default: 2)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        inventory = load_inventory(args.input)
        layout_map, warnings, errors = build_layout_map(
            inventory,
            strict=not args.no_strict,
            template_file=args.template_file,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(layout_map, ensure_ascii=False, indent=args.indent) + "\n",
            encoding="utf-8",
        )
    except LayoutMapError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Created: {args.output}")
    print(f"Layouts: {len(layout_map['layouts'])}")
    print(f"Warnings: {len(warnings)}")
    print(f"Errors: {len(errors)}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

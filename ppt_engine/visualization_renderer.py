"""Small python-pptx helpers for chart and table Visualization JSON."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Pt


class VisualizationRenderError(ValueError):
    """Raised for unsupported or inconsistent visualization data."""


def _chart_type(value: str):
    values = {
        "line": XL_CHART_TYPE.LINE_MARKERS,
        "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
        "bar": XL_CHART_TYPE.BAR_CLUSTERED,
        "area": XL_CHART_TYPE.AREA,
        "pie": XL_CHART_TYPE.PIE,
    }
    try:
        return values[value]
    except KeyError as exc:
        raise VisualizationRenderError(
            f"MVP chart renderer does not support chart_type={value!r}; use line, column, bar, area, or pie"
        ) from exc


def _chart_data(visualization: Mapping[str, Any]) -> CategoryChartData:
    categories = visualization.get("categories")
    series = visualization.get("series")
    if not isinstance(categories, list) or not isinstance(series, list) or not series:
        raise VisualizationRenderError("chart requires categories and at least one series")
    data = CategoryChartData()
    data.categories = [str(value) for value in categories]
    for item in series:
        if not isinstance(item, Mapping):
            raise VisualizationRenderError("each chart series must be an object")
        values = item.get("values")
        if not isinstance(values, list) or len(values) != len(categories):
            raise VisualizationRenderError("series values must match categories length")
        # python-pptx does not accept None as a chart point in all versions;
        # use an empty point for missing values while retaining the category.
        data.add_series(str(item.get("name", "Series")), [value if value is not None else 0 for value in values])
    return data


def remove_overlapping_charts(slide: Any, anchor: Any) -> None:
    """Remove template example charts whose bounds overlap a semantic anchor."""

    ax, ay, aw, ah = anchor.left, anchor.top, anchor.width, anchor.height
    for shape in list(slide.shapes):
        if not getattr(shape, "has_chart", False):
            continue
        sx, sy, sw, sh = shape.left, shape.top, shape.width, shape.height
        overlap = max(0, min(ax + aw, sx + sw) - max(ax, sx)) * max(
            0, min(ay + ah, sy + sh) - max(ay, sy)
        )
        if overlap > 0:
            slide.shapes._spTree.remove(shape._element)


def render_chart(slide: Any, anchor: Any, visualization: Mapping[str, Any]) -> Any:
    remove_overlapping_charts(slide, anchor)
    chart = slide.shapes.add_chart(
        _chart_type(str(visualization.get("chart_type"))),
        anchor.left,
        anchor.top,
        anchor.width,
        anchor.height,
        _chart_data(visualization),
    ).chart
    chart.has_title = False
    chart.has_legend = len(visualization.get("series", [])) > 1
    return chart


def render_table(slide: Any, target: Any, visualization: Mapping[str, Any]) -> Any:
    columns = visualization.get("columns")
    rows = visualization.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list) or not columns:
        raise VisualizationRenderError("table requires columns and rows")
    if any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
        raise VisualizationRenderError("each table row must match columns length")
    left, top, width, height = target.left, target.top, target.width, target.height
    old_element = target._element
    target_name = target.name
    slide.shapes._spTree.remove(old_element)
    table_shape = slide.shapes.add_table(len(rows) + 1, len(columns), left, top, width, height)
    table_shape.name = target_name
    table = table_shape.table
    for col, value in enumerate(columns):
        table.cell(0, col).text = str(value)
    for row_index, row in enumerate(rows, start=1):
        for col, value in enumerate(row):
            table.cell(row_index, col).text = "" if value is None else str(value)
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(11)
    return table_shape

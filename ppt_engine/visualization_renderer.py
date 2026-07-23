"""Small python-pptx helpers for chart, table, and image Visualization JSON."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from PIL import Image as PILImage
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
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


def _normalize_chart_axis_ids(chart: Any) -> None:
    """Keep generated axis IDs within the unsigned range required by Open XML."""

    for axis_id in chart._chartSpace.xpath(".//c:axId | .//c:crossAx"):
        raw = axis_id.get("val")
        if raw is None:
            continue
        value = int(raw)
        if value < 0 or value > 0x7FFFFFFF:
            axis_id.set("val", str(value & 0x7FFFFFFF))


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


def render_chart(
    slide: Any,
    anchor: Any,
    visualization: Mapping[str, Any],
    *,
    style: Mapping[str, Any] | None = None,
) -> Any:
    remove_overlapping_charts(slide, anchor)
    chart = slide.shapes.add_chart(
        _chart_type(str(visualization.get("chart_type"))),
        anchor.left,
        anchor.top,
        anchor.width,
        anchor.height,
        _chart_data(visualization),
    ).chart
    _normalize_chart_axis_ids(chart)
    chart.has_title = False
    chart.has_legend = len(visualization.get("series", [])) > 1
    style = style or {}
    font_size = Pt(float(style.get("font_size_pt", 11)))
    font_name = str(style.get("font_family", "")).strip() or None
    text_color = str(style.get("text_color", "")).strip()
    try:
        chart.category_axis.tick_labels.font.size = font_size
        chart.value_axis.tick_labels.font.size = font_size
        if font_name:
            chart.category_axis.tick_labels.font.name = font_name
            chart.value_axis.tick_labels.font.name = font_name
        if len(text_color) == 6:
            chart.category_axis.tick_labels.font.color.rgb = RGBColor.from_string(
                text_color
            )
            chart.value_axis.tick_labels.font.color.rgb = RGBColor.from_string(
                text_color
            )
    except ValueError:
        pass
    if chart.has_legend:
        chart.legend.font.size = Pt(float(style.get("legend_font_size_pt", 9)))
        if font_name:
            chart.legend.font.name = font_name
        if len(text_color) == 6:
            chart.legend.font.color.rgb = RGBColor.from_string(text_color)
    return chart


def render_table(
    slide: Any,
    target: Any,
    visualization: Mapping[str, Any],
    *,
    style: Mapping[str, Any] | None = None,
) -> Any:
    columns = visualization.get("columns")
    rows = visualization.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list) or not columns:
        raise VisualizationRenderError("table requires columns and rows")
    if any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
        raise VisualizationRenderError("each table row must match columns length")
    left, top, width, height = target.left, target.top, target.width, target.height
    old_element = getattr(target, "_element", None)
    target_name = getattr(target, "name", "compiled_table")
    if old_element is not None:
        slide.shapes._spTree.remove(old_element)
    table_shape = slide.shapes.add_table(len(rows) + 1, len(columns), left, top, width, height)
    table_shape.name = target_name
    table = table_shape.table
    for col, value in enumerate(columns):
        table.cell(0, col).text = str(value)
    for row_index, row in enumerate(rows, start=1):
        for col, value in enumerate(row):
            table.cell(row_index, col).text = "" if value is None else str(value)
    style = style or {}
    font_size = float(style.get("font_size_pt", 11))
    font_name = str(style.get("font_family", "")).strip() or None
    text_color = str(style.get("text_color", "")).strip()
    for row in table.rows:
        for cell in row.cells:
            cell.margin_left = Pt(3)
            cell.margin_right = Pt(3)
            cell.margin_top = Pt(2)
            cell.margin_bottom = Pt(2)
            for paragraph in cell.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(font_size)
                    if font_name:
                        run.font.name = font_name
                    if len(text_color) == 6:
                        run.font.color.rgb = RGBColor.from_string(text_color)
    return table_shape


def resolve_image_path(asset_path: object, *, asset_root: Path | None = None) -> Path:
    """Resolve a Visualization image within an explicit/current asset root."""

    if not isinstance(asset_path, str) or not asset_path.strip():
        raise VisualizationRenderError("image requires a non-empty asset_path")
    relative = Path(asset_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise VisualizationRenderError("image asset_path must be a safe relative path")
    root = (asset_root or Path.cwd()).resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise VisualizationRenderError("image asset_path escapes the asset root") from exc
    if not resolved.is_file():
        raise VisualizationRenderError(f"image asset does not exist: {asset_path}")
    return resolved


def render_image(
    slide: Any,
    anchor: Any,
    visualization: Mapping[str, Any],
    *,
    asset_root: Path | None = None,
) -> Any:
    """Insert a source image into a Layout Map anchor without distortion."""

    path = resolve_image_path(visualization.get("asset_path"), asset_root=asset_root)
    try:
        with PILImage.open(path) as image:
            pixel_width, pixel_height = image.size
            image.verify()
    except (OSError, ValueError) as exc:
        raise VisualizationRenderError(f"image asset is invalid: {path.name}") from exc
    if pixel_width <= 0 or pixel_height <= 0:
        raise VisualizationRenderError(f"image asset has invalid dimensions: {path.name}")

    scale = min(anchor.width / pixel_width, anchor.height / pixel_height)
    width = max(1, int(pixel_width * scale))
    height = max(1, int(pixel_height * scale))
    left = anchor.left + (anchor.width - width) // 2
    top = anchor.top + (anchor.height - height) // 2
    picture = slide.shapes.add_picture(str(path), left, top, width, height)
    source = visualization.get("source")
    identity = source.get("id") if isinstance(source, Mapping) else None
    picture.name = f"image_{identity or path.stem}"
    return picture

"""Template slide cloning and semantic field population."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, Sequence

from pptx.oxml.ns import qn

from .visualization_renderer import render_chart, render_table


class SlideBuildError(ValueError):
    """Raised when a template field cannot be populated."""


def duplicate_slide(prs: Any, source_slide: Any) -> Any:
    """Append a copy of a template slide, excluding native example charts."""

    target = prs.slides.add_slide(source_slide.slide_layout)
    sp_tree = target.shapes._spTree
    for shape in list(target.shapes):
        sp_tree.remove(shape._element)
    for shape in source_slide.shapes:
        if getattr(shape, "has_chart", False):
            continue
        sp_tree.append(deepcopy(shape.element))
    source_bg = source_slide.element.cSld.find(qn("p:bg"))
    if source_bg is not None:
        target_bg = target.element.cSld.find(qn("p:bg"))
        if target_bg is not None:
            target.element.cSld.remove(target_bg)
        target.element.cSld.insert(0, deepcopy(source_bg))
    return target


def remove_slide(prs: Any, index: int) -> None:
    slide_id = prs.slides._sldIdLst[index]
    prs.part.drop_rel(slide_id.rId)
    prs.slides._sldIdLst.remove(slide_id)


def _target_name(spec: Mapping[str, Any]) -> str | None:
    target = spec.get("target")
    return target.get("name") if isinstance(target, Mapping) else target if isinstance(target, str) else None


def find_shape(slide: Any, target: Mapping[str, Any] | str | None) -> Any | None:
    if target is None:
        return None
    if isinstance(target, Mapping):
        name = target.get("name")
        shape_id = target.get("shape_id")
    else:
        name = target
        shape_id = None
    if isinstance(name, str):
        for shape in slide.shapes:
            if shape.name == name:
                return shape
    if shape_id is not None:
        for shape in slide.shapes:
            if shape.shape_id == shape_id:
                return shape
    return None


def set_text(shape: Any | None, value: Any, *, required: bool = False) -> None:
    if shape is None:
        if required:
            raise SlideBuildError("required template text target is missing")
        return
    _replace_text_preserving_style(shape, [""] if value is None else str(value).splitlines() or [""])


def set_bullets(shape: Any | None, values: Iterable[Any], *, required: bool = False) -> None:
    if shape is None:
        if required:
            raise SlideBuildError("required template bullet target is missing")
        return
    items = [str(value) for value in values if value is not None and str(value).strip()]
    _replace_text_preserving_style(shape, items or [""])


def _replace_text_preserving_style(shape: Any, lines: Sequence[str]) -> None:
    """Replace text while retaining the template paragraph and run formatting."""

    text_frame = getattr(shape, "text_frame", None)
    if text_frame is None:
        raise SlideBuildError(f"template target {getattr(shape, 'name', '<unknown>')!r} has no text frame")
    tx_body = text_frame._txBody
    paragraphs = list(tx_body.findall(qn("a:p")))
    if not paragraphs:
        shape.text = "\n".join(lines)
        return

    template_paragraph = deepcopy(paragraphs[0])
    for paragraph in paragraphs:
        tx_body.remove(paragraph)

    for line in lines:
        paragraph = deepcopy(template_paragraph)
        text_nodes = list(paragraph.iter(qn("a:t")))
        if not text_nodes:
            raise SlideBuildError(
                f"template target {getattr(shape, 'name', '<unknown>')!r} has no reusable text run"
            )
        text_nodes[0].text = str(line)
        for text_node in text_nodes[1:]:
            text_node.text = ""
        tx_body.append(paragraph)


def _field(layout: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    fields = layout.get("fields", {})
    value = fields.get(name, {}) if isinstance(fields, Mapping) else {}
    return value if isinstance(value, Mapping) else {}


def _field_shape(slide: Any, layout: Mapping[str, Any], name: str) -> Any | None:
    return find_shape(slide, _field(layout, name).get("target"))


def _repeated_targets(layout: Mapping[str, Any], field_name: str) -> Sequence[Mapping[str, Any]]:
    targets = _field(layout, field_name).get("targets", [])
    return targets if isinstance(targets, list) else []


def _set_standard(slide: Any, layout: Mapping[str, Any], outline_slide: Mapping[str, Any], page_number: int) -> None:
    set_text(_field_shape(slide, layout, "title"), outline_slide.get("title"))
    set_text(_field_shape(slide, layout, "page_number"), page_number)
    refs = outline_slide.get("source_refs", [])
    set_text(_field_shape(slide, layout, "source_refs"), ", ".join(str(ref) for ref in refs))


def _set_repeated_text(slide: Any, targets: Sequence[Mapping[str, Any]], items: Sequence[Any], fields: Sequence[str]) -> None:
    for index, target_group in enumerate(targets):
        value = items[index] if index < len(items) else None
        for field in fields:
            set_text(find_shape(slide, target_group.get(field)), "")
        if isinstance(value, Mapping):
            for field in fields:
                target = target_group.get(field)
                set_text(find_shape(slide, target), value.get(field, ""))
        elif value is not None:
            text = str(value)
            if "number" in fields:
                set_text(find_shape(slide, target_group.get("number")), f"{index + 1:02d}")
            if fields == ("title", "body"):
                title, separator, body = text.partition("：")
                if not separator or len(title) > 12:
                    title, body = f"要点 {index + 1:02d}", text
                set_text(find_shape(slide, target_group.get("title")), title)
                set_text(find_shape(slide, target_group.get("body")), body)
            else:
                set_text(find_shape(slide, target_group.get(fields[-1])), text)


def _clear_repeated_text(
    slide: Any,
    targets: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> None:
    for target_group in targets:
        for field in fields:
            set_text(find_shape(slide, target_group.get(field)), "")


def _truncate(value: Any, limit: Any) -> str:
    text = "" if value is None else str(value)
    if not isinstance(limit, int) or limit < 2 or len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def populate_slide(
    slide: Any,
    layout: Mapping[str, Any],
    outline_slide: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    visualizations: Sequence[Mapping[str, Any]],
    page_number: int,
) -> None:
    """Populate the MVP fields for a resolved semantic layout."""

    layout_id = str(layout.get("layout_id", ""))
    _set_standard(slide, layout, outline_slide, page_number)
    title = outline_slide.get("title", "")
    key_message = outline_slide.get("key_message", "")
    bullets = outline_slide.get("bullet_points", [])
    if not isinstance(bullets, list):
        bullets = []

    if layout_id == "cover":
        set_text(_field_shape(slide, layout, "cover_title"), metadata.get("company_name", ""))
        set_text(_field_shape(slide, layout, "subtitle"), metadata.get("report_title", title))
        meta = "  |  ".join(str(metadata.get(key, "")) for key in ("stock_code", "report_date") if metadata.get(key))
        set_text(_field_shape(slide, layout, "cover_meta"), meta)
        set_text(_field_shape(slide, layout, "tag"), metadata.get("industry", ""))
        return

    if layout_id == "executive_summary":
        thesis = _field(layout, "thesis")
        set_text(
            _field_shape(slide, layout, "thesis"),
            _truncate(key_message, thesis.get("max_chars")),
        )
        _set_repeated_text(slide, _repeated_targets(layout, "logics"), bullets, ("title", "body"))
        _clear_repeated_text(
            slide,
            _repeated_targets(layout, "metrics"),
            ("value", "label", "note"),
        )
        return
    if layout_id == "company_overview":
        set_text(_field_shape(slide, layout, "company_name"), metadata.get("company_name"))
        set_text(_field_shape(slide, layout, "company_code"), metadata.get("stock_code"))
        set_text(_field_shape(slide, layout, "company_positioning"), key_message)
        _set_repeated_text(slide, _repeated_targets(layout, "segments"), bullets, ("title", "body"))
        _clear_repeated_text(
            slide,
            _repeated_targets(layout, "key_metric"),
            ("value", "label", "note"),
        )
    elif layout_id in {"industry_outlook", "competitive_landscape", "capability_map"}:
        field = {
            "industry_outlook": "drivers",
            "competitive_landscape": "moats",
            "capability_map": "stages",
        }[layout_id]
        _set_repeated_text(slide, _repeated_targets(layout, field), bullets, ("title", "body"))
        if layout_id == "capability_map":
            set_text(_field_shape(slide, layout, "catalyst_path"), key_message)
    elif layout_id == "risk_catalyst":
        _clear_repeated_text(
            slide,
            _repeated_targets(layout, "catalysts"),
            ("number", "text"),
        )
        _set_repeated_text(
            slide,
            _repeated_targets(layout, "risks"),
            bullets,
            ("number", "text"),
        )
    elif layout_id == "chart_text":
        set_text(_field_shape(slide, layout, "takeaway"), key_message)
        set_bullets(_field_shape(slide, layout, "bullets"), bullets)
        set_text(_field_shape(slide, layout, "conclusion"), key_message)
    elif layout_id == "valuation":
        headline = _field(layout, "headline")
        bullet_field = _field(layout, "bullets")
        conclusion = _field(layout, "conclusion")
        set_text(
            _field_shape(slide, layout, "headline"),
            _truncate(key_message, headline.get("max_chars")),
        )
        set_bullets(
            _field_shape(slide, layout, "bullets"),
            [
                _truncate(item, bullet_field.get("max_chars_per_item"))
                for item in bullets[: int(bullet_field.get("max_items", len(bullets)))]
            ],
        )
        set_text(
            _field_shape(slide, layout, "conclusion"),
            _truncate(key_message, conclusion.get("max_chars")),
        )
    elif layout_id == "earnings_forecast":
        set_text(_field_shape(slide, layout, "note"), key_message)
        set_bullets(_field_shape(slide, layout, "assumptions"), bullets)

    chart_visuals = [item for item in visualizations if "chart_type" in item]
    table_visuals = [item for item in visualizations if "columns" in item]
    chart_fields = [
        name for name in ("chart", "chart_left", "chart_right")
        if isinstance(_field(layout, name).get("anchor"), Mapping)
        and find_shape(slide, _field(layout, name).get("anchor")) is not None
    ]
    for chart_field in chart_fields:
        set_text(find_shape(slide, _field(layout, chart_field).get("title_target")), "")
    for index, visualization in enumerate(chart_visuals):
        if index >= len(chart_fields):
            raise SlideBuildError(f"layout {layout_id!r} has no chart slot for visualization {index + 1}")
        field = _field(layout, chart_fields[index])
        anchor = find_shape(slide, field.get("anchor"))
        if anchor is None:
            raise SlideBuildError(f"layout {layout_id!r} chart anchor is missing")
        render_chart(slide, anchor, visualization)
        set_text(find_shape(slide, field.get("title_target")), visualization.get("title", ""))
    for visualization in table_visuals:
        field = _field(layout, "table")
        target = find_shape(slide, field.get("target"))
        if target is None:
            raise SlideBuildError(f"layout {layout_id!r} table target is missing")
        render_table(slide, target, visualization)

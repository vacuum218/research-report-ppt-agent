"""Layout-driven text fitting and continuation-page planning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .abstract_layout import AbstractLayoutError, select_abstract_layout


_BREAK_MARKS = "。！？；，、 "
_DEFAULT_TITLE_MAX_CHARS = 72
_LEADING_LIST_MARKER_RE = re.compile(
    r"^\s*(?:(?:[➢►▶◆◇•●▪■□☞✓✔])|"
    r"(?:[（(]?[一二三四五六七八九十\d]+[）).、]))\s*"
)


@dataclass(frozen=True, slots=True)
class TextCapacity:
    title_max_chars: int
    key_message_max_chars: int
    body_max_items: int
    body_max_chars: int
    body_max_chars_per_item: int


@dataclass(frozen=True, slots=True)
class PhysicalSlide:
    slide: dict[str, Any]
    visualizations: tuple[Mapping[str, Any], ...]
    source_slide_id: str
    continuation_index: int


def _positive_int(value: object, fallback: int) -> int:
    return int(value) if isinstance(value, int) and value > 0 else fallback


def text_capacity(layout: Mapping[str, Any]) -> TextCapacity:
    """Read all text limits from one resolved Abstract Layout."""
    regions = {
        str(region.get("content_role")): region
        for region in layout.get("regions", [])
        if isinstance(region, Mapping)
    }
    title = regions.get("title", {}).get("capacity", {})
    key_message = regions.get("key_message", {}).get("capacity", {})
    body = regions.get("bullet_list", {}).get("capacity", {})
    title = title if isinstance(title, Mapping) else {}
    key_message = key_message if isinstance(key_message, Mapping) else {}
    body = body if isinstance(body, Mapping) else {}
    return TextCapacity(
        title_max_chars=_positive_int(
            title.get("max_chars"), _DEFAULT_TITLE_MAX_CHARS
        ),
        key_message_max_chars=_positive_int(
            key_message.get("max_chars"), 120
        ),
        body_max_items=_positive_int(body.get("max_items"), 8),
        body_max_chars=_positive_int(body.get("max_chars"), 520),
        body_max_chars_per_item=_positive_int(
            body.get("max_chars_per_item"), 120
        ),
    )


def split_text(value: object, max_chars: int) -> list[str]:
    """Split text at natural boundaries without omitting any non-space text."""
    remaining = str(value or "").strip()
    if not remaining:
        return []
    chunks: list[str] = []
    while len(remaining) > max_chars:
        window = remaining[:max_chars]
        minimum = max(1, max_chars // 2)
        boundary = max(window.rfind(mark) for mark in _BREAK_MARKS)
        cut = boundary + 1 if boundary >= minimum else max_chars
        chunk = remaining[:cut].strip()
        if not chunk:
            chunk = remaining[:max_chars]
            cut = max_chars
        chunks.append(chunk)
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _fit_title(value: object, max_chars: int) -> tuple[str, str | None]:
    title = str(value or "").strip()
    if len(title) <= max_chars:
        return title, None
    display = title[: max_chars - 1].rstrip("，；：、 ") + "…"
    return display, f"完整标题：{title}"


def _expand_bullets(
    values: Sequence[object],
    *,
    max_chars_per_item: int,
) -> list[str]:
    result: list[str] = []
    for value in values:
        cleaned = _LEADING_LIST_MARKER_RE.sub(
            "", str(value or ""), count=1
        ).strip()
        result.extend(split_text(cleaned, max_chars_per_item))
    return result


def _take_page(
    remaining: list[str],
    capacity: TextCapacity,
) -> list[str]:
    page: list[str] = []
    total = 0
    while remaining and len(page) < capacity.body_max_items:
        value = remaining[0]
        if len(value) > capacity.body_max_chars_per_item:
            break
        if page and total + len(value) > capacity.body_max_chars:
            break
        if not page and len(value) > capacity.body_max_chars:
            break
        page.append(remaining.pop(0))
        total += len(value)
    if not page and remaining:
        # The caller splits with the strictest item limit, so this is only a
        # defensive fallback for malformed/custom catalogs.
        hard_limit = min(
            capacity.body_max_chars,
            capacity.body_max_chars_per_item,
        )
        first, *rest = split_text(remaining.pop(0), hard_limit)
        page.append(first)
        remaining[:0] = rest
    return page


def _rebalance_sparse_pages(
    pages: list[list[str]],
    continuation_capacity: TextCapacity,
) -> None:
    minimum_chars = min(
        180,
        max(80, continuation_capacity.body_max_chars // 3),
    )
    for index in range(len(pages) - 1, 0, -1):
        current = pages[index]
        previous = pages[index - 1]
        while (
            sum(len(value) for value in current) < minimum_chars
            and len(previous) > 1
            and len(current) < continuation_capacity.body_max_items
        ):
            candidate = previous[-1]
            if (
                sum(len(value) for value in current) + len(candidate)
                > continuation_capacity.body_max_chars
            ):
                break
            current.insert(0, previous.pop())


def paginate_content_slide(
    slide: Mapping[str, Any],
    visualizations: Sequence[Mapping[str, Any]],
    abstract_catalog: Mapping[str, Any],
) -> list[PhysicalSlide]:
    """Convert one semantic slide into capacity-safe physical slides."""
    source_slide_id = str(slide.get("slide_id") or "")
    if slide.get("page_role") != "content":
        return [
            PhysicalSlide(
                slide=dict(slide),
                visualizations=tuple(visualizations),
                source_slide_id=source_slide_id,
                continuation_index=1,
            )
        ]

    title = str(slide.get("title") or "")
    key_message = (
        ""
        if slide.get("slide_type") == "figure_page"
        else str(slide.get("key_message") or "")
    )
    raw_bullets = list(slide.get("bullet_points", []))
    title_overflow = len(title) > _DEFAULT_TITLE_MAX_CHARS
    has_body = bool(key_message or raw_bullets or title_overflow)
    try:
        _, first_layout = select_abstract_layout(
            abstract_catalog,
            page_role="content",
            visualizations=visualizations,
            has_body=has_body,
        )
        _, continuation_layout = select_abstract_layout(
            abstract_catalog,
            page_role="content",
            visualizations=[],
            has_body=True,
        )
    except AbstractLayoutError:
        return [
            PhysicalSlide(
                slide=dict(slide),
                visualizations=tuple(visualizations),
                source_slide_id=source_slide_id,
                continuation_index=1,
            )
        ]

    first_capacity = text_capacity(first_layout)
    continuation_capacity = text_capacity(continuation_layout)
    strict_key_limit = min(
        first_capacity.key_message_max_chars,
        continuation_capacity.key_message_max_chars,
    )
    strict_item_limit = min(
        first_capacity.body_max_chars_per_item,
        continuation_capacity.body_max_chars_per_item,
    )
    display_title, full_title_bullet = _fit_title(
        title,
        min(
            first_capacity.title_max_chars,
            continuation_capacity.title_max_chars,
        ),
    )
    if full_title_bullet:
        raw_bullets.insert(0, full_title_bullet)

    key_chunks = split_text(key_message, strict_key_limit)
    key_message_display = key_chunks[0] if key_chunks else ""
    overflow_key_chunks = key_chunks[1:]
    remaining_bullets = overflow_key_chunks + _expand_bullets(
        raw_bullets,
        max_chars_per_item=strict_item_limit,
    )
    bullet_pages: list[list[str]] = []
    bullet_pages.append(_take_page(remaining_bullets, first_capacity))
    while remaining_bullets:
        bullet_pages.append(
            _take_page(remaining_bullets, continuation_capacity)
        )
    _rebalance_sparse_pages(bullet_pages, continuation_capacity)

    page_count = max(1, len(bullet_pages))
    pages: list[PhysicalSlide] = []
    for index in range(page_count):
        physical = dict(slide)
        physical["slide_id"] = (
            source_slide_id
            if index == 0
            else f"{source_slide_id}__cont_{index + 1:02d}"
        )
        physical["title"] = display_title
        physical["key_message"] = key_message_display if index == 0 else ""
        physical["bullet_points"] = (
            bullet_pages[index] if index < len(bullet_pages) else []
        )
        if page_count > 1:
            physical["_force_adaptive"] = True
        if index > 0:
            physical["visual_candidates"] = []
        pages.append(
            PhysicalSlide(
                slide=physical,
                visualizations=(
                    tuple(visualizations) if index == 0 else ()
                ),
                source_slide_id=source_slide_id,
                continuation_index=index + 1,
            )
        )
    return pages

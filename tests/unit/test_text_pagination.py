from __future__ import annotations

import json
from pathlib import Path

from ppt_engine.text_pagination import paginate_content_slide, split_text


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _catalog():
    return json.loads(
        (PROJECT_ROOT / "layouts/abstract_layout_catalog.json").read_text(
            encoding="utf-8"
        )
    )


def _slide(**overrides):
    value = {
        "slide_id": "slide_009",
        "page_role": "content",
        "slide_type": "business_model",
        "title": "卫星互联网业务布局",
        "key_message": "公司持续推进卫星互联网技术与产品布局。",
        "bullet_points": [],
        "visual_candidates": [{"type": "table"}],
    }
    value.update(overrides)
    return value


def test_split_text_preserves_content_and_respects_limit():
    source = "第一句说明业务背景。第二句包含更多信息；第三句给出结论。"

    chunks = split_text(source, 12)

    assert all(len(value) <= 12 for value in chunks)
    assert "".join(chunks) == source


def test_visual_slide_overflow_creates_text_only_continuation():
    bullets = [f"第{index}条：" + "业务说明" * 14 + "。" for index in range(1, 7)]
    pages = paginate_content_slide(
        _slide(bullet_points=bullets),
        [{"visual_type": "table", "visualization_id": "visual_001"}],
        _catalog(),
    )

    assert len(pages) >= 2
    assert pages[0].slide["slide_id"] == "slide_009"
    assert pages[0].visualizations
    assert pages[1].slide["slide_id"] == "slide_009__cont_02"
    assert pages[1].visualizations == ()
    assert all(page.slide["_force_adaptive"] is True for page in pages)
    rebuilt = "".join(
        value
        for page in pages
        for value in page.slide["bullet_points"]
    )
    assert rebuilt == "".join(bullets)


def test_long_key_message_is_preserved_across_pages():
    key_message = "核心结论：" + "公司持续推进研发与产业化。" * 15

    pages = paginate_content_slide(
        _slide(key_message=key_message, visual_candidates=[]),
        [],
        _catalog(),
    )

    rebuilt = "".join(
        [
            pages[0].slide["key_message"],
            *[
                value
                for page in pages
                for value in page.slide["bullet_points"]
            ],
        ]
    )
    assert rebuilt == key_message
    assert all(
        len(page.slide["key_message"]) <= 120
        for page in pages
    )


def test_sparse_last_page_is_rebalanced():
    bullets = ["说明内容" * 20 + "。" for _ in range(6)]
    pages = paginate_content_slide(
        _slide(bullet_points=bullets),
        [{"visual_type": "table", "visualization_id": "visual_001"}],
        _catalog(),
    )

    assert len(pages) >= 2
    assert len(pages[-1].slide["bullet_points"]) >= 2


def test_long_title_uses_display_title_and_preserves_full_title_in_body():
    title = "公司业务与行业发展趋势" * 10

    pages = paginate_content_slide(
        _slide(title=title, visual_candidates=[]),
        [],
        _catalog(),
    )

    assert all(len(page.slide["title"]) <= 72 for page in pages)
    body = "".join(
        value
        for page in pages
        for value in page.slide["bullet_points"]
    )
    assert f"完整标题：{title}" == body

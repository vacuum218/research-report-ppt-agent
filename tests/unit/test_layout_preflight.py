from __future__ import annotations

from ppt_engine.abstract_layout import load_abstract_layout_catalog
from ppt_engine.preflight import preflight_layouts
from visualization_generator.planning import VisualizationPlan


def _slide(**updates):
    slide = {
        "slide_id": "slide_001",
        "page_role": "content",
        "slide_type": "industry_analysis",
        "title": "Analysis",
        "key_message": "Evidence-backed conclusion",
        "bullet_points": ["Point"],
    }
    slide.update(updates)
    return slide


def _plan(identity: str, visual_type: str = "chart") -> VisualizationPlan:
    return VisualizationPlan(
        slide_id="slide_001",
        visualization_id=identity,
        visual_type=visual_type,
        purpose="Analysis",
        chart_intent="comparison" if visual_type == "chart" else None,
        data_requirement={},
        evidence_refs=(("block", "p001-b001"),),
        source_refs=("src",),
    )


def test_content_page_with_one_visual_selects_compatible_layout():
    report = preflight_layouts(
        {"slides": [_slide()]},
        [_plan("visual_001")],
        load_abstract_layout_catalog(),
    )

    assert report["status"] == "passed"
    assert report["pages"][0]["selected_abstract_layout"] in {
        "visual_left_text_right",
        "visual_right_text_left",
    }


def test_two_visuals_warn_but_remain_within_hard_budget():
    report = preflight_layouts(
        {"slides": [_slide()]},
        [_plan("visual_001"), _plan("visual_002", "table")],
        load_abstract_layout_catalog(),
    )

    assert report["status"] == "passed"
    assert report["warning_count"] == 1
    assert report["pages"][0]["selected_abstract_layout"] == "two_visuals"


def test_three_visuals_fail_before_rendering():
    report = preflight_layouts(
        {"slides": [_slide()]},
        [_plan("visual_001"), _plan("visual_002"), _plan("visual_003")],
        load_abstract_layout_catalog(),
    )

    assert report["status"] == "failed"
    assert report["pages"][0]["issues"][0]["code"] == "visual_budget_exceeded"


def test_non_content_page_rejects_visuals():
    report = preflight_layouts(
        {"slides": [_slide(page_role="title", slide_type="cover")]},
        [_plan("visual_001")],
        load_abstract_layout_catalog(),
    )

    assert report["status"] == "failed"
    assert report["pages"][0]["maximum_visual_count"] == 0


def test_closing_page_without_visual_has_adaptive_overflow_layout():
    report = preflight_layouts(
        {"slides": [_slide(page_role="closing", slide_type="closing")]},
        [],
        load_abstract_layout_catalog(),
    )

    assert report["status"] == "passed"
    assert report["pages"][0]["selected_abstract_layout"] == "non_content_text"

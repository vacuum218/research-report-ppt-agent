from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ppt_engine.layout_resolver import (
    LayoutMapError,
    LayoutResolver,
    resolve_outline,
    validate_layout_map,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def layout_map():
    return json.loads(
        (PROJECT_ROOT / "templates/template_layout_map.json").read_text(encoding="utf-8")
    )


def slide(page_role="content", slide_type="summary", visual_type=None, layout_hint=""):
    candidates = []
    if visual_type:
        candidates.append(
            {
                "candidate_id": f"visual_{visual_type}",
                "type": visual_type,
                "description": "test visual",
                "source_refs": [],
            }
        )
    return {
        "slide_id": "slide_test",
        "page_role": page_role,
        "slide_type": slide_type,
        "layout_hint": layout_hint,
        "visual_candidates": candidates,
    }


def test_canonical_layout_map_is_valid(layout_map):
    assert validate_layout_map(layout_map) == []


def test_title_role_has_highest_priority(layout_map):
    resolver = LayoutResolver(layout_map)
    chart = {"chart_type": "line", "series": []}

    assert resolver.resolve(slide("title", "company_overview"), [chart]) == "cover"


def test_semantic_visual_rules_use_slide_type_candidate_and_hint(layout_map):
    resolver = LayoutResolver(layout_map)

    assert resolver.resolve(
        slide(slide_type="industry_analysis", visual_type="chart", layout_hint="展示行业趋势图")
    ) == "industry_outlook"
    assert resolver.resolve(
        slide(slide_type="financial_forecast", visual_type="table", layout_hint="盈利预测表格")
    ) == "earnings_forecast"
    assert resolver.resolve(
        slide(slide_type="valuation_analysis", visual_type="table", layout_hint="可比公司PE表格")
    ) == "valuation_comparison"


def test_candidate_without_matching_hint_uses_slide_type_default(layout_map):
    resolver = LayoutResolver(layout_map)

    assert resolver.resolve(
        slide(slide_type="industry_analysis", visual_type="chart", layout_hint="纯文字行业结论")
    ) == "executive_summary"


def test_slide_type_mapping_is_used_without_visualization(layout_map):
    resolver = LayoutResolver(layout_map)

    assert resolver.resolve(slide(slide_type="investment_risk")) == "risk_catalyst"
    assert resolver.resolve(slide(slide_type="company_overview")) == "company_overview"
    assert resolver.resolve(slide(slide_type="figure_page")) == "image_only_layout"


def test_unknown_resolution_target_is_rejected(layout_map):
    broken = copy.deepcopy(layout_map)
    broken["layout_resolution"]["fallback_layout"] = "missing"

    with pytest.raises(LayoutMapError, match="UNKNOWN_RESOLUTION_TARGET"):
        LayoutResolver(broken)


def test_formal_outline_resolves_expected_slides_and_logs(layout_map, capsys):
    outline = json.loads(
        (PROJECT_ROOT / "examples/generated/002544_2025-10-28_slide_outline.json").read_text(
            encoding="utf-8"
        )
    )

    results = {item.slide_id: item for item in resolve_outline(outline, layout_map=layout_map)}

    assert results["slide_006"].layout_id == "industry_outlook"
    assert results["slide_007"].layout_id == "earnings_forecast"
    assert results["slide_009"].layout_id == "valuation_comparison"
    assert results["slide_010"].layout_id == "risk_catalyst"
    output = capsys.readouterr().out
    assert "slide_id=slide_006" in output
    assert "matched_rule=semantic_visual_rules.industry_analysis_chart" in output
    assert "final_layout_id=valuation_comparison" in output

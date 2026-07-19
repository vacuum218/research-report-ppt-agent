from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ppt_engine.layout_resolver import LayoutMapError, LayoutResolver, validate_layout_map


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def layout_map():
    return json.loads(
        (PROJECT_ROOT / "templates/template_layout_map.json").read_text(encoding="utf-8")
    )


def slide(page_role="content", slide_type="summary"):
    return {"page_role": page_role, "slide_type": slide_type}


def test_canonical_layout_map_is_valid(layout_map):
    assert validate_layout_map(layout_map) == []


def test_title_role_has_highest_priority(layout_map):
    resolver = LayoutResolver(layout_map)
    chart = {"chart_type": "line", "series": []}

    assert resolver.resolve(slide("title", "company_overview"), [chart]) == "cover"


def test_table_has_priority_over_chart(layout_map):
    resolver = LayoutResolver(layout_map)
    chart = {"chart_type": "line", "series": []}
    table = {"columns": ["A"], "rows": [[1]]}

    assert resolver.resolve(slide(), [chart, table]) == "earnings_forecast"


def test_slide_type_mapping_is_used_without_visualization(layout_map):
    resolver = LayoutResolver(layout_map)

    assert resolver.resolve(slide(slide_type="investment_risk")) == "risk_catalyst"
    assert resolver.resolve(slide(slide_type="company_overview")) == "company_overview"
    assert resolver.resolve(slide(slide_type="industry_analysis")) == "industry_outlook"
    assert resolver.resolve(slide(slide_type="business_model")) == "company_overview"
    assert resolver.resolve(slide(slide_type="core_competitiveness")) == "capability_map"
    assert resolver.resolve(slide(slide_type="financial_forecast")) == "executive_summary"
    assert resolver.resolve(slide(slide_type="valuation_analysis")) == "valuation"


def test_unknown_resolution_target_is_rejected(layout_map):
    broken = copy.deepcopy(layout_map)
    broken["layout_resolution"]["fallback_layout"] = "missing"

    with pytest.raises(LayoutMapError, match="UNKNOWN_RESOLUTION_TARGET"):
        LayoutResolver(broken)

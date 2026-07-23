from __future__ import annotations

import json
from pathlib import Path

import pytest
from pptx import Presentation

from ppt_engine.slide_builder import SlideBuildError, execute_compiled_operations


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_executor_sets_only_explicit_text_operations(tmp_path):
    prs = Presentation(PROJECT_ROOT / "templates/financial_report_template_v1.pptx")
    slide = prs.slides[2]
    title = next(shape for shape in slide.shapes if shape.name == "title")

    execute_compiled_operations(
        slide,
        [
            {
                "op": "set_text",
                "binding_id": "title",
                "target": {"name": "title"},
                "value": "确定性标题",
            }
        ],
        visualizations_by_id={},
        asset_root=tmp_path,
    )

    assert title.text == "确定性标题"


def test_executor_rejects_missing_explicit_target(tmp_path):
    prs = Presentation(PROJECT_ROOT / "templates/financial_report_template_v1.pptx")

    with pytest.raises(SlideBuildError, match="compiled target is missing"):
        execute_compiled_operations(
            prs.slides[0],
            [
                {
                    "op": "set_text",
                    "binding_id": "title",
                    "target": {"name": "missing"},
                    "value": "内容",
                }
            ],
            visualizations_by_id={},
            asset_root=tmp_path,
        )


def test_executor_rejects_unknown_operation(tmp_path):
    prs = Presentation(PROJECT_ROOT / "templates/financial_report_template_v1.pptx")

    with pytest.raises(SlideBuildError, match="unsupported compiled operation"):
        execute_compiled_operations(
            prs.slides[0],
            [{"op": "guess_layout"}],
            visualizations_by_id={},
            asset_root=tmp_path,
        )

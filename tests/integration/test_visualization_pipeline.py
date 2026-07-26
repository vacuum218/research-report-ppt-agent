from __future__ import annotations

import json
from pathlib import Path

from document_bundle.markdown import build_from_markdown
from document_intelligence import load_document_intelligence
from visualization_generator.generate_visualizations import generate_visualizations


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_legacy_charts_without_native_evidence_are_rejected(tmp_path):
    bundle = tmp_path / "document_bundle"
    build_from_markdown(PROJECT_ROOT / "data/reports/agent/002544_2025-10-28.md", bundle)
    document = load_document_intelligence(bundle, PROJECT_ROOT / "schemas/document_bundle.schema.json")
    outline = _load(PROJECT_ROOT / "examples/generated/002544_2025-10-28_slide_outline.json")
    artifacts, issues = generate_visualizations(outline, document)
    # Legacy tables may still resolve to complete native tables. Charts must
    # never fall back to numeric values published in an old outline.
    assert {artifact.visualization_id for artifact in artifacts} == {
        "visual_003",
        "visual_005",
    }
    assert all(artifact.metric_group is None for artifact in artifacts)
    assert issues
    assert all(
        "reject.missing_evidence_scope" in issue.reason for issue in issues
    )

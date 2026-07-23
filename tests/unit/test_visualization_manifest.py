from __future__ import annotations

import json
from pathlib import Path

import pytest

from visualization_generator.manifest import (
    VisualizationManifestError,
    canonical_sha256,
    load_visualization_manifest,
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def chart() -> dict:
    return {
        "chart_type": "line",
        "title": "趋势",
        "unit": "",
        "categories": ["2024", "2025"],
        "series": [{"name": "收入", "values": [1, 2]}],
        "source_refs": ["src_test"],
        "sources": [{"kind": "table", "id": "table-001"}],
    }


def manifest(asset_root: Path) -> dict:
    return {
        "schema_version": "3.0.0",
        "outline_sha256": "a" * 64,
        "document_source_sha256": "b" * 64,
        "asset_root": str(asset_root),
        "bindings": [
            {
                "slide_id": "slide_001",
                "visualization_id": "visual_001",
                "visual_type": "chart",
                "sources": [{"kind": "table", "id": "table-001"}],
                "visualization_file": "visual.json",
            }
        ],
    }


def test_loader_resolves_and_validates_artifacts(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_json(tmp_path / "visual.json", chart())
    write_json(tmp_path / "manifest.json", manifest(bundle))

    loaded = load_visualization_manifest(tmp_path / "manifest.json")

    assert loaded.asset_root == bundle.resolve()
    assert loaded.visualizations_by_id["visual_001"]["visual_type"] == "chart"
    assert loaded.bindings_by_slide["slide_001"][0]["data"]["title"] == "趋势"


def test_loader_rejects_declared_type_mismatch(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_json(tmp_path / "visual.json", chart())
    value = manifest(bundle)
    value["bindings"][0]["visual_type"] = "table"
    write_json(tmp_path / "manifest.json", value)

    with pytest.raises(VisualizationManifestError, match="declares"):
        load_visualization_manifest(tmp_path / "manifest.json")


def test_loader_rejects_duplicate_visualization_id(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_json(tmp_path / "visual.json", chart())
    value = manifest(bundle)
    value["bindings"].append(dict(value["bindings"][0]))
    write_json(tmp_path / "manifest.json", value)

    with pytest.raises(VisualizationManifestError, match="duplicate"):
        load_visualization_manifest(tmp_path / "manifest.json")


def test_canonical_hash_is_key_order_independent():
    assert canonical_sha256({"a": 1, "b": 2}) == canonical_sha256({"b": 2, "a": 1})

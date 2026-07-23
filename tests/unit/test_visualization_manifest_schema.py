from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def validator() -> Draft202012Validator:
    schema = json.loads(
        (PROJECT_ROOT / "schemas/visualization_manifest.schema.json").read_text(
            encoding="utf-8"
        )
    )
    return Draft202012Validator(schema)


@pytest.fixture()
def manifest() -> dict:
    return {
        "schema_version": "3.0.0",
        "outline_sha256": "a" * 64,
        "document_source_sha256": "b" * 64,
        "asset_root": "document_bundle",
        "bindings": [
            {
                "slide_id": "slide_001",
                "visualization_id": "visual_001",
                "visual_type": "chart",
                "sources": [{"kind": "table", "id": "table-001"}],
                "visualization_file": "slide_001__visual_001.json",
            }
        ],
    }


def assert_invalid(validator, value):
    assert list(validator.iter_errors(value))


def test_valid_manifest_passes(validator, manifest):
    validator.validate(manifest)


def test_manifest_rejects_parent_path(validator, manifest):
    value = copy.deepcopy(manifest)
    value["bindings"][0]["visualization_file"] = "../visual.json"
    assert_invalid(validator, value)


def test_manifest_requires_visual_type(validator, manifest):
    value = copy.deepcopy(manifest)
    del value["bindings"][0]["visual_type"]
    assert_invalid(validator, value)


def test_manifest_rejects_absolute_visualization_path(validator, manifest):
    value = copy.deepcopy(manifest)
    value["bindings"][0]["visualization_file"] = "C:/visual.json"
    assert_invalid(validator, value)

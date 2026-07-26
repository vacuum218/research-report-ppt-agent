from __future__ import annotations

import json
from pathlib import Path

import pytest

from visualization_generator.metric_artifact_io import (
    MetricArtifactError,
    load_metric_group_catalog,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_metric_group_loader_validates_schema_and_count(tmp_path):
    path = tmp_path / "metric_groups.json"
    path.write_text(
        json.dumps({"schema_version": "1.0.0", "group_count": 0, "groups": []}),
        encoding="utf-8",
    )

    loaded = load_metric_group_catalog(
        path, PROJECT_ROOT / "schemas/metric_group.schema.json"
    )

    assert loaded["groups"] == []


def test_metric_group_loader_rejects_inconsistent_count(tmp_path):
    path = tmp_path / "metric_groups.json"
    path.write_text(
        json.dumps({"schema_version": "1.0.0", "group_count": 1, "groups": []}),
        encoding="utf-8",
    )

    with pytest.raises(MetricArtifactError, match="group_count"):
        load_metric_group_catalog(
            path, PROJECT_ROOT / "schemas/metric_group.schema.json"
        )

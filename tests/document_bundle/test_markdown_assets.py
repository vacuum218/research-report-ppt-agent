from __future__ import annotations

from pathlib import Path

from document_bundle.markdown import build_from_markdown


def _write_markdown(path: Path, reference: str) -> None:
    path.write_text(f"# 图表\n\n![收入趋势]({reference})\n", encoding="utf-8")


def test_local_markdown_image_is_materialized_deterministically(tmp_path):
    source_directory = tmp_path / "source"
    image = source_directory / "images" / "chart.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"deterministic-png-fixture")
    report = source_directory / "report.md"
    _write_markdown(report, "images/chart.png")

    first, first_validation = build_from_markdown(
        report, tmp_path / "first_bundle"
    )
    second, second_validation = build_from_markdown(
        report, tmp_path / "second_bundle"
    )

    first_figure = first["figures"][0]
    second_figure = second["figures"][0]
    assert first_validation["status"] == "passed"
    assert second_validation["status"] == "passed"
    assert first_figure["asset_available"] is True
    assert first_figure["asset_path"] == second_figure["asset_path"]
    assert first_figure["asset_path"].startswith("assets/figures/fig-001-")
    assert (tmp_path / "first_bundle" / first_figure["asset_path"]).read_bytes() == image.read_bytes()


def test_remote_markdown_image_is_not_downloaded(tmp_path):
    report = tmp_path / "report.md"
    _write_markdown(report, "https://example.invalid/chart.png")

    document, validation = build_from_markdown(report, tmp_path / "bundle")

    assert validation["status"] == "needs_review"
    assert validation["issues"][0]["code"] == "remote_markdown_image_unavailable"
    assert document["figures"][0]["asset_available"] is False
    assert document["figures"][0]["asset_path"] is None
    assert not list((tmp_path / "bundle/assets/figures").iterdir())


def test_missing_markdown_image_is_reported_without_fabrication(tmp_path):
    report = tmp_path / "report.md"
    _write_markdown(report, "images/missing.png")

    document, validation = build_from_markdown(report, tmp_path / "bundle")

    assert validation["status"] == "needs_review"
    assert validation["issues"][0]["code"] == "missing_markdown_image"
    assert document["figures"][0]["asset_path"] is None


def test_markdown_image_parent_traversal_fails_validation(tmp_path):
    report = tmp_path / "source" / "report.md"
    report.parent.mkdir()
    _write_markdown(report, "../outside.png")

    _, validation = build_from_markdown(report, tmp_path / "bundle")

    assert validation["status"] == "failed"
    assert validation["issues"][0]["code"] == "unsafe_markdown_image_path"


def test_plain_text_declares_no_native_figures(tmp_path):
    report = tmp_path / "report.txt"
    report.write_text("第一章 公司概况\n\n公司经营稳定。\n", encoding="utf-8")

    document, validation = build_from_markdown(report, tmp_path / "bundle")

    assert document["document"]["source_format"] == "plain_text"
    assert document["figures"] == []
    assert validation["figures"] == {
        "detected": 0,
        "available": 0,
        "unavailable": 0,
    }

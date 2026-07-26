#!/usr/bin/env python3
"""Run the fixed five-report Phase 0 baseline with a real Outline API."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS = (
    "000333_2025-10-30.md",
    "001309_2025-10-28.md",
    "002444_2025-09-21.md",
    "002544_2025-10-28.md",
    "002821_2025-09-11.md",
)


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run five real Markdown reports through the real LLM pipeline"
    )
    parser.add_argument("--template-profile", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--outline-model")
    parser.add_argument("--outline-base-url")
    parser.add_argument("--outline-api-provider")
    parser.add_argument("--outline-timeout", type=int, default=600)
    parser.add_argument("--outline-max-attempts", type=int, default=2)
    parser.add_argument(
        "--candidate-mode",
        choices=["shadow", "active", "disabled"],
        default="shadow",
    )
    args = parser.parse_args()

    if not os.environ.get("DEEPSEEK_API_KEY"):
        parser.error(
            "DEEPSEEK_API_KEY is required; this baseline refuses mock or dry-run execution"
        )
    profile = args.template_profile.resolve()
    if not profile.is_file():
        parser.error(f"template profile does not exist: {profile}")

    args.output_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for report_name in REPORTS:
        report_id = report_name.split("_", 1)[0]
        report = PROJECT_ROOT / "data" / "reports" / "agent" / report_name
        output = args.output_root / report_id
        command = [
            sys.executable,
            str(PROJECT_ROOT / "main.py"),
            "run-pipeline",
            str(report),
            "--template-profile",
            str(profile),
            "--output-dir",
            str(output),
            "--outline-timeout",
            str(args.outline_timeout),
            "--outline-max-attempts",
            str(args.outline_max_attempts),
            "--candidate-mode",
            args.candidate_mode,
        ]
        for flag, value in (
            ("--outline-model", args.outline_model),
            ("--outline-base-url", args.outline_base_url),
            ("--outline-api-provider", args.outline_api_provider),
        ):
            if value:
                command.extend([flag, value])
        print(f"Running real API baseline: {report_id}", flush=True)
        completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
        if completed.returncode != 0:
            print(f"Baseline failed: {report_id}", file=sys.stderr)
            return completed.returncode
        manifest = _load_json(output / "run_manifest.json")
        outline = _load_json(output / "slide_outline.json")
        results.append(
            {
                "report_id": report_id,
                "status": manifest.get("status"),
                "slide_count": len(outline.get("slides", [])),
                "presentation_sha256": manifest.get("hashes", {}).get(
                    "presentation_sha256"
                ),
                "outline_sha256": manifest.get("hashes", {}).get("outline_sha256"),
            }
        )

    summary = {
        "schema_version": "1.0.0",
        "api_execution": "real",
        "candidate_mode": args.candidate_mode,
        "report_count": len(results),
        "results": results,
    }
    summary_path = args.output_root / "baseline_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Created baseline summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

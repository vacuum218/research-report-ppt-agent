#!/usr/bin/env python3
"""Unified command-line entry point for the implemented pipeline stages."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research Report PPT Agent")
    commands = parser.add_subparsers(dest="command", required=True)

    parse = commands.add_parser("parse-report", help="Parse Markdown or plain text")
    parse.add_argument("input", type=Path)
    parse.add_argument("-o", "--output", type=Path)
    parse.add_argument(
        "--source-format",
        choices=["auto", "markdown", "plain_text"],
        default="auto",
    )

    bundle = commands.add_parser(
        "document-bundle",
        help="Build the canonical DocumentBundle from PDF, raw artifacts, or Markdown",
    )
    bundle.add_argument("args", nargs=argparse.REMAINDER)

    outline = commands.add_parser(
        "generate-outline",
        help="Generate a schema-valid semantic slide outline",
    )
    outline.add_argument("args", nargs=argparse.REMAINDER)

    compact_summary = commands.add_parser(
        "compact-front-summary",
        help="Compact an existing pre-contents summary without calling an LLM",
    )
    compact_summary.add_argument("args", nargs=argparse.REMAINDER)

    inspect = commands.add_parser(
        "inspect-template",
        help="Inspect PPT template objects for layout-map construction",
    )
    inspect.add_argument("args", nargs=argparse.REMAINDER)

    layout_map = commands.add_parser(
        "build-layout-map",
        help="Build semantic template mappings from inspected objects",
    )
    layout_map.add_argument("args", nargs=argparse.REMAINDER)

    template_profile = commands.add_parser(
        "build-template-profile",
        help="Build the deterministic Template Profile from the legacy Layout Map",
    )
    template_profile.add_argument("args", nargs=argparse.REMAINDER)

    validate_outline = commands.add_parser(
        "validate-outline",
        help="Validate a semantic slide outline",
    )
    validate_outline.add_argument("args", nargs=argparse.REMAINDER)

    validate_visualization = commands.add_parser(
        "validate-visualization",
        help="Validate chart/table data",
    )
    validate_visualization.add_argument("args", nargs=argparse.REMAINDER)

    generate_visualizations = commands.add_parser(
        "generate-visualizations",
        help="Resolve outline visual intent into schema-valid visualization data",
    )
    generate_visualizations.add_argument("args", nargs=argparse.REMAINDER)

    validate_layout_map = commands.add_parser(
        "validate-layout-map",
        help="Validate runtime template layout mappings",
    )
    validate_layout_map.add_argument("args", nargs=argparse.REMAINDER)

    compile_layout = commands.add_parser(
        "compile-layout",
        help="Compile Outline, Visualization Manifest, and Template Profile",
    )
    compile_layout.add_argument("args", nargs=argparse.REMAINDER)

    render = commands.add_parser(
        "render-ppt",
        help="Render a semantic slide outline as a template-based PPTX",
    )
    render.add_argument("args", nargs=argparse.REMAINDER)

    render_compiled = commands.add_parser(
        "render-compiled-plan",
        help="Execute a Compiled Layout Plan without layout inference",
    )
    render_compiled.add_argument("args", nargs=argparse.REMAINDER)

    pipeline = commands.add_parser(
        "run-pipeline",
        help="Run DocumentBundle, Outline, Visualization, Compiler, and Renderer atomically",
    )
    pipeline.add_argument("input", type=Path)
    pipeline.add_argument("--template-profile", type=Path, required=True)
    pipeline.add_argument("--output-dir", type=Path, required=True)
    pipeline.add_argument(
        "--template",
        type=Path,
        default=Path(__file__).resolve().parent
        / "templates/financial_report_template_v1.pptx",
    )
    pipeline.add_argument(
        "--outline-input",
        type=Path,
        help="Use a prebuilt Outline for deterministic/offline runs",
    )
    pipeline.add_argument("--outline-model")
    pipeline.add_argument("--outline-base-url")
    pipeline.add_argument("--outline-api-provider")
    pipeline.add_argument("--outline-max-tokens", type=int)
    pipeline.add_argument("--outline-max-attempts", type=int)
    pipeline.add_argument("--outline-timeout", type=int)

    template = commands.add_parser(
        "parse-template",
        help="Parse generic PPT structure, styles, and theme",
    )
    template.add_argument("input", type=Path)
    template.add_argument("-o", "--output", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "parse-report":
        from document_parser.parse_report import main as parse_main

        forwarded = [str(args.input), "--format", args.source_format]
        if args.output:
            forwarded.extend(["--output", str(args.output)])
        return parse_main(forwarded)

    if args.command == "document-bundle":
        from document_bundle.cli import main as bundle_main

        return bundle_main(args.args)

    if args.command == "generate-outline":
        from outline_generator.generate_outline import main as outline_main

        return outline_main(args.args)

    if args.command == "compact-front-summary":
        from tools.compact_front_summary import main as compact_summary_main

        return compact_summary_main(args.args)

    if args.command == "inspect-template":
        from tools.inspect_template import main as inspect_main

        return inspect_main(args.args)

    if args.command == "build-layout-map":
        from tools.build_layout_map import main as layout_map_main

        return layout_map_main(args.args)

    if args.command == "build-template-profile":
        from tools.build_template_profile import main as template_profile_main

        return template_profile_main(args.args)

    if args.command == "validate-outline":
        from tools.validate_outline import main as validate_outline_main

        return validate_outline_main(args.args)

    if args.command == "validate-visualization":
        from tools.validate_visualization import main as validate_visualization_main

        return validate_visualization_main(args.args)

    if args.command == "generate-visualizations":
        from visualization_generator.generate_visualizations import main as visualization_main

        return visualization_main(args.args)

    if args.command == "validate-layout-map":
        from ppt_engine.layout_resolver import main as validate_layout_map_main

        return validate_layout_map_main(args.args)

    if args.command == "compile-layout":
        from ppt_engine.compiler import main as compile_layout_main

        return compile_layout_main(args.args)

    if args.command == "render-ppt":
        from visualization_generator.generate_visualizations import warn_for_render_args
        from ppt_engine.renderer import main as render_main

        warn_for_render_args(args.args)
        return render_main(args.args)

    if args.command == "render-compiled-plan":
        from ppt_engine.renderer import compiled_main

        return compiled_main(args.args)

    if args.command == "run-pipeline":
        import sys

        from pipeline_runner import PipelineRunError, run_pipeline

        try:
            output = run_pipeline(
                args.input,
                template_profile_path=args.template_profile,
                output_directory=args.output_dir,
                template_path=args.template,
                outline_input=args.outline_input,
                outline_model=args.outline_model,
                outline_base_url=args.outline_base_url,
                outline_api_provider=args.outline_api_provider,
                outline_max_tokens=args.outline_max_tokens,
                outline_max_attempts=args.outline_max_attempts,
                outline_timeout=args.outline_timeout,
            )
        except PipelineRunError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"Pipeline completed: {output}")
        print(f"Presentation: {output / 'presentation.pptx'}")
        print(f"Run manifest: {output / 'run_manifest.json'}")
        return 0

    if args.command == "parse-template":
        import json

        from ppt_template_parser import PPTTemplateParser, PPTThemeParser

        result = PPTTemplateParser(args.input).parse()
        result["theme"] = PPTThemeParser(args.input).parse()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Created template description: {args.output}")
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

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

    outline = commands.add_parser(
        "generate-outline",
        help="Generate a schema-valid semantic slide outline",
    )
    outline.add_argument("args", nargs=argparse.REMAINDER)

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

    render = commands.add_parser(
        "render-ppt",
        help="Render a semantic slide outline as a template-based PPTX",
    )
    render.add_argument("args", nargs=argparse.REMAINDER)

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

    if args.command == "generate-outline":
        from outline_generator.generate_outline import main as outline_main

        return outline_main(args.args)

    if args.command == "inspect-template":
        from tools.inspect_template import main as inspect_main

        return inspect_main(args.args)

    if args.command == "build-layout-map":
        from tools.build_layout_map import main as layout_map_main

        return layout_map_main(args.args)

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

    if args.command == "render-ppt":
        from visualization_generator.generate_visualizations import warn_for_render_args
        from ppt_engine.renderer import main as render_main

        warn_for_render_args(args.args)
        return render_main(args.args)

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

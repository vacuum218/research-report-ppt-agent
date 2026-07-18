"""Unified command-line interface for implemented pipeline stages."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .outline import generator
from .parsing.report import ParseError, parse_file
from .paths import PATHS
from .templates.inspection import inspect_presentation, print_summary
from .templates.layout_map import LayoutMapError, build_layout_map, load_inventory
from .templates.parser import PPTTemplateParser
from .templates.theme import PPTThemeParser
from .validation.outline import InputError, load_json, validate_outline
from .validation.visualization import validate_visualization


def _add_parse_report(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "parse-report",
        help="Parse Markdown or plain text",
        description="Parse a Markdown/plain-text financial report into parsed-document JSON",
    )
    parser.add_argument("input", type=Path, help="Input .md/.markdown/.txt file")
    parser.add_argument("-o", "--output", type=Path, help="Output JSON path")
    parser.add_argument(
        "--format",
        "--source-format",
        dest="source_format",
        choices=["auto", "markdown", "plain_text"],
        default="auto",
        help="Source format (default: infer from extension)",
    )
    parser.add_argument("--document-id", help="Override generated document ID")
    parser.add_argument(
        "--no-plain-headings",
        action="store_true",
        help="Disable numbered-heading detection for plain text",
    )
    parser.add_argument(
        "--drop-code-blocks",
        action="store_true",
        help="Skip fenced code blocks instead of preserving them",
    )
    parser.add_argument(
        "--drop-images",
        action="store_true",
        help="Treat standalone Markdown images as paragraph text",
    )
    parser.add_argument(
        "--no-merge-paragraph-lines",
        action="store_true",
        help="Keep each non-empty plain line as a separate paragraph",
    )
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation (default: 2)")
    parser.set_defaults(handler=_run_parse_report)


def _add_generate_outline(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "generate-outline",
        help="Generate a schema-valid semantic slide outline",
        description="Generate a PPT outline JSON with DeepSeek V4",
    )
    parser.add_argument("input", type=Path, help="Parsed-document JSON")
    parser.add_argument("-o", "--output", type=Path, help="Final outline JSON path")
    parser.add_argument("--schema", type=Path, default=PATHS.slide_outline_schema)
    parser.add_argument(
        "--parsed-schema",
        type=Path,
        default=PATHS.parsed_document_schema,
        help="Schema used to validate the parsed-document input",
    )
    parser.add_argument("--system-prompt", type=Path, default=PATHS.outline_system_prompt)
    parser.add_argument("--few-shot", type=Path, default=PATHS.outline_few_shot)
    parser.add_argument("--model", default=generator.DEFAULT_MODEL)
    parser.add_argument(
        "--base-url",
        default=os.getenv("DEEPSEEK_BASE_URL", generator.DEFAULT_BASE_URL),
    )
    parser.add_argument("--max-tokens", type=int, default=16000)
    parser.add_argument("--max-input-chars", type=int, default=180000)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=2,
        help="Maximum API attempts for retryable response/API failures (default: 2)",
    )
    parser.add_argument("--thinking", choices=["enabled", "disabled"], default="enabled")
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high", "max"],
        default="high",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build request JSON without calling DeepSeek",
    )
    parser.add_argument(
        "--request-output",
        type=Path,
        help="Optional path for the API request preview",
    )
    parser.add_argument("--skip-validation", action="store_true")
    parser.set_defaults(handler=_run_generate_outline)


def _add_inspect_template(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "inspect-template",
        help="Inspect PPT template objects for layout-map construction",
        description="Export PowerPoint template object names and structure",
    )
    parser.add_argument("pptx", type=Path, help="Input .pptx file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output JSON; defaults to <stem>_objects.json beside the PPTX",
    )
    parser.add_argument("--text-preview-length", type=int, default=120)
    parser.add_argument("--no-text-preview", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=_run_inspect_template)


def _add_layout_map(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "build-layout-map",
        help="Build semantic template mappings from inspected objects",
        description="Build template_layout_map.json from template object inventory",
    )
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("template_layout_map.json"),
    )
    parser.add_argument("--template-file")
    parser.add_argument("--no-strict", action="store_true")
    parser.add_argument("--indent", type=int, default=2)
    parser.set_defaults(handler=_run_build_layout_map)


def _add_validate_outline(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "validate-outline",
        help="Validate a semantic slide outline",
    )
    parser.add_argument("outline", type=Path)
    parser.add_argument("--schema", type=Path, default=PATHS.slide_outline_schema)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--warnings-as-errors", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=_run_validate_outline)


def _add_validate_visualization(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "validate-visualization",
        help="Validate chart/table data",
    )
    parser.add_argument("visualization", type=Path)
    parser.add_argument("--schema", type=Path, default=PATHS.visualization_schema)
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=_run_validate_visualization)


def _add_parse_template(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "parse-template",
        help="Parse generic PPT structure, styles, and theme",
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.set_defaults(handler=_run_parse_template)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research Report PPT Agent")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    _add_parse_report(commands)
    _add_generate_outline(commands)
    _add_inspect_template(commands)
    _add_layout_map(commands)
    _add_validate_outline(commands)
    _add_validate_visualization(commands)
    _add_parse_template(commands)
    return parser


def parse_command_args(
    command: str,
    argv: Optional[Sequence[str]] = None,
) -> argparse.Namespace:
    return build_parser().parse_args([command, *(list(argv) if argv is not None else [])])


def _run_parse_report(args: argparse.Namespace) -> int:
    output = args.output or args.input.with_name(f"{args.input.stem}_parsed.json")
    try:
        result = parse_file(
            args.input,
            source_format=args.source_format,
            document_id=args.document_id,
            plain_text_heading_detection=not args.no_plain_headings,
            preserve_code_blocks=not args.drop_code_blocks,
            preserve_images=not args.drop_images,
            merge_adjacent_paragraph_lines=not args.no_merge_paragraph_lines,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=args.indent) + "\n",
            encoding="utf-8",
        )
    except (ParseError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    stats = result["statistics"]
    print(f"Created: {output}")
    print(
        "Blocks: {block_count} (headings={heading_count}, paragraphs={paragraph_count}, "
        "lists={list_count}, tables={table_count}, images={image_count})".format(**stats)
    )
    print(f"Warnings: {len(result['warnings'])}")
    return 0


def _run_generate_outline(args: argparse.Namespace) -> int:
    output = args.output or Path("output/outlines") / f"{args.input.stem}_outline.json"
    try:
        if args.max_attempts < 1:
            raise generator.OutlineGenerationError("--max-attempts must be at least 1")
        parsed_document = generator.load_json(args.input, "Parsed document")
        parsed_schema = generator.load_json(args.parsed_schema, "Parsed document schema")
        generator.validate_json_instance(parsed_document, parsed_schema, label="Parsed document")
        schema = generator.load_json(args.schema, "Outline schema")
        few_shot = generator.load_json(args.few_shot, "Few-shot examples")
        system_prompt = generator.load_text(args.system_prompt, "System prompt")
        messages = generator.build_messages(
            parsed_document,
            schema,
            few_shot,
            system_prompt,
            max_input_chars=args.max_input_chars,
        )
        request_body = generator.build_request(
            messages,
            model=args.model,
            max_tokens=args.max_tokens,
            thinking=args.thinking,
            reasoning_effort=args.reasoning_effort,
        )

        if args.request_output:
            args.request_output.parent.mkdir(parents=True, exist_ok=True)
            args.request_output.write_text(
                json.dumps(request_body, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Created request preview: {args.request_output}")

        if args.dry_run:
            print(f"Dry run OK: model={args.model}, messages={len(messages)}")
            return 0

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise generator.OutlineGenerationError("DEEPSEEK_API_KEY is not set")
        outline, issues, attempts_used = generator.generate_with_retries(
            messages,
            schema,
            api_key=api_key,
            base_url=args.base_url,
            timeout=args.timeout,
            model=args.model,
            max_tokens=args.max_tokens,
            thinking=args.thinking,
            reasoning_effort=args.reasoning_effort,
            max_attempts=args.max_attempts,
            validate_output=not args.skip_validation,
        )

        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix="outline_",
            dir=output.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(outline, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        try:
            temporary_path.replace(output)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

        errors = [issue for issue in issues if issue.severity == "error"]
        warnings = [issue for issue in issues if issue.severity == "warning"]
        if not args.skip_validation:
            print(f"VALID: {len(errors)} error(s), {len(warnings)} warning(s)")
        print(f"Created outline: {output}")
        print(f"Model: {args.model}")
        print(f"Attempts: {attempts_used}/{args.max_attempts}")
        print(f"Slides: {len(outline.get('slides', []))}")
        return 0
    except (generator.OutlineGenerationError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _run_validate_outline(args: argparse.Namespace) -> int:
    try:
        outline = load_json(args.outline, "outline")
        schema = load_json(args.schema, "schema")
        issues = validate_outline(outline, schema)
    except InputError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2

    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    valid = not errors and not (args.warnings_as_errors and warnings)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(
                {
                    "valid": valid,
                    "outline_file": str(args.outline),
                    "schema_file": str(args.schema),
                    "error_count": len(errors),
                    "warning_count": len(warnings),
                    "issues": [asdict(issue) for issue in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    if not args.quiet:
        for issue in issues:
            print(f"[{issue.severity.upper()}] {issue.code} {issue.path}: {issue.message}")
    print(f"{'VALID' if valid else 'INVALID'}: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 0 if valid else 1


def _run_validate_visualization(args: argparse.Namespace) -> int:
    try:
        visualization = load_json(args.visualization, "visualization")
        schema = load_json(args.schema, "schema")
        issues = validate_visualization(visualization, schema)
    except InputError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    if not args.quiet:
        for issue in issues:
            print(f"[{issue.severity.upper()}] {issue.code} {issue.path}: {issue.message}")
    print(f"{'VALID' if not issues else 'INVALID'}: {len(issues)} error(s)")
    return 0 if not issues else 1


def _run_inspect_template(args: argparse.Namespace) -> int:
    pptx_path = args.pptx.expanduser().resolve()
    if not pptx_path.exists():
        print(f"错误：文件不存在：{pptx_path}", file=sys.stderr)
        return 2
    if pptx_path.suffix.lower() != ".pptx":
        print("错误：输入文件必须是 .pptx", file=sys.stderr)
        return 2
    if args.text_preview_length < 0:
        print("错误：--text-preview-length 不能小于0", file=sys.stderr)
        return 2
    output_path = (
        args.output.expanduser().resolve()
        if args.output
        else pptx_path.with_name(f"{pptx_path.stem}_objects.json")
    )
    try:
        data = inspect_presentation(
            pptx_path,
            text_preview_length=args.text_preview_length,
            include_text=not args.no_text_preview,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"错误：无法读取PPTX：{exc}", file=sys.stderr)
        return 1
    if not args.quiet:
        print_summary(data)
    print(f"\nJSON已保存：{output_path}")
    return 0


def _run_build_layout_map(args: argparse.Namespace) -> int:
    try:
        inventory = load_inventory(args.input)
        layout_map, warnings, errors = build_layout_map(
            inventory,
            strict=not args.no_strict,
            template_file=args.template_file,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(layout_map, ensure_ascii=False, indent=args.indent) + "\n",
            encoding="utf-8",
        )
    except (LayoutMapError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Created: {args.output}")
    print(f"Layouts: {len(layout_map['layouts'])}")
    print(f"Warnings: {len(warnings)}")
    print(f"Errors: {len(errors)}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    return 0


def _run_parse_template(args: argparse.Namespace) -> int:
    try:
        result = PPTTemplateParser(args.input).parse()
        result["theme"] = PPTThemeParser(args.input).parse()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Created template description: {args.output}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)

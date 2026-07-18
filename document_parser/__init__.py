"""Compatibility package for the legacy ``document_parser`` import."""

from .parse_report import ParseError, ReportParser, parse_file

__all__ = ["ParseError", "ReportParser", "parse_file"]

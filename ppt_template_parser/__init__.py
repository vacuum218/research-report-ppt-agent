"""Compatibility package for the legacy ``ppt_template_parser`` import."""

from .ppt_template_parser import PPTTemplateParser
from .theme_parser import PPTThemeParser

__all__ = ["PPTTemplateParser", "PPTThemeParser"]

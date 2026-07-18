"""PowerPoint template parsing, inspection, and semantic layout mapping."""

from .inspection import inspect_presentation
from .layout_map import LayoutMapError, build_layout_map
from .parser import PPTTemplateParser
from .theme import PPTThemeParser

__all__ = [
    "LayoutMapError",
    "PPTTemplateParser",
    "PPTThemeParser",
    "build_layout_map",
    "inspect_presentation",
]

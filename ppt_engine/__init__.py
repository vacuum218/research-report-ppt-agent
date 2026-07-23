"""Template-backed PowerPoint generation for the frozen project contracts."""

from .layout_resolver import (
    LayoutMapError,
    LayoutResolutionError,
    LayoutResolver,
    resolve_layout,
    resolve_outline,
)
from .renderer import RenderError, render_ppt, render_presentation
from .compiler import LayoutCompileError, compile_layout_plan

__all__ = [
    "LayoutResolutionError",
    "LayoutMapError",
    "LayoutResolver",
    "RenderError",
    "render_ppt",
    "render_presentation",
    "resolve_layout",
    "resolve_outline",
    "LayoutCompileError",
    "compile_layout_plan",
]

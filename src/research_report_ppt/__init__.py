"""Research-report to PowerPoint pipeline primitives."""

from .outline.generator import OutlineGenerationError
from .parsing.report import ParseError, ReportParser, parse_file
from .validation.outline import Issue, validate_outline
from .validation.visualization import validate_visualization

__version__ = "0.2.0"

__all__ = [
    "Issue",
    "OutlineGenerationError",
    "ParseError",
    "ReportParser",
    "__version__",
    "parse_file",
    "validate_outline",
    "validate_visualization",
]

"""LLM-backed semantic slide-outline generation."""

from .generator import (
    DeepSeekAPIError,
    OutlineGenerationError,
    OutlineResponseError,
    OutlineValidationError,
    generate_with_retries,
)

__all__ = [
    "DeepSeekAPIError",
    "OutlineGenerationError",
    "OutlineResponseError",
    "OutlineValidationError",
    "generate_with_retries",
]

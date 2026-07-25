"""Single-command orchestration for the research-report PPT pipeline."""

from .run_pipeline import PipelineRunError, run_pipeline

__all__ = ["PipelineRunError", "run_pipeline"]

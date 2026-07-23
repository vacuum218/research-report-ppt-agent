"""Generate schema-valid Visualization JSON from outline intent and document evidence."""

from .generate_visualizations import (
    GenerationIssue,
    VisualizationArtifact,
    VisualizationCoverageWarning,
    bindings_from_artifacts,
    generate_visualizations,
    preflight_visualizations,
    warn_for_render_args,
)
from .manifest import (
    LoadedVisualizationManifest,
    VisualizationManifestError,
    load_visualization_manifest,
)

__all__ = [
    "GenerationIssue",
    "VisualizationArtifact",
    "VisualizationCoverageWarning",
    "bindings_from_artifacts",
    "generate_visualizations",
    "preflight_visualizations",
    "warn_for_render_args",
    "LoadedVisualizationManifest",
    "VisualizationManifestError",
    "load_visualization_manifest",
]

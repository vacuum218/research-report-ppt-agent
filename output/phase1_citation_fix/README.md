# Phase 1 acceptance output

This directory contains the final pipeline output for five real research reports after the minimal citation-marker and chart-admission fixes.

- The Phase 0 baseline `slide_outline.json` files were reused without modification, so slide planning and layout selection were not regenerated.
- Internal markers in both `[^cite_id:...]` and `[^citeid:...]` forms are removed from rendered table cells.
- Bar and column charts require 3–8 comparable categories and cannot substitute an unrelated same-section table when their cited evidence has no numeric facts.
- The invalid two-category chart on report `002444`, slide 22 is skipped; the verified valuation table and explanatory text remain.
- Citation metadata remains available in source and audit artifacts for traceability; only display-facing table content is cleaned.
- All 91 generated slides were rendered for visual inspection, and all 5 presentations passed slide-boundary checks.

Final presentations:

- `000333/presentation.pptx`
- `001309/presentation.pptx`
- `002444/presentation.pptx`
- `002544/presentation.pptx`
- `002821/presentation.pptx`

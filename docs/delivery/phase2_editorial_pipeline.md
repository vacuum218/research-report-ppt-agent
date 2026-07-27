# Phase 2 editorial pipeline

Phase 2 separates source understanding from presentation editing:

```text
DocumentBundle -> ReportMap -> DeckStoryboard -> Slide Outline adapter -> PPTX
```

`report_map.json` preserves source section titles, evidence-backed atomic claims,
native figure inventory, and explicit exclusions such as disclaimers, analyst
profiles, certificates, contact details, rating definitions, and legal notices.

`deck_storyboard.json` selects one claim and one unique purpose for every content
page. `section_title` remains source provenance while `headline` is the concise,
audience-facing title. The adapter maps `headline` to legacy `title`, `claim` to
`key_message`, and supporting points to `bullet_points`, so the existing renderer
does not need a second content model.

Native figures may now be `image` visual candidates on ordinary content pages.
The existing adaptive layout path places the image beside explanatory text; old
`figure_page` outlines remain readable for backward compatibility.

Offline `--outline-input` runs derive compatibility ReportMap and Storyboard
artifacts without an API call. Phase 2 quality acceptance requires fresh API
generation because the new artifacts contain editorial decisions that do not
exist in Phase 0 outlines.

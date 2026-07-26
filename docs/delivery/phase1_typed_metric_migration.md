# Phase 1 typed metric migration

Phase 1 changes the chart publication contract. A chart is now publishable only
after every referenced `NumericFact` has been assembled into one verified
`MetricGroup`. Tables remain traceable to native evidence but do not require a
metric group.

## New persisted fields

`numeric_fact_ledger.json` now records, for every fact:

- entity identity and type;
- canonical metric key and label;
- measure kind (`amount`, `growth_rate`, `share`, and related kinds);
- unit family, scale, and currency;
- scope kind and label;
- scenario (`actual`, `estimate`, `guidance`, or `target`).

Successful chart groups are written to `metric_groups.json`. The catalog records
the compatible fact IDs, chart intent, common semantic dimensions, scenarios,
and the historical/forecast boundary when present.

Both artifacts are validated against
`schemas/numeric_fact_ledger.schema.json` and
`schemas/metric_group.schema.json` before the pipeline publishes its output.
Consumers can use `visualization_generator.metric_artifact_io` to load and
validate persisted files, including their declared count fields.

## Compatibility policy

Old outlines remain valid input only when their visual candidates contain native
`evidence_refs`. A legacy chart candidate that contains only a prose description
or `source_refs` is rejected with `reject.missing_evidence_scope`; the pipeline no
longer reconstructs an unverified chart from published outline values.

Facts whose metric cannot be determined are retained in the ledger as
`metric_key: "unknown"` for auditability. They cannot enter a chart unless the
candidate purpose provides an unambiguous deterministic classification. A group
is rejected when it mixes metrics, measure kinds, unit families or scales,
currencies, entities, scopes, scenarios, or incompatible historical/forecast
ordering.

## Offline acceptance

Phase 1 acceptance reuses the five real-API outlines created in Phase 0:

```text
output/phase0_baseline/<报告ID>/slide_outline.json
```

Run `main.py run-pipeline` with each report and the corresponding
`--outline-input`; do not call the LLM API again. Compare the resulting
`metric_groups.json`, `numeric_audit.json`, `visualization_warnings.json`, and
PPTX against the Phase 0 baseline. The fixed report IDs are `000333`, `001309`,
`002444`, `002544`, and `002821`.

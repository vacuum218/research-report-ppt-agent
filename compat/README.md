# Compatibility boundary

`compat/` contains deprecated adapters that are excluded from every production pipeline.

Current contents:

- `structured_content/`: deterministic DocumentBundle → Parsed Document adapter retained only for compatibility regression tests.

Rules:

- production packages must not import `compat`;
- no new feature may depend on these adapters;
- compatibility code may be deleted only when its dedicated regression tests and external consumers are retired;
- canonical runtime inputs remain DocumentBundle and Document Intelligence.

`document_parser/` is not inside this directory because its `parse_file` implementation is still used by the
Markdown/plain-text DocumentBundle builder. Only its direct `parse-report` Parsed JSON CLI is deprecated.

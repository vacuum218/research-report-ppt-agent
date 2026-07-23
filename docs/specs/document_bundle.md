# DocumentBundle v0.1

## 目的

DocumentBundle 是 PDF、Markdown 和纯文本研报的统一上游数据层。它保存原文块、章节、
阅读顺序、图表资产和可审计的源位置，不包含 LLM 生成内容。

## 冻结顶层字段

| 字段 | 内容 |
|---|---|
| `document` | 文档 ID、标题、来源文件、格式、SHA-256、页数 |
| `pages` | 页面及其 block 引用 |
| `blocks` | 原始可读内容块 |
| `sections` | 只引用原始 heading block 的章节树 |
| `tables` | 表格结构、截图 fragment、状态和 issue |
| `figures` | 图片/图表资产及源位置 |
| `reading_order` | 覆盖所有 block 一次的派生阅读顺序 |

不得删除、重命名或创建替代性的顶层字段。

## PDF profile

- `source_format` 为 `pdf`。
- block 使用 `page + bbox` 定位回 PDF。
- bbox 使用实际 PDF 页面坐标。
- raw 目录严格保留四个 MinerU 原始文件。
- 表格和图片资产从原 PDF 确定性裁切。

## Markdown/Text profile

- `source_format` 为 `markdown` 或 `plain_text`。
- `location_model` 为 `line_range`。
- block 保存 `line_start/line_end`，`bbox` 为 `null`。
- 不伪造 PDF 坐标。
- raw 目录保留原始 `document.md`。

## 表格策略

- `complete`：结构来自 parser 的 HTML/grid，可进入 Visualization。
- `image_only`：保留高清 fragment，但不自动补写缺失单元格。
- LLM 不得作为权威表格解析器。

## 验证

结构由 `schemas/document_bundle.schema.json` 校验。PDF profile 还通过
`document_bundle.validation` 验证 page/bbox、reading order、章节引用、资产路径和 raw 文件。

`validation.json` 的状态为 `passed`、`needs_review` 或 `failed`。

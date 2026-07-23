# 接口规范

## 正式依赖

```text
outline_generator
        ↓
document_intelligence
        ↓
DocumentBundle document.json + assets/
```

Outline 正式路径禁止依赖 `structured_content`、`parsed_document.schema.json` 和
`document_parser`。

## Document Intelligence

Document Intelligence 返回只读运行时索引和 chunk，不写出新的长期 JSON。它不得包含
summary、key points、importance 或 slide plan。

每个 chunk 保留原始 section ID/path、block ID、reading order、源位置、关联 table/figure
及允许引用的 evidence ID。

## Context Compression

Context Compression memory 只允许存在于 Outline Generator 当前进程内。项目不提供
memory output、memory Schema 或 memory cache。`--request-output` 只允许在 dry-run 中输出
空 memory 模板和请求预览，不写真实 LLM memory。

## Slide Outline

`section_ref` 和 `evidence_refs` 是 backward-compatible optional 字段。新 Outline Generator
对 section/content slide 执行强制的 DocumentBundle 后置校验；旧 Outline 仍可由 Renderer 读取。

## Visualization 和 Renderer

正式依赖为：

```text
visualization_generator
        ↓
document_intelligence
        ↓
DocumentBundle document.json + assets/
```

Planning 输出是运行时对象，不是新的长期数据标准。它只能描述 type、purpose、chart intent、
data requirement 和 evidence refs，禁止携带 values、table cells 或 asset path。

Generator 输出 chart/table/image Visualization JSON，并为每个对象写入原生 `sources`。
`compat/structured_content/` 仅作为 deprecated 兼容模块保留，正式 Visualization 无任何 import 依赖。

Renderer 接口保持为 Outline + Visualization + Layout Map，不读取任何上游文档格式。冻结版本
仅支持 chart/table；image 的物理渲染需要未来单独扩展 Renderer 能力。

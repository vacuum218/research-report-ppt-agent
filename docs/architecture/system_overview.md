# 系统架构

## 总体流程

```text
PDF / Markdown / Text
          ↓
DocumentBundle
          ↓
Document Intelligence Layer
          ↓
LLM Context Compression（运行时 memory）
          ↓
LLM Slide Planning
          ↓
Slide Outline + Document Intelligence
          ↓
Visualization Planning（无数值、无路径）
          ↓
Deterministic Visualization Generator
          ↓
Layout Resolver + PPT Renderer
          ↓
PPTX
```

DocumentBundle 是唯一上游事实来源。Outline Generator 不读取 Parsed Document，
Context Compression 的输出不写盘、不注册 Schema，也不作为模块间长期接口。

## Document Intelligence Layer

`document_intelligence/` 是纯确定性层，只负责：

- bundle 读取与 Schema 校验；
- section hierarchy 解析；
- block、page、table、figure 索引；
- table/figure 与题注、脚注、section 的关系；
- page/bbox 或 line range evidence 定位；
- 按 section 和 reading order 生成 chunk。

明确禁止 summary、key points、重要性判断、slide 内容规划、LLM 调用和 section 重排。

## LLM Understanding Layer

Context Compression 输入 Document Intelligence chunk，输出仅存在于当前进程的临时 memory。
Slide Planning 使用有序 section catalog 和 runtime memory 生成最终 Outline，并保留 source/evidence refs。

## Visualization Planning 与 Generator

`visualization_generator/planning.py` 消费 Slide Outline 中的 LLM 语义建议，并校验
`block/table/figure` evidence 是否真实存在。Planning 不生成数值、表格单元格或 asset path。

`visualization_generator/generator.py` 是纯确定性层，只从 Document Intelligence 索引读取：

- complete table → PPT 原生 table 或 chart；
- block 中的明确数值序列 → chart；
- DocumentBundle figure → image Visualization；
- image-only table → image Visualization，不补全缺失结构。

每个生成物使用 `sources` 保留原生 block/table/figure ID。正式路径不再经过
`compat.structured_content`、Parsed Document 或 `document_parser`。

## PPT Engine 边界

PPT Engine 继续只消费 Outline、Visualization、Layout Map 和 PPT 模板。当前冻结的 Renderer
只渲染 chart/table；image Visualization 已可生成和追溯，但预检会报告
`image_not_supported_by_frozen_renderer`，不会静默声称图片已进入 PPT。

迁移期并行增加新的确定性链路：

```text
Template Profile + Slide Outline + Visualization Manifest
        → Layout Compiler
        → Compiled Layout Plan
        → Compiled-plan Renderer
        → PPTX
```

旧 Outline + Layout Map Renderer 在新链路完成验收前继续保留。

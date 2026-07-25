# Visualization JSON Schema

## 定位

Visualization Pipeline 分为两个边界明确的阶段：

```text
Slide Outline + Document Intelligence
  → Candidate Locator（slide-scoped，无 values）
  → Visualization Planning（合并 Outline 建议）
  → Numeric Fact Ledger（Decimal、单位、期间、span/cell）
  → Structure Mapper（只引用 fact_id）
  → Deterministic Verifier / Assembler
  → Visualization JSON
  → Renderer
```

正式 Schema 位于 `schemas/visualization.schema.json`。一个文件表示一个 chart、table 或 image。
`source_refs` 保留研报级来源，`sources` 保留 DocumentBundle 原生 block/table/figure 证据。

## Chart

```json
{
  "chart_type": "line",
  "title": "卫星互联网市场规模",
  "unit": "亿元",
  "categories": ["2021", "2025"],
  "series": [{"name": "市场规模", "values": [291.62, 376]}],
  "source_refs": ["src_002544_2025-07-07"],
  "sources": [{"kind": "block", "id": "p004-b011"}]
}
```

values 必须由确定性代码从来源 block 或 complete table 提取。时间序列强制使用 line；明显的
分类比较会覆盖不合理的 LLM chart 建议。缺失值使用 `null`，不得用 0 伪装。

Renderer 对 `line`、`column`、`bar`、`pie` 使用 PowerPoint 原生 Chart。默认样式包含固定
系列色、底部图例、浅色网格线和模板字体；bar 默认显示数值标签，pie 显示百分比标签。line 的
`forecast_start_index` 及之后数据点使用空心标记；line 遇到 `null` 时不生成该点或数值，但会
跨接相邻已知数据点，避免 PowerPoint 默认空距造成断线。pie 只允许一个系列，且不允许缺失值、
负值或非正合计。当前原生 Renderer 不支持 secondary axis；遇到 secondary series 会明确失败。

有 evidence 的 Week 3 路径不允许 Mapper 直接携带数值。Mapper 只能返回 fact_id；Verifier
从 Numeric Fact Ledger 取回 Decimal 规范值，检查候选作用域、单位、序列长度、图表类型和
`sources` 后组装本 Schema。未知 fact、跨 evidence 引用或单位冲突会拒绝该 Visualization。

## Table

complete DocumentBundle table 可以转换为结构化表格：

```json
{
  "title": "盈利预测",
  "columns": ["项目", "2025E", "2026E"],
  "rows": [["收入", 100, 120]],
  "source_refs": ["src_report"],
  "sources": [{"kind": "table", "id": "table-003"}]
}
```

`image_only` table 不允许补齐结构，只能使用其 DocumentBundle crop 生成 image。
complete table 的每个数值单元格必须能通过 table ID、零基 row/column 回查到 Numeric Fact；
缺少任一 fact 时不生成部分可信的结构化表格。

Renderer 使用 PowerPoint 原生 Table，并采用确定性样式：深色表头、白色粗体表头文字、浅色
隔行底纹、细边框、水平及垂直居中。列宽根据表头和单元格
显示宽度分配，首个文本列获得额外权重，所有列宽之和严格等于 Layout slot 宽度。`null` 显示为
空单元格，不替换为 0。Renderer 全局上限为 18 个数据行 × 8 列；Compiler 还会应用各 Layout
slot 更严格的 `max_rows/max_columns`。任一上限超出都会明确失败，不静默截断或丢弃数据。

端到端验收使用独立 Numeric Audit sidecar 保存 `fact_id` 到最终 Visualization JSON 路径的
绑定，并以 Decimal 重新核对每个输出值。该绑定只存在于生成和审计阶段，不进入正式
Visualization Schema；缺少绑定、未知 fact、路径不存在或数值不一致均视为失败。

## Image

```json
{
  "type": "image",
  "title": "PDT星通站实现一站多能",
  "source": {"kind": "figure", "id": "fig-007"},
  "asset_path": "assets/figures/fig-007.png",
  "source_refs": ["src_002544_2025-07-07"],
  "sources": [{"kind": "figure", "id": "fig-007"}]
}
```

asset path 必须是 bundle 内已存在的相对路径；绝对路径、父目录跳转和不存在的文件都会被拒绝。
image source 可以是原生 figure 或 image-only table。

## Manifest

Manifest v3.0.0 由 `schemas/visualization_manifest.schema.json` 冻结，为每个生成物记录：

```json
{
  "slide_id": "slide_006",
  "visualization_id": "visual_001",
  "visual_type": "chart",
  "sources": [
    {"kind": "block", "id": "p005-b001"},
    {"kind": "table", "id": "table-003"},
    {"kind": "figure", "id": "fig-001"}
  ],
  "visualization_file": "slide_006__visual_001.json"
}
```

Manifest 还记录 Outline、DocumentBundle 的稳定身份和 `asset_root`。Compiler 通过
Manifest loader 校验每个文件、声明类型和 Visualization Schema；迁移期 loader
继续只读兼容 v2.0，但 Generator 只输出 v3.0.0。

## Renderer 边界

当前冻结 Renderer 支持 PPT 原生 chart/table。image Schema 和生成链路已经完成，但 Renderer
尚无 image slot/插图实现；预检会明确输出 `image_not_supported_by_frozen_renderer`。

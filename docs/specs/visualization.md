# Visualization JSON Schema

## 定位

Visualization Pipeline 分为两个边界明确的阶段：

```text
Slide Outline + Document Intelligence
  → Visualization Planning（语义判断，无 values/路径）
  → Deterministic Generator（只读取 DocumentBundle 事实）
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

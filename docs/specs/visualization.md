# Visualization JSON Schema

## 1. 定位

Visualization JSON 是独立的可视化数据层，负责回答“需要展示什么数据”。它接收 Slide Outline 的可视化候选和来源引用，输出经过抽取与核对的 chart 或 table 数据。

它不负责：

- 决定页面业务主题。
- 选择 PPT 模板 Layout。
- 保存坐标、字体、颜色等渲染属性。
- 执行 `python-pptx` 渲染。

正式 Schema 位于 `schemas/visualization.schema.json`，使用 JSON Schema Draft 2020-12。一个 JSON 文档表示一个 chart 或一个 table。

## 2. Chart

```json
{
  "chart_type": "line",
  "title": "营业收入增长",
  "unit": "亿元",
  "categories": ["2023A", "2024A", "2025E"],
  "series": [
    {
      "name": "营业收入",
      "values": [100, 120, 150]
    }
  ],
  "source_refs": ["src_annual_2025"]
}
```

支持的 `chart_type`：

- `line`
- `column`
- `bar`
- `area`
- `pie`
- `scatter`
- `combo`

`values` 接受数值或 `null`。缺失值应使用 `null`，不得使用 0 伪装缺失数据。可选的 `forecast_start_index` 标记第一个预测期，可选的 `axis` 标记系列使用主轴或次轴。

## 3. Table

```json
{
  "title": "盈利预测",
  "columns": ["项目", "2025E", "2026E"],
  "rows": [
    ["收入", 100, 120]
  ],
  "source_refs": ["src_calc_forecast"]
}
```

表格单元格支持字符串、数值、布尔值和 `null`。`unit` 和 `note` 为可选字段。

## 4. 来源和语义校验

chart 和 table 都必须提供至少一个 `source_refs`，每项必须是以 `src_` 开头的来源 ID，并引用 Slide Outline 顶层 `sources`。

标准 JSON Schema 负责结构验证。以下跨字段或跨文件规则应由后续语义校验器完成：

- 每个 `source_refs` 都能在 Slide Outline 中找到。
- 每个 series 的 values 数量等于 categories 数量。
- 每个 table row 的单元格数量等于 columns 数量。
- `forecast_start_index` 在 categories 范围内。
- 所有数值都能追溯到原文或明确计算依据。

## 5. 与其他层的关系

```text
visual_candidates（意图）
  → 数值抽取与事实核对
  → Visualization JSON（数据）
  → Template Mapping（落位）
  → Renderer（生成图表、表格和 PPTX）
```

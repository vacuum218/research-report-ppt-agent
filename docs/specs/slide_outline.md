# Slide Outline JSON Schema

## 1. 定位与边界

Slide Outline JSON 是研报内容语义层的数据契约，负责回答“这一页讲什么”。它连接结构化 Document JSON 与后续 Visualization Detector，但不承担图表数据、模板映射或 PPT 渲染职责。

允许描述：

- 报告及公司基本信息。
- 全局来源目录。
- 页面业务主题和结构角色。
- 页面核心观点与支撑要点。
- 页面引用了哪些来源。
- 是否存在图表或表格候选。

禁止描述：

- `layout_id` 或具体模板名称。
- PPT 坐标、字体、颜色。
- `python-pptx` 对象。
- chart 的 categories、series、values。
- table 的 columns、rows。

正式 Schema 位于 `schemas/slide_outline.schema.json`，使用 JSON Schema Draft 2020-12，当前版本为 `1.0.0`。

## 2. 数据流分层

```text
Document JSON
  → Slide Outline JSON：这一页讲什么
  → Visualization JSON：展示什么数据
  → Layout Mapping：如何放入 PPT 模板
  → PPT Renderer：如何生成 PPTX
```

`layout_hint` 只是 Outline Generator 给出的非强制建议。T2.5 可以忽略或修正它，最终模板选择由独立的 Template Mapping 决定。

## 3. 顶层结构

```json
{
  "schema_version": "1.0.0",
  "metadata": {},
  "sources": [],
  "slides": []
}
```

四个顶层字段均为必需字段。

### metadata

| 字段 | 说明 |
|---|---|
| `company` | 公司主体或法定全称 |
| `company_name` | 用于封面和文件名的展示名称 |
| `stock_code` | 股票代码 |
| `industry` | 所属行业 |
| `report_title` | 研报标题 |
| `report_date` | 报告日期，推荐 `YYYY-MM-DD` |
| `source_file` | 输入文件名或输入文档标识 |

## 4. 全局来源目录

`sources` 集中保存来源信息，页面和可视化只保存 `source_id`，不重复保存全文。

```json
{
  "source_id": "src_annual_2025",
  "type": "annual_report",
  "title": "公司2025年年度报告",
  "locator": "财务报表章节"
}
```

`source_id` 必须以 `src_` 开头，并在同一 Outline 中唯一。支持的来源类型包括年报、季报、公司公告、券商研报、数据库、网站、计算结果、用户输入和其他来源。

页面及候选中的 `source_refs` 是去重的 `source_id` 字符串数组。所有引用都必须能在顶层 `sources` 中找到。

标准 JSON Schema 只能验证 ID 格式和完全重复对象，不能验证“某个属性在数组中唯一”及跨数组引用存在性。因此 `source_id` 唯一性和引用完整性属于生成后的语义校验器职责。

## 5. 页面结构

每页必需字段：

- `slide_id`
- `page_role`
- `slide_type`
- `title`
- `key_message`
- `bullet_points`
- `source_refs`
- `visual_candidates`

可选字段：

- `section`
- `layout_hint`

### slide_type

`slide_type` 只表达“这一页讲什么业务主题”：

- `company_overview`
- `industry_analysis`
- `business_model`
- `core_competitiveness`
- `financial_forecast`
- `valuation_analysis`
- `investment_risk`
- `summary`

不得使用 `chart`、`table`、`two_column`、`content` 等布局或页面形式作为 `slide_type`。

### page_role

`page_role` 只表达页面在整份报告中的结构作用：

- `title`
- `section`
- `content`
- `closing`

### layout_hint

`layout_hint` 是不限制具体取值的非空字符串，例如 `title_content`、`two_column`、`chart_page`、`table_page`。它不是 `layout_id`，也不绑定某个模板。

## 6. 可视化候选

Slide Outline 中的候选只描述可视化意图：

```json
{
  "candidate_id": "visual_001",
  "type": "chart",
  "description": "展示收入增长趋势",
  "source_refs": ["src_annual_2025"]
}
```

基础字段为 `candidate_id`、`type`、`description`、`source_refs`；`type` 为 `chart` 或 `table`。候选对象允许额外扩展字段，但不得把 categories、series、values、columns 或 rows 当作 Slide Outline 的标准字段。完成抽取后的数据应使用 `visualization.schema.json`。

## 7. 字段职责

| 字段或文件 | 回答的问题 |
|---|---|
| `slide_type` | 这一页讲什么业务主题？ |
| `page_role` | 这一页在报告结构中是什么角色？ |
| `layout_hint` | 内容模块建议怎样呈现？ |
| `visualization.schema.json` | 具体展示什么 chart/table 数据？ |
| Template Mapping | 最终选择什么模板版式？ |
| Renderer | 如何生成 PPTX？ |

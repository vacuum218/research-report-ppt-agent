# Slide Outline JSON Schema

## 1. 定位

Slide Outline JSON 是研报内容语义层的数据契约，用于连接文档解析、大纲生成、可视化检测和 PPT 生成模块。

它描述：

- 一页主要讨论什么业务主题。
- 页面在整份报告中承担什么角色。
- 本页希望传达的核心观点。
- 内容来自哪些原文位置。
- 是否存在适合进一步处理的可视化候选。

它不描述 PPT 坐标、字体、颜色、具体模板 Layout 或最终排版。最终版式由 T2.5 Template Mapping 根据页面语义、内容量、模板能力和 `layout_hint` 综合决定。

正式 Schema 位于 `schemas/slide_outline.schema.json`，使用 JSON Schema Draft 2020-12，当前版本为 `1.0.0`。

## 2. 顶层结构

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | 是 | 接口版本，当前固定为 `1.0.0` |
| `metadata` | 是 | 研报基本信息 |
| `slides` | 是 | 按叙事顺序排列的页面列表，至少一页 |

`metadata` 包含：

- `company`：公司名称。
- `industry`：所属行业。
- `report_date`：报告日期，推荐 `YYYY-MM-DD`；无法确定时允许空字符串。
- `source_file`：输入研报文件名或可追溯标识。

## 3. 页面字段

每个页面必须包含：

- `slide_id`：稳定页面标识，格式为 `slide-*`。
- `title`：页面标题。
- `slide_type`：业务内容分类。
- `page_role`：页面在报告中的结构角色。
- `key_message`：本页单一核心观点，类型为字符串。
- `bullet_points`：支撑核心观点的要点列表。
- `source_refs`：页面内容对应的一个或多个原文引用。
- `visual_candidates`：可视化候选列表。

可选字段：

- `section`：页面所属研报章节。
- `layout_hint`：大纲生成阶段给出的非强制布局建议。

### slide_type

`slide_type` 只表达“这一页主要讨论什么业务主题”，允许值为：

- `company_overview`
- `industry_analysis`
- `business_model`
- `core_competitiveness`
- `financial_forecast`
- `valuation_analysis`
- `investment_risk`
- `summary`

### page_role

`page_role` 只表达页面角色，允许值为：

- `title`
- `section`
- `content`
- `closing`

### layout_hint

`layout_hint` 是可选的普通字符串，例如：

- `title_content`
- `two_column`
- `chart_page`
- `table_page`

它不直接绑定模板 Layout，也不保证渲染器采用该建议。

## 4. 来源追溯

`source_refs` 是引用对象数组。每个引用包含：

| 字段 | 说明 |
|---|---|
| `text` | 支撑页面内容或可视化候选的原文，不能为空 |
| `section` | 原文所在章节；无法确定时可为空字符串 |
| `location` | 页码、段落、节点 ID 等位置描述；无法确定时可为空字符串 |

标题页、章节页和尾页允许使用空的页面级 `source_refs`。内容页是否必须存在来源属于语义校验规则，后续由独立校验器结合 `page_role` 和原始文档检查。

## 5. 可视化候选

每个 `visual_candidates` 项目的基础字段为：

- `candidate_id`：稳定候选标识，格式为 `visual-*`。
- `type`：候选类型，例如 `line_chart`、`bar_chart` 或 `table`。
- `description`：希望表达的可视化内容。
- `source_refs`：支撑该候选的原文引用，至少一项。

可视化候选对象允许额外字段，以便 Week 3 增加优先级、单位、数据抽取状态等信息，而无需破坏 Slide Outline 1.0 接口。具体 categories、series 和 values 应由独立的 Visualization JSON Schema 定义。

## 6. 分层约束

三个字段职责不得混用：

| 字段 | 负责回答的问题 |
|---|---|
| `slide_type` | 这一页讲什么业务主题？ |
| `page_role` | 这一页在报告结构中是什么角色？ |
| `layout_hint` | 内容生成模块建议怎样呈现？ |

最终 PPT 布局由 T2.5 负责。Slide Outline 中不得加入坐标、字体、颜色或模板 Layout 名称等渲染层字段。

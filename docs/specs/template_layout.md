# 财报 PPT 模板版式与占位区域说明

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 财报 PPT 模板版式与占位区域说明 |
| 文档版本 | 1.0 |
| 对应模板 | `financial_report_template_v1.pptx` |
| 对象清单 | `template_objects.json` |
| 模板页数 | 16 |
| 页面比例 | 16:9 |
| 页面尺寸 | 13.3333 × 7.5 英寸 |
| 主要用途 | 指导大纲 JSON 到财报 PPT 页面的版式选择与内容填充 |

## 2. 文档目的

本文档面向项目开发、内容评审和模板维护人员，用于说明：

1. 模板中每种页面版式的用途和适用条件。
2. 每种版式包含哪些可填充区域。
3. 各区域对应的大纲 JSON 字段、内容类型和容量限制。
4. 内容缺失、超长或数量超限时的处理方法。
5. 后续 `template_layout_map.json` 应遵循的语义约定。

模板中的图表为版式示例，不代表最终报告必须使用相同图表类型或数据。实际渲染时，应根据大纲 JSON 动态创建图表，并放入本文件规定的逻辑图表槽位。

## 3. 模板使用原则

### 3.1 一页一个核心结论

每页只表达一个主要观点。页面标题应优先使用结论式标题，例如：

> 品牌业务占比提升，推动收入韧性和利润结构改善

避免仅使用“财务分析”“行业分析”等缺少信息量的标题。

### 3.2 版式数量不等于最终页数

模板的 16 页代表 16 种参考页面或内容角色。实际生成时允许：

- 重复使用 `chart_text`、`two_charts` 等分析版式。
- 根据报告内容省略不适用的页面。
- 将图表过多或要点过多的内容拆分为多页。
- 将详细数据移动到 `appendix`。

### 3.3 图表采用逻辑槽位

原始对象清单中的图表名称可能为通用名称 `Chart`。渲染器不应仅依赖该名称，而应使用语义锚点定位图表区域：

| 页面 | 逻辑槽位 | 位置锚点 |
|---|---|---|
| 业务结构 | `chart_left` | `chart_left_panel` |
| 业务结构 | `chart_right` | `chart_right_panel` |
| 行业空间 | `chart_main` | `industry_chart_panel` |
| 单图分析 | `chart_main` | `logic_chart_panel` |
| 双图分析 | `chart_left` | `two_chart_left` |
| 双图分析 | `chart_right` | `two_chart_right` |
| 历史财务 | `chart_main` | `financial_chart_panel` |
| 盈利预测 | `chart_main` | `forecast_chart_panel` |
| 估值分析 | `chart_main` | `valuation_chart_panel` |

推荐渲染方式：删除或忽略模板示例图表，读取锚点对象坐标，然后创建新的图表。

### 3.4 对象定位规则

对象定位优先级如下：

1. 唯一语义对象名称，如 `title`、`logic_bullets`。
2. 逻辑槽位对应的锚点对象名称，如 `two_chart_left`。
3. 对象类型和坐标范围。
4. 对象在该页同类型对象中的顺序，仅作为最后的兼容方案。

不要将 `shape_id` 作为跨模板版本的唯一标识，因为模板重新保存或重新生成后，`shape_id` 可能变化。

## 4. 全局视觉规范

### 4.1 颜色

| 用途 | 颜色 |
|---|---|
| 主标题、深色背景 | `#102A43` |
| 主强调色 | `#2F6FED` |
| 辅助强调色 | `#16A3A5` |
| 正向或增长提示 | `#2E9D67` |
| 催化剂或重点提醒 | `#F59E0B` |
| 风险提示 | `#D95C5C` |
| 页面背景 | `#F7F9FC` |
| 主正文 | `#1F2937` |
| 辅助正文 | `#64748B` |

### 4.2 字体与字号

| 内容 | 建议字号 |
|---|---:|
| 封面主标题 | 50–56 pt |
| 正文页标题 | 32–38 pt |
| 核心结论或大数字 | 26–34 pt |
| 模块标题 | 20–24 pt |
| 正文 | 16–20 pt |
| 图表标签 | 10–14 pt |
| 来源与页脚 | 9–11 pt |

中文字体优先使用 Microsoft YaHei 或项目统一指定的无衬线中文字体。

### 4.3 公共对象

除封面外，大部分正文页包含以下公共对象：

| 对象名称 | 类型 | 用途 | 填充方式 |
|---|---|---|---|
| `layout_label` | 文本 | 模板或章节辅助标签 | 通常保留或隐藏 |
| `title` | 文本 | 页面主标题 | 来自 `slide.title` |
| `header_rule` | 线条 | 标题区分隔线 | 保留样式 |
| `layout_type` | 文本 | 版式名称 | 调试时保留，正式输出可隐藏 |
| `page_no` | 文本 | 页码 | 渲染器自动生成 |
| `source` | 文本 | 数据来源 | 来自 `slide.source_refs` |

## 5. 内容类型约定

| 类型 | 说明 |
|---|---|
| `text` | 普通文本或结论文本 |
| `bullet_list` | 要点列表 |
| `metric` | 指标值、指标名和辅助说明 |
| `chart_slot` | 动态生成图表的区域 |
| `table` | 可编辑表格 |
| `timeline` | 时间轴节点集合 |
| `matrix` | 二维竞争矩阵或定位矩阵 |
| `source_list` | 数据来源或原文引用列表 |
| `auto` | 页码等由渲染器生成的内容 |

## 6. 版式总览

| 模板页 | `layout_id` | 页面类型 | 核心用途 |
|---:|---|---|---|
| 1 | `cover` | 封面 | 报告标题和公司信息 |
| 2 | `agenda` | 目录 | 展示报告章节结构 |
| 3 | `executive_summary` | 核心结论 | 投资结论、核心逻辑和关键指标 |
| 4 | `company_overview` | 公司概览 | 公司定位、业务结构和规模 |
| 5 | `timeline` | 发展历程 | 战略阶段和关键节点 |
| 6 | `business_structure` | 业务结构 | 分业务收入、占比或毛利率 |
| 7 | `industry_outlook` | 行业空间 | 行业趋势和驱动因素 |
| 8 | `competitive_landscape` | 竞争格局 | 竞争定位和护城河 |
| 9 | `chart_text` | 单图分析 | 一张主图配解释与结论 |
| 10 | `two_charts` | 双图分析 | 两张相关图表共同支撑结论 |
| 11 | `capability_map` | 能力路径 | 能力、进展和商业兑现路径 |
| 12 | `financial_review` | 历史财务 | 收入、利润率和现金流质量 |
| 13 | `earnings_forecast` | 盈利预测 | 预测表、趋势图和核心假设 |
| 14 | `valuation` | 估值分析 | 可比估值、估值判断和结论 |
| 15 | `risk_catalyst` | 风险与催化剂 | 上行因素和结论失效条件 |
| 16 | `appendix` | 附录 | 财务明细、口径和来源 |

## 7. 各版式详细说明

### 7.1 `cover`：封面

- 模板页：1
- 适用场景：每份报告的第一页。
- 主要任务：说明报告对象、主题、日期和汇报信息。

| 语义字段 | 模板对象 | 必填 | 内容限制 |
|---|---|---:|---|
| `company_name` | `cover_title` 的公司名称部分 | 是 | 建议不超过 12 个汉字 |
| `report_title` | `cover_title` | 是 | 总长度建议不超过 24 个汉字 |
| `subtitle` | `cover_subtitle` | 否 | 建议不超过 30 个汉字 |
| `stock_code` | `cover_meta` | 否 | 股票代码或公司标识 |
| `report_date` | `cover_meta` | 是 | `YYYY-MM-DD` |
| `presenter` | `cover_meta` | 否 | 汇报人或团队名称 |

超限处理：优先压缩副标题；主标题仍超限时允许分为两行，但不得缩小到 44 pt 以下。

### 7.2 `agenda`：目录

- 模板页：2
- 适用场景：报告包含 3 个以上章节时。
- 推荐章节数：4–6 个。

| 语义字段 | 模板对象模式 | 必填 | 内容限制 |
|---|---|---:|---|
| `items[].number` | `agenda_no_*` | 是 | 两位编号 |
| `items[].title` | `agenda_title_*` | 是 | 每项不超过 8 个汉字 |
| `items[].description` | `agenda_desc_*` | 否 | 每项不超过 20 个汉字 |

少于 4 个章节时可扩大行距；超过 6 个章节时应合并相近章节。

### 7.3 `executive_summary`：核心结论

- 模板页：3
- 适用场景：报告结论总览。
- 页面容量：1 条总判断、3 条核心逻辑、4 个关键指标。

| 语义字段 | 模板对象 | 必填 | 内容限制 |
|---|---|---:|---|
| `thesis` | `thesis` | 是 | 不超过 45 个汉字 |
| `logics[0..2].title` | `logic_*_title` | 是 | 每项不超过 10 个汉字 |
| `logics[0..2].body` | `logic_*_body` | 是 | 每项不超过 45 个汉字 |
| `metrics[0..3].value` | `metric_*_value` | 是 | 数值或短文本 |
| `metrics[0..3].label` | `metric_*_label` | 是 | 不超过 12 个汉字 |
| `metrics[0..3].note` | `metric_*_note` | 否 | 不超过 15 个汉字 |
| `source_refs` | `source` | 否 | 建议不超过 2 条 |

不足 3 条逻辑时允许保留空白或切换到普通概览版式；超过 3 条时保留优先级最高的 3 条。

### 7.4 `company_overview`：公司概览

- 模板页：4
- 适用场景：说明公司定位、主营业务和规模。

| 语义字段 | 模板对象 | 必填 | 内容限制 |
|---|---|---:|---|
| `company.name` | `company_name` | 是 | 不超过 12 个汉字 |
| `company.code` | `company_code` | 否 | 股票代码或公司标识 |
| `company.positioning` | `company_positioning` | 是 | 1 条定位和 3–5 条属性 |
| `segments[0..2].title` | `business_*_title` | 是 | 每项不超过 10 个汉字 |
| `segments[0..2].body` | `business_*_body` | 是 | 每项不超过 45 个汉字 |
| `key_metric.value` | `metric_年度营业收入_value` | 否 | 单个关键规模指标 |
| `key_metric.label` | `metric_年度营业收入_label` | 否 | 不超过 12 个汉字 |

业务板块多于 3 个时，应合并为核心业务、成长业务和战略业务三个层级，或改用业务结构页。

### 7.5 `timeline`：发展历程

- 模板页：5
- 适用场景：公司发展阶段、技术路线或战略演进。
- 推荐节点数：3–4 个；最大 4 个。

| 语义字段 | 模板对象模式 | 必填 | 内容限制 |
|---|---|---:|---|
| `milestones[].stage` | `timeline_stage_*` | 是 | 不超过 8 个汉字 |
| `milestones[].title` | `timeline_title_*` | 是 | 不超过 12 个汉字 |
| `milestones[].description` | `timeline_body_*` | 否 | 不超过 25 个汉字 |
| `takeaway` | `timeline_takeaway` | 否 | 不超过 40 个汉字 |

超过 4 个节点时，只保留改变业务结构或增长曲线的关键节点。

### 7.6 `business_structure`：业务结构

- 模板页：6
- 适用场景：分业务收入、占比、毛利率或增速对比。
- 图表槽位：2。

| 逻辑槽位 | 位置锚点 | 必填 | 推荐用途 |
|---|---|---:|---|
| `chart_left` | `chart_left_panel` | 是 | 分业务收入或收入占比 |
| `chart_right` | `chart_right_panel` | 是 | 分业务毛利率或增速 |
| `chart_left_title` | `chart_left_title` | 是 | 左图标题 |
| `chart_right_title` | `chart_right_title` | 是 | 右图标题 |

每张图建议不超过 8 个分类和 3 个系列。只有一个图表时应使用 `chart_text`，不要留出大面积空白。

### 7.7 `industry_outlook`：行业空间

- 模板页：7
- 适用场景：行业规模、渗透率、景气指数或资本开支趋势。
- 图表槽位：1。
- 驱动因素：最多 3 项。

| 语义字段 | 模板对象 | 必填 | 内容限制 |
|---|---|---:|---|
| `chart` | 锚点 `industry_chart_panel` | 是 | 1 个主趋势图 |
| `chart.title` | `industry_chart_title` | 是 | 不超过 18 个汉字 |
| `drivers[0..2].title` | `driver_*_title` | 是 | 每项不超过 8 个汉字 |
| `drivers[0..2].body` | `driver_*_body` | 是 | 每项不超过 35 个汉字 |

驱动因素不足 3 项时可保留 2 项并扩大间距；超过 3 项时合并同类因素。

### 7.8 `competitive_landscape`：竞争格局

- 模板页：8
- 适用场景：二维定位、竞争对比和护城河总结。

| 语义字段 | 模板对象模式 | 必填 | 内容限制 |
|---|---|---:|---|
| `matrix.x_axis` | `matrix_x_label` | 是 | 不超过 12 个汉字 |
| `matrix.y_axis` | `matrix_y_label` | 是 | 不超过 12 个汉字 |
| `matrix.points[]` | `matrix_point_*`、`matrix_label_*` | 是 | 推荐 3–6 个对象 |
| `moats[0..2].title` | `moat_*_title` | 是 | 不超过 10 个汉字 |
| `moats[0..2].body` | `moat_*_body` | 是 | 不超过 35 个汉字 |

维度必须依据行业特征确定，不能跨行业固定使用同一组维度。

### 7.9 `chart_text`：单图表分析

- 模板页：9
- 适用场景：一个核心图表配合解释和结论。
- 图表槽位：1。

| 语义字段 | 模板对象 | 必填 | 内容限制 |
|---|---|---:|---|
| `chart` | 锚点 `logic_chart_panel` | 是 | 最多 8 个分类、3 个系列 |
| `chart.title` | `logic_chart_title` | 是 | 不超过 18 个汉字 |
| `takeaway` | `logic_main_point` | 是 | 不超过 25 个汉字 |
| `bullets` | `logic_bullets` | 是 | 2–4 条，每条不超过 30 字 |
| `conclusion` | `logic_conclusion_text` | 否 | 不超过 35 个汉字 |

没有结构化图表数据时，应降级为公司概览或普通要点版式。

### 7.10 `two_charts`：双图表分析

- 模板页：10
- 适用场景：两张图共同验证一个结论，例如增长与盈利、规模与份额。
- 图表槽位：2。

| 逻辑槽位 | 位置锚点 | 必填 | 内容限制 |
|---|---|---:|---|
| `chart_left` | `two_chart_left` | 是 | 最多 8 个分类、3 个系列 |
| `chart_right` | `two_chart_right` | 是 | 最多 8 个分类、3 个系列 |
| `chart_left_title` | `two_chart_left_title` | 是 | 不超过 16 个汉字 |
| `chart_right_title` | `two_chart_right_title` | 是 | 不超过 16 个汉字 |
| `conclusion` | `two_chart_conclusion` | 是 | 不超过 45 个汉字 |

两张图必须服务同一个结论。若只有一张图，切换至 `chart_text`。

### 7.11 `capability_map`：能力与兑现路径

- 模板页：11
- 适用场景：新业务、产品管线、订单兑现、产能爬坡或商业化路径。

| 语义字段 | 模板对象 | 必填 | 内容限制 |
|---|---|---:|---|
| `stages[0].title/body` | `capability_1_title/body` | 是 | 单段正文不超过 70 字 |
| `stages[1].title/body` | `capability_2_title/body` | 是 | 单段正文不超过 70 字 |
| `stages[2].title/body` | `capability_3_title/body` | 是 | 单段正文不超过 70 字 |
| `catalyst_path` | `catalyst_strip_body` | 是 | 3–5 个短节点 |

页面只表达一条连续的商业兑现路径，避免将互不相关的三项业务强行组合。

### 7.12 `financial_review`：历史财务表现

- 模板页：12
- 适用场景：历史收入、利润、利润率、现金流和经营质量分析。
- 图表槽位：1。
- 指标槽位：3。

| 语义字段 | 模板对象 | 必填 | 内容限制 |
|---|---|---:|---|
| `chart` | 锚点 `financial_chart_panel` | 是 | 建议 3–5 年数据 |
| `chart.title` | `financial_chart_title` | 是 | 不超过 20 个汉字 |
| `metrics[0..2].value` | `metric_*_value` | 是 | 数值或短结论 |
| `metrics[0..2].label` | `metric_*_label` | 是 | 不超过 12 个汉字 |
| `metrics[0..2].note` | `metric_*_note` | 否 | 不超过 18 个汉字 |

不同单位的指标不应无说明地放在同一坐标轴。必要时使用指数化数据或拆分页面。

### 7.13 `earnings_forecast`：盈利预测

- 模板页：13
- 适用场景：分业务预测、盈利预测和核心假设。
- 表格槽位：1。
- 图表槽位：1。

| 语义字段 | 模板对象 | 必填 | 内容限制 |
|---|---|---:|---|
| `table` | `forecast_table` | 是 | 最大 7 行 × 5 列 |
| `chart` | 锚点 `forecast_chart_panel` | 否 | 主要总量指标趋势 |
| `note` | `forecast_note` | 否 | 单位和 A/E 说明 |
| `assumptions` | `forecast_assumption` | 是 | 2–4 条，每条不超过 22 字 |
| `source_refs` | `source` | 是 | 预测依据或原始来源 |

表格超过 7 行时保留关键业务和合计项，其余移动到附录。

### 7.14 `valuation`：估值分析

- 模板页：14
- 适用场景：可比公司估值、历史估值或目标价值分析。
- 图表槽位：1。

| 语义字段 | 模板对象 | 必填 | 内容限制 |
|---|---|---:|---|
| `chart` | 锚点 `valuation_chart_panel` | 是 | 建议不超过 8 个比较对象 |
| `chart.title` | `valuation_chart_title` | 是 | 不超过 18 个汉字 |
| `headline` | `valuation_headline` | 是 | 不超过 30 个汉字 |
| `bullets` | `valuation_bullets` | 是 | 2–4 条，每条不超过 30 字 |
| `conclusion` | `valuation_conclusion_text` | 是 | 评级、区间或目标价 |

必须注明估值口径、预测年度和股价基准日。没有可靠估值数据时，不得虚构目标价。

### 7.15 `risk_catalyst`：风险与催化剂

- 模板页：15
- 适用场景：总结上行触发因素和结论失效条件。
- 每侧最大条目数：4。

| 语义字段 | 模板对象模式 | 必填 | 内容限制 |
|---|---|---:|---|
| `catalysts[]` | `catalyst_item_*` | 否 | 最多 4 条，每条不超过 24 字 |
| `risks[]` | `risk_item_*` | 是 | 最多 4 条，每条不超过 24 字 |

风险应具体说明可能受影响的业务或指标，避免只使用“市场风险”“政策风险”等空泛表述。

### 7.16 `appendix`：附录

- 模板页：16
- 适用场景：详细财务指标、统计口径、数据来源和补充说明。
- 表格槽位：1。

| 语义字段 | 模板对象 | 必填 | 内容限制 |
|---|---|---:|---|
| `table` | `appendix_financial_table` | 是 | 最大 9 行 × 5 列 |
| `source_policy_title` | `appendix_sources_title` | 否 | 不超过 12 个汉字 |
| `source_policy` | `appendix_sources` | 否 | 不超过 80 个汉字 |
| `source_refs` | `source` | 是 | 来源列表 |

数据超过单页容量时允许生成多个附录页，但每页必须重复表头和单位说明。

## 8. 图表输入约定

图表数据建议统一为以下结构：

```json
{
  "chart_type": "line",
  "title": "营业收入持续增长",
  "unit": "亿元",
  "categories": ["2023A", "2024A", "2025E", "2026E"],
  "series": [
    {
      "name": "营业收入",
      "values": [100.0, 120.0, 145.0, 170.0]
    }
  ],
  "source_refs": ["source_001"]
}
```

推荐限制：

- 单图分类数不超过 8。
- 单图系列数不超过 3。
- 折线图主要用于时间趋势。
- 柱状图主要用于分类比较。
- 饼图仅用于少量互斥类别的占比展示，类别不超过 6。
- 不使用三维图表。
- 历史值和预测值应在颜色、线型或标签中明确区分。

## 9. 表格输入约定

表格数据建议统一为：

```json
{
  "title": "分业务盈利预测",
  "unit": "亿元",
  "columns": ["项目", "2024A", "2025E", "2026E", "2027E"],
  "rows": [
    ["业务 A", 100.0, 110.0, 125.0, 140.0],
    ["业务 B", 20.0, 28.0, 36.0, 45.0]
  ],
  "source_refs": ["source_001"]
}
```

表格规则：

- 数字保持数值类型，不提前拼接单位。
- 百分比、货币和倍数由渲染器统一格式化。
- 实际值使用 `A`，预测值使用 `E`。
- 合计行和关键利润指标应高亮。
- 超出页面容量的行应筛选或转移到附录。

## 10. 内容溢出与降级规则

| 情况 | 处理方式 |
|---|---|
| 标题过长 | 优先压缩措辞；必要时允许两行；禁止无限缩小字号 |
| 要点过多 | 按优先级保留；其余拆页或移动到附录 |
| 无图表数据 | 切换到纯文本或概览版式 |
| 只有 1 张图 | 使用 `chart_text` |
| 有 2 张相关图 | 使用 `two_charts` |
| 有 3 张以上图 | 拆页或筛选最重要的 1–2 张 |
| 表格行数超限 | 保留关键行，其他行进入附录 |
| 缺少来源 | 标记为数据质量问题，不得静默删除来源区域 |
| 图表类型不适配 | 根据数据语义重新选择图表类型 |

## 11. 与大纲 JSON 的建议映射

建议幻灯片对象至少提供以下字段：

```json
{
  "slide_id": "slide_009",
  "layout_id": "chart_text",
  "title": "品牌业务占比提升，推动利润结构改善",
  "takeaway": "结构升级比单纯规模扩张更重要",
  "bullets": [
    "自有品牌提升定价权",
    "收入波动小于传统代工业务"
  ],
  "charts": [],
  "tables": [],
  "conclusion": "结构变化正在转化为盈利质量改善",
  "source_refs": ["source_001"]
}
```

主要映射关系：

| 大纲 JSON 字段 | 模板语义区域 |
|---|---|
| `layout_id` | 版式选择 |
| `title` | `title` |
| `takeaway` | 页面核心结论区域 |
| `bullets` | 要点列表区域 |
| `metrics` | KPI 指标区域 |
| `charts` | 图表逻辑槽位 |
| `tables` | 表格对象或表格槽位 |
| `conclusion` | 底部结论区域 |
| `source_refs` | `source` |

## 12. 验收标准

模板和版式说明满足以下条件时，可进入 `template_layout_map.json` 制作阶段：

1. 16 个模板页面均有唯一 `layout_id`。
2. 每个版式的用途、必填字段和容量限制明确。
3. 图表页面均定义了逻辑槽位和位置锚点。
4. 表格页面明确最大行列数。
5. 公共对象与大纲 JSON 字段关系清晰。
6. 溢出、缺失和数量超限时存在明确降级规则。
7. `template_objects.json` 中对应锚点对象实际存在。

## 13. 已知注意事项

1. 原生图表对象在当前 PPTX 中被命名为通用名称 `Chart`。
2. 第 6 页和第 10 页各有两个同名图表对象。
3. 当前方案不依赖图表对象名称，而依赖语义面板对象定位图表槽位，因此上述重名不影响 MVP。
4. `template_objects.json` 中的 `source_path` 为生成环境的绝对路径，不应作为项目运行时依赖；跨环境使用时只保留 `source_file` 即可。
5. `template_objects.json` 是检查产物，不能直接替代最终的 `template_layout_map.json`。

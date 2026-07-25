# 研报到演示文稿生成系统：目标架构与重构实施要求

> 状态：待实施的目标架构说明，不代表当前代码已经具备这些能力  
> 适用对象：负责后续架构重构、数据契约、流水线与质量保障的开发人员  
> 更新日期：2026-07-25

## 1. 文档目的

本文档用于明确本项目下一阶段的产品目标、架构边界、模块职责、数据契约、硬性质量要求、迁移顺序与验收标准。

后续开发不得仅以“JSON Schema 合法、PPTX 可以打开、图表数值可追溯”为完成标准。最终目标是生成一份能够用于研报展演的 PPTX：内容顺序忠实、观点清楚、视觉选择合理、图文相关、页面可读。

本文中的关键词含义如下：

- **必须（MUST）**：验收硬要求，不满足不得合并到主链路。
- **应该（SHOULD）**：默认实现要求；若不实现，必须在设计记录中说明原因。
- **可以（MAY）**：可选增强能力，不阻塞首期重构。

## 2. 产品目标与边界

### 2.1 输入

系统必须至少支持：

- PDF 证券研究报告；
- Markdown 证券研究报告；
- TXT 证券研究报告。

典型输入是一家证券机构发布的某家上市公司研究报告，通常包含：

- 封面和报告元数据；
- 核心观点或投资要点；
- 公司概况；
- 行业分析；
- 业务、产品或竞争力分析；
- 原始图、表；
- 文字描述的数值事实；
- 盈利预测、估值和风险提示；
- 分析师信息、评级说明和免责声明等后台内容。

三种输入格式允许在定位模型和原始资源能力上有差异，但进入语义规划前必须归一为同一个正式数据模型。

### 2.2 输出

系统输出一份可编辑的 `.pptx`，并至少满足：

1. 按研报的章节与论证顺序组织，不随意重排核心结论。
2. 选择适合展演的重点，而不是逐段复制全文。
3. 合理保留研报已有的重要图表。
4. 仅将真正适合视觉化的文字数据转换为图表、表格、KPI 或对比卡片。
5. 所有事实和视觉均可追溯到输入证据。
6. 页面无文字溢出、对象越界、遮挡或不可读缩放。
7. 同页图文围绕同一核心观点，不出现证据相关但语义无关的拼接。
8. 输出失败时不得发布半成品 PPTX，但必须保留足够的诊断产物。

### 2.3 非目标

首期重构不以以下能力为目标：

- 自动补充外部网络资料；
- 为研报缺失的数据进行推测或插值；
- 生成研报没有支持的投资结论；
- 支持任意数量视觉对象的自由画布；
- 复制 MemSlides 的完整长期记忆或多 Agent 体系；
- 一次性支持所有 PowerPoint 图表和 SmartArt 类型。

## 3. 当前架构的主要问题

当前主链路大致为：

```text
DocumentBundle
  → Document Intelligence
  → LLM Slide Outline
  → Candidate Locator / Visualization Planning
  → Visualization Generator
  → Layout Compiler
  → PPT Renderer
```

该结构具有事实追溯和确定性渲染基础，但缺少两个关键决策层：

1. **研报编辑决策层**：判断哪些内容值得进入演示、每页为何存在、页面之间如何承接。
2. **页面编排决策层**：判断该页应使用文字、KPI、原图、表格还是新图表，以及实际页面容量。

由此产生以下问题：

- LLM Outline 一次承担内容理解、取舍、拆页、标题、证据和视觉意图，职责过重。
- `evidence_refs` 同时被当作叙事证据和视觉发现范围，证据多时容易产生过多图表。
- Candidate Locator 判断“能够抽取数字”，但没有可靠判断“值得画图”。
- 同章节扩展可能把多个数值段落全部变成视觉候选。
- Slide Outline 的视觉数量没有统一页面预算，而 Abstract Layout 最多只支持两个视觉。
- 文字容量按字符数近似，无法代表实际字体、换行和渲染高度。
- Renderer 使用自动缩放时可能生成技术上未越界、实际不可读的文字。
- 表格主要检查行列数，没有完整检查单元格文本在真实字号下是否可读。
- 原始 PDF figure 被强制独立成页，容易产生只有一张图、没有解读的页面。
- 自动化测试主要检查结构和对象数量，缺少渲染图像级质量检查。
- 失败后 staging 被清理，难以判断候选来自 LLM、直接证据还是章节扩展。

## 4. 目标总体架构

目标主链路必须调整为：

```text
PDF / Markdown / TXT
  → Input Adapter
  → Canonical Source Model
  → Report Understanding
  → Deck Storyboard
  → Candidate Pool
  → Metric Semantic Grouping
  → Editorial Visual Decision
  → Visual Portfolio Selection
  → Page Composition
  → Visualization Generation
  → Layout Compilation
  → PPTX Rendering
  → Render QA
  → Local Page Repair（必要时）
  → Published PPTX
```

### 4.1 核心设计原则

1. **来源事实与编辑判断分离**。
2. **候选发现与最终选择分离**。
3. **语义页面与物理页面分离**。
4. **布局选择必须早于昂贵的视觉生成**。
5. **静态容量检查与真实渲染检查并存**。
6. **LLM 可以做语义和编辑判断，但不得拥有数值事实写权限**。
7. **每个阶段都必须保存可审计的决策原因**。
8. **失败必须可诊断，修复应尽量限制在单页范围内**。

## 5. 模块与数据契约

以下契约是目标设计。具体 Schema 版本号在实施时统一确定，但不得继续把不兼容字段直接加入现有 `slide_outline.schema.json` 1.0.0。

### 5.1 Canonical Source Model

建议正式名称：`ResearchReportDocument`。

职责：统一 PDF、Markdown、TXT 的结构与证据表示，不进行摘要、重要性判断或页面规划。

必须包含：

```text
document metadata
ordered sections
ordered content blocks
native tables
native figures
captions and source notes
source locations
asset availability
parsing issues and confidence
```

实施要求：

- PDF 保留真实页码和 bbox。
- Markdown/TXT 保留行号范围，不伪造 PDF 坐标。
- Markdown 本地图片必须复制到 bundle `assets/` 下。
- Markdown 远程图片默认不得在无明确下载策略时进入最终 PPT。
- TXT 必须明确声明没有原生视觉资产，不能伪造 figure。
- 原始顺序必须可确定性重建。
- 免责声明、分析师信息等在本层保留，不在输入层静默删除。

现有 `DocumentBundle` 可以演进为该契约，无需另起一套重复事实层。

### 5.2 ReportMap

职责：把来源文档转换为研报语义地图，但不直接决定 PPT 坐标和具体布局。

建议结构：

```json
{
  "document_id": "report_001",
  "ordered_sections": [],
  "claims": [],
  "metric_groups": [],
  "native_assets": [],
  "content_classifications": [],
  "exclusions": []
}
```

必须识别：

- 章节层级与原始顺序；
- 每节主要观点和支持证据；
- 关键数值指标及业务范围；
- 原始 figure/table 与附近解释文字；
- 历史值、预测值、估值值、风险描述；
- 可进入主体、可进入附录、默认排除的内容。

默认排除项应包括：

- 分析师执业证书；
- 联系方式；
- 评级通用说明；
- 免责声明；
- 页码、报告编号等行政字段。

排除必须记录 reason code，不得直接从事实层删除。

### 5.3 DeckStoryboard

职责：按研报主线规划语义页面，回答“为什么需要这一页、这一页讲什么”。

建议字段：

```json
{
  "slide_intent_id": "intent_007",
  "section_ref": "sec-2-1",
  "source_order": 7,
  "purpose": "解释盈利预测的主要驱动",
  "claim": "三大业务均进入恢复期，但增长驱动不同",
  "supporting_points": [],
  "evidence_refs": [],
  "priority": "core",
  "visual_need": "optional"
}
```

硬性要求：

- `source_order` 必须保持单调，不允许无理由跨章节重排。
- 每个内容页只允许一个主要 claim。
- 标题必须服务于展演，不再强制逐字复制长章节标题。
- 原始章节标题应保留为 `section_title` 或 provenance，不与演示 headline 混用。
- 允许同一章节拆成多页，但每页 purpose/claim 必须不同。
- 不得为了达到固定页数生成低价值页面。
- 不得把所有原始 figure 强制生成独立页面。

### 5.4 CandidatePool

职责：高召回发现潜在视觉，不决定最终生成。

Candidate Locator 必须改造成候选池构建器。候选池可以包含超过页面容量的候选，但不得直接全部绑定到 slide。

每个候选必须记录：

```json
{
  "candidate_id": "cand_001",
  "origin": "outline|direct_evidence|section_fallback|native_asset",
  "evidence_refs": [],
  "candidate_kind": "numeric_text|native_table|native_figure",
  "trigger_codes": [],
  "discovery_score": 0.0
}
```

硬性要求：

- `discovery_score` 只表示“值得进一步检查”，不表示最终应展示。
- 同章节扫描只允许作为没有直接候选时的 fallback。
- fallback 结果必须降低优先级，并受严格数量限制。
- 候选来源必须可诊断。
- 候选池不得直接传给 Visualization Generator。

### 5.5 Typed Metric Facts 与 MetricGroup

现有 Numeric Fact Ledger 应保留并扩展语义字段。

目标事实模型至少包含：

```json
{
  "fact_id": "fact_001",
  "entity": "公司或业务对象",
  "metric_id": "revenue",
  "metric_label": "营业收入",
  "measure_kind": "level",
  "unit_family": "currency",
  "unit": "亿元",
  "period": "2025E",
  "scenario": "forecast",
  "scope": "公司整体",
  "value": "100",
  "source_locator": {}
}
```

`measure_kind` 至少应区分：

- `level`：收入、利润、销量等绝对量；
- `growth_rate`：同比、环比、CAGR；
- `margin`：毛利率、净利率；
- `share`：占比、市占率；
- `multiple`：PE、PB 等倍数；
- `count`：项目数、客户数等；
- `other`。

只有满足以下条件的 facts 才能进入同一 MetricGroup：

```text
entity compatible
metric_id identical
measure_kind identical
unit_family identical
scope compatible
periods non-conflicting
scenario explicitly known or compatible
```

禁止：

- 营业收入和营业收入同比进入同一序列；
- 收入和利润因单位同为亿元而进入同一序列；
- 历史值与预测值在未标记边界时混合；
- 缺失单位时由 LLM 猜测并写回事实；
- 从风险假设、日期、证券代码中构造业务序列。

### 5.6 EditorialVisualDecision

职责：判断一个候选是否值得视觉化，以及适合的表达形式。

允许的决策结果建议固定为：

```text
text
kpi
comparison_cards
source_figure
table
line
column
bar
pie
reject
```

决策对象必须包含：

```json
{
  "candidate_id": "cand_001",
  "decision": "reject",
  "recommended_form": "text",
  "editorial_value": "low",
  "selected_fact_ids": [],
  "reason_codes": ["short_series", "low_information_gain"],
  "supports_claim": false
}
```

必须同时存在：

1. 确定性预筛选；
2. LLM 编辑判断；
3. 确定性准入验证。

LLM 的具体边界见第 6 节。

### 5.7 VisualPortfolio

职责：在页面预算内，从全部合格视觉决策中选择最有价值且互补的视觉组合。

默认页面预算：

| 页面类型 | 推荐视觉数 | 硬上限 |
|---|---:|---:|
| 普通内容页且有正文 | 1 | 2 |
| 视觉主导内容页 | 1 | 2 |
| 原始 figure 主导页 | 1 | 1 |
| 封面、章节页、结束页 | 0 | 0 |

选择顺序应该综合：

- 与本页 claim 的相关性；
- 信息增益；
- 数据完整性；
- 是否已有原始视觉；
- 与已选视觉是否重复；
- 页面容量；
- 在整份 deck 中是否重复。

未入选候选必须记录拒绝原因。不得静默截断列表。

### 5.8 PageSpec 与 Page Composer

职责：把语义页面转换成一个或多个可实际渲染的物理页面。

建议字段：

```json
{
  "page_id": "slide_013",
  "source_intent_id": "intent_007",
  "headline": "……",
  "claim": "……",
  "supporting_text": [],
  "selected_visuals": [],
  "layout_archetype": "visual_right_text_left",
  "content_budget": {},
  "continuation_index": 1
}
```

Page Composer 必须统一处理：

- 文字分页；
- 视觉分页；
- 表格拆页；
- 标题和正文容量；
- 稀疏页面；
- 图文相关性；
- 原图可读尺寸。

如果必需视觉超过页面预算，必须拆成具有独立 purpose 的续页，而不是：

- 创建六图布局；
- 自动丢弃视觉；
- 把所有视觉缩小后塞入一页；
- 仅复制相同正文生成多页。

## 6. LLM 使用边界

### 6.1 必须使用 LLM 的任务

LLM 适合：

- 识别研报段落的语义角色；
- 提取忠实的 claim 和 supporting points；
- 判断候选是否支持当前 slide claim；
- 判断图表相对于文字是否有信息增益；
- 在 text/KPI/table/chart/source figure 之间提出编辑建议；
- 对候选排序和解释拒绝理由；
- 为拆页后的页面生成聚焦 headline。

### 6.2 禁止交给 LLM 的任务

LLM 不得：

- 修改 Numeric Fact 的 value、unit、period、source locator；
- 自行补齐缺失数字或单位；
- 直接输出最终 chart values/categories/series；
- 把不同 measure kind 合并为同一序列；
- 在没有原文支持时计算并写入派生指标；
- 决定最终对象坐标；
- 绕过页面预算和 Layout Compiler。

### 6.3 推荐调用方式

以页面为单位批量判断候选，不要每个候选单独调用一次模型。

模型输入应为：

- 当前 slide claim；
- supporting points；
- 规则预筛选后的有限候选；
- 规范化且只读的 fact 摘要；
- 原始视觉资产摘要；
- 页面视觉预算；
- 相邻页已选视觉摘要。

模型输出必须符合严格 JSON Schema，只能引用 `candidate_id` 和 `fact_id`。

模型接受某候选后，确定性 Validator 必须再次检查数据和页面约束。

## 7. 图表准入规则

### 7.1 通用硬规则

任何新生成图表必须满足：

- 至少一个明确的业务问题或比较关系；
- 所有数据点属于兼容 MetricGroup；
- 所有数据点可回查到 fact ID；
- 标签、时期和单位明确；
- 与本页 claim 直接相关；
- 相比一句话、KPI 或表格具有更高信息增益；
- 不与本页或相邻页视觉重复；
- 当前 Renderer 支持该图表类型和数据规模。

### 7.2 折线图

默认要求：

- 至少 4 个有序时期；
- 同一 metric、measure kind、unit family 和 scope；
- 不允许重复时期；
- 历史和预测边界必须显式标记。

只有 2–3 个时期时默认拒绝折线图，优先：

- 保留文字；
- KPI；
- 首尾对比卡；
- 在存在显著拐点且有明确编辑理由时使用柱状图。

### 7.3 柱状图与条形图

默认要求：

- 3–8 个具有明确标签的可比较类别；
- 类别属于同一指标口径；
- 类别名称在当前槽位可读；
- 不把时间序列机械改成分类图来规避折线图规则。

### 7.4 饼图

默认要求：

- 3–6 个部分；
- 全部为非负 share；
- 合计在允许误差内约等于 100%；
- 不存在“其他”占比过大导致图表失去解释力的情况。

### 7.5 表格

优先使用表格的场景：

- 需要精确读取多个指标；
- 同时包含水平值、增长率、利润率等不同 measure kind；
- 盈利预测与估值数据需要保留完整口径；
- 图表会掩盖重要数值细节。

表格超过布局容量时必须拆分、简化或进入附录，不得把全部字体缩小到不可读。

### 7.6 绝对值与增长率

以下文本：

```text
2024 年营业收入为 100 亿元，2025 年同比增长 2.5%。
```

必须解析为两个不同事实：

- `revenue / level / currency`；
- `revenue_yoy / growth_rate / percentage`。

禁止把 `100` 和 `2.5%` 放入同一 series、同一数值列或同一单轴图表。

首期不支持 secondary axis 时，应选择：

- 文字；
- KPI + 增速注释；
- 分离的小型视觉；
- 表格；
- 或直接拒绝图表化。

## 8. 原始图表处理要求

原始 figure/table 应组织为资产包：

```text
asset
caption
source note
nearby explanation
section reference
editorial takeaway
```

实现要求：

- 不再强制每张 figure 单独占页。
- 原图应与相关解读同页，除非该图本身信息密度足够高。
- 必须检查裁切区域是否包含无关页眉、页脚和大面积空白。
- 必须检查放入目标槽位后的有效像素和内部文字可读性。
- 原图与新生成图表达同一结论时，默认优先保留更可信、更清楚的一个。
- 不要求迁移研报中的全部 figure，只迁移对演示主线重要的视觉。
- 多张原图必须保持原始顺序，但允许穿插相应解读页。

## 9. 页面布局与质量保障

### 9.1 静态布局检查

每个 PageSpec 在 Visualization Generator 之前必须完成 Layout Preflight：

- 存在至少一个兼容 layout；
- 视觉数量不超过预算；
- 视觉类型被 slot 支持；
- 字符、bullet、表格行列和图表类别不超过初步容量；
- 必需内容都有目标区域；
- 不存在明显的内容缺失。

### 9.2 真实文本测量

不得仅用 `len(text)` 作为最终容量依据。

必须逐步引入：

- 按实际字体与字号估算中英文宽度；
- 真实区域宽高下的换行估算；
- 标题、正文、表格单元格的行数限制；
- 图表轴标签和图例的显示预算。

PowerPoint 的自动 fit 只能作为最后防护，不能把文字缩小到低于最小字号。

建议最小字号：

- 正文：14pt；
- 标题：20pt；
- 表格与图表标签：9–10pt；
- 来源说明：8pt。

具体数值应进入 Page Policy/Template Profile，不应散落在 Renderer 常量中。

### 9.3 稀疏页面检查

普通内容页不应只有一句短句或一个很小的视觉对象。

但不得用机械填充解决稀疏问题。处理顺序应为：

1. 判断该页是否应该与前后页合并；
2. 判断原图是否应放大为主视觉；
3. 增加有证据支持的短 takeaway；
4. 更换适合低密度内容的布局；
5. 若没有独立表达价值，删除该页。

章节页、封面和结束页可以有意留白。

### 9.4 图文相关性检查

同页视觉必须同时满足：

- 视觉 evidence 与 slide evidence 有确定性交集；
- Visual Decision 明确标记 `supports_claim=true`；
- 图表 metric 与 claim 中讨论的实体、指标或业务范围兼容；
- 不允许仅因位于同一章节就视为相关。

### 9.5 Render QA

PPTX 保存成功不等于质量通过。

正式流水线必须能够将最终 PPTX 渲染为页面图像并执行：

- 页面尺寸与对象 bounds 检查；
- 对象重叠检查；
- 文本裁切和最小字号检查；
- 表格单元格可读性检查；
- 图片有效分辨率检查；
- 图表标签、图例和轴文字检查；
- 页面稀疏或过密检查；
- 全 deck 风格一致性和重复页面检查。

失败时优先局部修复单页，最多进行有限次数的重排；超过次数后必须失败并输出诊断，不得无限重试。

## 10. 流水线与诊断产物

建议工作目录：

```text
run/
├── source_bundle/
├── report_map.json
├── deck_storyboard.json
├── candidate_pool.json
├── metric_facts.json
├── visual_decisions.json
├── visual_portfolio.json
├── page_specs.json
├── visualizations/
├── compiled_layout_plan.json
├── render_qa.json
├── rendered_slides/
├── presentation.pptx
└── run_manifest.json
```

失败运行必须至少保留：

```text
failure.json
last_successful_stage
relevant stage outputs
slide/candidate IDs
reason codes
```

最终发布仍应保持原子性：只有所有 P0 质量门通过后才发布 `presentation.pptx`。

可以通过配置控制是否保留完整失败工作区，但默认必须保留轻量诊断包。

## 11. 与现有模块的迁移关系

### 11.1 保留并演进

- `document_bundle/`：演进为统一事实输入层。
- `document_intelligence/`：保留确定性索引职责。
- `visualization_generator/numeric_facts.py`：扩展 typed metric 语义。
- `visualization_generator/verification.py`：继续作为事实准入防线。
- `visualization_generator/audit.py`：继续执行数值审计。
- `ppt_engine/compiler.py`：继续作为最终确定性布局防线。
- `ppt_engine/renderer.py`：继续只执行已编译操作。
- Template Profile、Manifest、Compiled Plan：保留并升级版本。

### 11.2 拆分或重构

- `outline_generator/`：拆出 Report Understanding 与 Deck Storyboard。
- `visualization_generator/candidate_detection.py`：改为 CandidatePoolBuilder。
- `visualization_generator/planning.py`：拆成语义分组、LLM 编辑判断和 Portfolio Selector。
- `ppt_engine/text_pagination.py`：升级为统一 Page Composer，不再只处理文字。
- `pipeline_runner/`：增加阶段产物、失败诊断和 Render QA。

### 11.3 逐步淘汰

- Legacy Layout Map 运行时推断链路；
- 未版本化或职责混杂的中间 JSON；
- 仅依靠 Prompt 保证页面容量的规则；
- 视觉候选自动全部生成的行为；
- 对 figure 一律独立成页的硬规则。

## 12. MemSlides 可借鉴范围

参考项目：<https://github.com/huohua325/Memslides>

建议借鉴：

- 持久化工作区与明确的阶段产物；
- Research、Template Planning、Deck Design 职责分离；
- 每页执行 brief；
- 资产 manifest；
- 渲染后局部修订；
- 不因修改一页而重新生成整份 deck。

首期不照搬：

- 长期用户画像；
- 通用网络研究；
- 自由多 Agent 工具循环；
- 与本项目无关的个性化记忆体系。

## 13. 实施阶段与交付要求

### Phase 0：基线和安全闸门

必须完成：

- 建立至少 10 份真实研报的 deck-level 基线集。
- Candidate Locator 默认进入 shadow mode。
- 普通页视觉硬上限设为 2，推荐为 1。
- 增加折线图最少时期、mixed metric、mixed measure kind 规则。
- 增加失败诊断包。
- 增加生成前 Layout Preflight。

交付物：

- 新的测试集说明；
- 规则配置；
- 失败报告 Schema；
- 不改变最终 Renderer 的安全改动。

### Phase 1：ReportMap 与 typed metric

必须完成：

- ReportMap Schema 与生成器；
- 内容分类与默认排除项；
- typed metric fact；
- MetricGroup Validator；
- PDF/Markdown/TXT 同内容语义一致性测试。

### Phase 2：Storyboard 与 Visual Decision

必须完成：

- DeckStoryboard Schema；
- LLM 编辑判断接口；
- 严格输出 Schema；
- Visual Decision Validator；
- Visual Portfolio Selector；
- 候选拒绝原因审计。

### Phase 3：Page Composer

必须完成：

- Page Policy；
- 视觉预算；
- 文字与视觉联合分页；
- 表格拆页；
- 稀疏页面处理；
- 原始图与解读的组合页面。

### Phase 4：Render QA 与局部修复

必须完成：

- PPTX 页面渲染；
- 静态和像素级 QA 报告；
- montage；
- 有限次数的单页重排；
- CI 中保留失败渲染产物。

### Phase 5：旧链路清理

必须完成：

- 更新 README 和长期架构文档；
- Schema 版本迁移说明；
- Legacy 入口弃用警告；
- 移除不再使用的兼容代码；
- 全量回归。

## 14. 测试与验收标准

### 14.1 输入层

- PDF、Markdown、TXT 均可生成统一 Source Model。
- 同一内容的三种格式在章节顺序和核心文本上保持一致。
- Markdown 图片正确物化或明确拒绝。
- 不伪造页码、bbox 或不存在的资产。

### 14.2 Storyboard

- 核心章节顺序保持单调。
- 不出现分析师证书、联系方式和免责声明主体页。
- 每页只有一个 claim。
- 无重复 purpose 的页面。
- 不为凑页数生成内容。

### 14.3 可视化

必须覆盖以下负样本：

- 单一数值；
- 两三个低信息量时间点；
- 收入与增长率混合；
- 收入与利润混合但单位相同；
- 日期、证券代码、页码；
- 风险假设数字；
- 不同业务范围的数据；
- 历史与预测口径不明；
- 与 slide claim 无关的同章节数据；
- 与已有原始 figure 重复。

建议目标：

- Candidate Precision ≥ 90%；
- Candidate Recall ≥ 80%；
- 正确拒绝率 ≥ 90%；
- 编造数值为 0；
- mixed metric/unit 错误为 0。

对本项目，宁可少生成一个非必要图表，也不能生成语义错误的图表。

### 14.4 页面编排

- 任意最终物理页视觉数不超过 Policy 上限。
- 每页在生成视觉前可找到兼容布局。
- 表格超出容量时确定性拆页或失败。
- 不静默丢失 required 内容。
- 不依赖低于最小字号的自动缩放通过验收。

### 14.5 Render QA

- 对象越界数为 0。
- 非设计性重叠数为 0。
- 文字裁切数为 0。
- 正文字号低于 Policy 下限数为 0。
- 表格不可读单元格数为 0。
- 图片路径逃逸和缺失数为 0。
- 所有失败页均有 page ID 和 reason code。

### 14.6 人工 deck-level 验收

每个里程碑至少对真实研报检查：

- 是否保持研报主线；
- 是否选择了真正重要的内容；
- 是否存在机械复制的长标题；
- 是否存在图文不相关；
- 是否存在无意义图表；
- 是否存在重复页；
- 是否存在异常空洞或过度拥挤；
- 是否能在不阅读原文的情况下讲清主要投资逻辑。

## 15. Pull Request 实施检查清单

每个涉及主链路的 PR 必须回答：

- 修改了哪个正式契约？
- 是否需要 Schema 版本升级？
- 是否改变来源顺序或 evidence 绑定？
- 是否改变 Candidate、Decision 或 Selection 的职责？
- 是否可能新增错误图表？
- 是否可能静默丢弃内容？
- 是否影响页面视觉预算？
- 是否新增或改变最小字号、表格容量？
- 是否增加了负样本测试？
- 是否生成 Render QA 产物？
- 失败时是否仍可诊断？
- README 和长期架构文档是否需要同步？

## 16. 最终架构不变量

以下不变量必须贯穿全链路：

```text
每个事实都有来源；
每个视觉都服务于页面 claim；
每个图表只包含语义兼容的数据；
每个页面都符合内容和视觉预算；
每个物理页面都有兼容布局；
每个最终页面在真实渲染后可读；
每个自动决策都有原因；
每个失败都可诊断；
只有通过全部 P0 门禁的 PPTX 才能发布。
```

后续开发应以这些不变量为优先级最高的实施标准，而不是以现有模块边界或历史 Schema 的兼容性为最高目标。

# Week 3 可视化内容定位与抽取执行计划

## 1. 本周结论

第三周不重建现有 Visualization Schema、Layout Compiler 或 PPT Renderer。新增工作的核心是补齐：

```text
DocumentBundle 事实
        ↓
可视化候选主动定位
        ↓
数值事实登记与来源定位
        ↓
结构化映射（规则 + 可选 LLM）
        ↓
确定性校验
        ↓
现有 Visualization JSON
```

本周交付目标是一个可评估的 MVP：给定 Slide Outline 和 DocumentBundle，系统能够主动发现
可视化候选，生成可追溯的 chart/table 数据；任何输出数值都能回查到原始 block/table，
并能进入现有编译与 PPT 渲染链路。

## 2. 必须保持的架构约束

1. `DocumentBundle document.json + assets/` 是唯一事实来源。
2. `schemas/visualization.schema.json` 继续作为正式 Visualization 输出契约，不建立平行 Schema。
3. 候选定位结果和 LLM 映射结果属于运行时中间对象，不直接进入 Renderer。
4. LLM 可以判断语义、指标关系和展示方式，但不得成为数值事实来源。
5. 输出数值必须由确定性代码从已验证的 block 或 complete table 中复制、解析和归一化。
6. 每个 Visualization 必须保留 `sources: [{kind, id}]`；无法定位来源时拒绝生成。
7. Renderer 只消费校验通过的 Visualization，不回读 DocumentBundle，也不推断缺失数据。
8. 图表优先复用现有 `python-pptx` 原生渲染器，不新增 matplotlib 平行主链路。

## 3. 调整后的模块框架

### 3.1 数据流

```text
Slide Outline ───────────────────────────────────────────────┐
                                                            │
Document Intelligence Snapshot                              │
        ↓                                                   │
Candidate Locator（高召回规则、表格特征、数字模式）          │
        ↓                                                   │
VisualCandidate（无 values）                                │
        ↓                                                   │
Numeric Fact Ledger（事实 ID、原值、归一值、单位、span）     │
        ↓                                                   │
Structure Mapper（规则优先，LLM 可选且只能引用 fact_id）     │
        ↓                                                   │
Extraction Proposal（引用 fact_id，不携带自由生成的数值）   │
        ↓                                                   │
Deterministic Verifier / Assembler                          │
        ↓                                                   │
Visualization JSON ─────────────────────────────────────────┤
                                                            ↓
Visualization Manifest → Layout Compiler → Compiled Plan → PPTX
```

### 3.2 候选定位模式

生产路径采用 slide-scoped 模式：

1. 优先扫描该页 `evidence_refs` 指向的 block/table；
2. 证据不足时只允许扩展到同一 `section_ref` 的有限上下文；
3. 禁止无约束地从全篇搜索数据后绑定到当前页面；
4. 合并 Outline 已给出的 `visual_candidates` 与规则主动发现的候选；
5. 按 evidence、指标和展示意图去重。

评估工具另提供 corpus-scan 模式，逐个扫描标注 evidence unit，用于计算定位准确率和召回率。

### 3.3 建议的内部对象

以下对象用于 Python 内部接口，不作为新的长期 JSON 标准。

```python
@dataclass(frozen=True)
class VisualCandidate:
    candidate_id: str
    slide_id: str | None
    visual_type: str             # chart | table
    chart_intent: str | None     # trend | comparison | composition
    evidence_refs: tuple[tuple[str, str], ...]
    trigger_ids: tuple[str, ...] # 命中的规则编号
    score: float
    excerpt: str                 # 仅用于审计和评估


@dataclass(frozen=True)
class NumericFact:
    fact_id: str
    source_kind: str
    source_id: str
    raw_value: str
    normalized_value: Decimal
    unit: str
    label: str | None
    period: str | None
    start: int | None
    end: int | None


@dataclass(frozen=True)
class ExtractionProposal:
    candidate_id: str
    chart_type: str
    title: str
    unit: str
    category_labels: tuple[str, ...]
    series: tuple[dict, ...]     # 数据点只能引用 fact_id
```

Verifier 根据 `fact_id` 从 Numeric Fact Ledger 取回真实数值，检查单位、长度和来源后组装现有
Visualization JSON。Proposal 中出现未知 fact、单位冲突或无法一一对应的系列时，必须拒绝输出。

## 4. 候选判定规则框架

### 4.1 正向特征

- 关键词：同比、环比、增长率、增速、CAGR、毛利率、净利率、市占率、占比、营收、利润等；
- 至少两个可比较数字，并存在年份、季度、分类或系列标签；
- complete table 中存在一个标签列和至少一个可解析数值列；
- 时间序列、分类比较、构成占比等明确关系；
- 数值和标签位于同一 block/table，或有可验证的题注/表头关系。

关键词只增加候选分数，不能单独决定生成图表。

### 4.2 排除规则

- 只有一个孤立数字；
- 仅包含日期、页码、股票代码或报告编号；
- 只有评级、目标价等单点信息且不存在比较关系；
- 数字属于不同指标或不同单位，无法形成同一系列；
- OCR/解析残缺，表格状态不是 `complete`；
- 百分比不构成同一分母下的组成关系；
- 缺失标签，无法判断数字对应的时期或分类。

### 4.3 图表类型确定

- 时间或季度序列：`line`；
- 多分类横向比较：`column` 或 `bar`；
- 同一总体的非负构成，分类不超过 6 项且合计约为 100%：`pie`；
- 多指标、密集数据或需要精确查阅：`table`；
- 无法可靠确定：拒绝生成或降级为 table，不猜测。

## 5. 代码落点

计划新增：

```text
visualization_generator/
├── candidate_detection.py      候选规则、评分、去重
├── numeric_facts.py            数字、单位、期间、span 的确定性解析
├── extraction.py               规则映射与可选 LLM 映射适配器
└── verification.py             fact 引用、单位、系列及来源校验

tools/
└── evaluate_visualization_extraction.py

data/evaluation/visualization/
├── README.md                   标注指南
└── week3_gold.jsonl            20–30 个初评 evidence unit

tests/unit/
├── test_candidate_detection.py
├── test_numeric_facts.py
├── test_visualization_extraction.py
└── test_visualization_verification.py
```

计划修改：

- `visualization_generator/planning.py`：合并 Outline 建议与主动发现候选；
- `visualization_generator/generate_visualizations.py`：接入 locator、extractor、verifier；
- `main.py`：在全部模块稳定后增加单命令 Pipeline；
- `tests/integration/test_visualization_pipeline.py`：增加候选定位到 PPTX 的回归路径。

暂不修改：

- `schemas/document_bundle.schema.json`；
- `schemas/slide_outline.schema.json` 的正式页面语义边界；
- `schemas/visualization.schema.json`，除非实现中发现无法表达且有测试证明的必要字段；
- `ppt_engine/compiler.py` 的输入职责。

## 6. 任务拆分与依赖

工时按净开发时间估算，不含等待外部模型或接口的时间。

| ID | 任务 | 负责人 | 估算 | 依赖 | 完成定义 |
|---|---|---|---:|---|---|
| T3.0 | 冻结接口、标注口径和验收指标 | 共同 | 2h | T2.6 | 本文评审通过，正式 Schema 不重复 |
| T3.1 | Candidate Locator | 学生A | 6h | T3.0 | 可扫描 block/table，输出带 evidence 和 reason 的候选 |
| T3.2a | Numeric Fact Ledger | 学生A | 5h | T3.0 | 数字、单位、期间、span 可稳定解析并测试 |
| T3.2b | 结构映射与确定性校验 | 学生A | 7h | T3.1,T3.2a | 仅通过 fact_id 组装 Visualization，未知事实被拒绝 |
| T3.3 | 标注集与评估脚本 | 共同 | 6h | T3.0，可与开发并行 | 20–30 条 gold + 指标报告 |
| T3.4 | 原生图表能力与样式验收 | 学生B | 4h | T3.0 | line/column/bar/pie 样例及对象级测试 |
| T3.5 | 原生表格样式与容量验收 | 学生B | 4h | T3.0 | 表头、列宽、行列上限和溢出策略明确 |
| T3.6 | 端到端联调与数值审计 | 共同 | 4h | T3.2b,T3.3,T3.4,T3.5 | 3 个片段无人工改数并生成 PPTX |
| T3.7 | 单命令 Pipeline 与回归 | 共同 | 5h | T3.6 | 单命令运行、非零失败码、产物清单和回归测试 |
| T3.8 | 评估报告和交付说明 | 共同 | 3h | T3.7 | 报告包含计数、指标、失败案例和遗留问题 |

总计约 46 人时；两人并行时一周可完成，关键路径约 27 小时。

## 7. 每日安排

### Day 1：冻结边界并启动评估

- 共同评审本文、冻结 Visualization 输出契约；
- 制定标注指南并选择至少 3 份研报来源；
- 学生A实现候选规则框架和 reason code；
- 学生B对现有 chart/table Renderer 建立基线截图与对象级测试。

检查点：能对一个 DocumentBundle 打印候选、证据 ID、命中规则和分数。

### Day 2：候选定位与事实解析

- 完成 block/table 候选定位、去重和负样本排除；
- 完成 Numeric Fact Ledger 的数字、百分比、金额、年份和单位解析；
- 两人交叉标注第一批样本，解决标注分歧。

检查点：定位脚本可在 gold 样本上输出第一版 Precision/Recall。

### Day 3：结构映射与防幻觉校验

- 实现规则结构映射；
- 接入可选 LLM adapter，限制其只能引用 fact_id；
- 实现来源、单位、系列长度、图表类型和 Schema 校验；
- 完成图表、表格样式与容量边界。

检查点：人为注入一个不存在的 fact_id 时，Pipeline 必须失败而不是生成图表。

### Day 4：评估、调参与集成

- 完成 20–30 条初评集；
- 根据错误类型调整规则，不直接针对样本内容写特例；
- 接入 Manifest、Compiler 和 Renderer；
- 对 2–3 个真实片段逐项核对原文数字与图表数据。

检查点：Schema、来源覆盖率和零编造门槛全部通过。

### Day 5：单命令、回归与报告

- 增加统一 Pipeline CLI；
- 跑单元测试、集成测试和三个固定样例；
- 输出评估报告、失败案例和下一轮扩展清单；
- 冻结本周演示产物，记录命令、输入 hash 和输出路径。

检查点：新环境按文档执行单命令可复现 PPTX 和评估结果。

## 8. 评估集与指标

### 8.1 初评集组成

初评集最少 30 个 evidence unit，建议：

- 15–18 个应生成可视化的正样本；
- 12–15 个不应生成的负样本；
- 至少覆盖 3 份不同研报；
- 同时包含 paragraph 和 complete table；
- 覆盖趋势、比较、构成、多系列、单位混合、缺失值和干扰数字。

每条标注至少包含：

```text
sample_id
document_id
source kind/id
原始文本或表格定位
是否可视化
期望 visual_type / chart_intent
title / unit / categories / series
每个数值的原文 raw value
拒绝原因（负样本）
```

标注集必须在规则调优前冻结一个版本。若后续修正 gold，需要在评估报告中记录原因。

### 8.2 指标定义

候选定位：

- Precision = 正确候选数 / 全部预测候选数；
- Recall = 找到的 gold 候选数 / 全部 gold 候选数；
- F1 = Precision 与 Recall 的调和平均；
- 匹配键以 evidence kind/id + visual intent 为主，不能只按文本模糊相似度匹配。

结构化抽取：

- 图表类型准确率；
- title、unit、categories、series name 字段准确率；
- 数值单元格 Precision、Recall、Exact Match；
- 完整对象准确率：所有必填字段和数值全部正确的对象比例；
- 正确拒绝率：证据不足时未生成错误 Visualization 的比例。

安全与工程门槛：

- Visualization Schema 通过率 = 100%；
- `sources` 覆盖率 = 100%；
- 无来源数值数量 = 0；
- 编造数值数量 = 0；
- 端到端固定样例成功率 = 100%。

### 8.3 MVP 验收阈值

小样本初评采用以下门槛，同时报告分子和分母，避免只报告百分比：

| 指标 | 最低门槛 | 目标 |
|---|---:|---:|
| 候选定位 Precision | 70% | 80% |
| 候选定位 Recall | 80% | 90% |
| 数值单元格 Exact Match | 90% | 95% |
| 完整对象准确率 | 70% | 85% |
| Schema 通过率 | 100% | 100% |
| 来源覆盖率 | 100% | 100% |
| 编造数值 | 0 | 0 |

20–30 条结果只能称为初评。若需要对外声明模块稳定，应在后续扩展到至少 100 个 evidence unit，
并按研报而不是按段落切分训练/调试集与测试集。

## 9. T3.6 固定联调场景

至少固定三个场景：

1. paragraph 时间序列：两个以上年份、同一指标、同一单位，生成 line；
2. complete table 分类比较：多个分类、一个或多个系列，生成 column/bar 或 table；
3. 构成占比：同一总体、非负值、合计约 100%，生成 pie。

另增加两个必须拒绝的回归用例：

1. 只有一个百分比或孤立金额；
2. 两组数字单位不同且无法确定换算关系。

每个成功场景保存：

- 输入 evidence kind/id；
- Numeric Fact Ledger；
- 最终 Visualization JSON；
- Manifest 和 Compiled Layout Plan；
- PPTX；
- 原文数值与输出数值核对表。

## 10. 单命令 Pipeline 目标

最终命令名称在实现时以 `main.py` 现有风格确定，预期能力为：

```powershell
python main.py run-pipeline `
  INPUT_DOCUMENT `
  --template-profile TEMPLATE_PROFILE `
  --output-dir OUTPUT_DIRECTORY
```

输出目录至少包含：

```text
document_bundle/
slide_outline.json
visualizations/
├── visualization_manifest.json
└── *.json
compiled_layout_plan.json
presentation.pptx
run_manifest.json
```

`run_manifest.json` 记录输入、正式 Schema、Outline、Visualization Manifest、模板和最终计划的 hash。
任何 P0 校验失败时命令返回非零状态，不生成或不宣称生成了有效 PPTX。

## 11. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 微调模型尚未可用 | 阻塞 LLM 映射 | 保留规则基线和可替换 adapter；测试使用 mock |
| 关键词召回高但误报多 | Precision 下降 | 增加“至少两个可比较数字”和负样本排除 |
| LLM 改写或编造数字 | 数值失真 | LLM 只返回 fact_id；Verifier 确定性取值 |
| 单位和口径混合 | 错误系列 | 单位一致性检查；无法证明换算时拒绝 |
| 20–30 条样本过小 | 结论不稳定 | 本周只称初评，后续扩到 100+ |
| 与 partner 修改冲突 | 延迟集成 | 核心新增文件集中在 `visualization_generator/`，Day 4 前不改 `main.py` |
| 重复建设 Renderer | 时间浪费 | 复用现有原生 chart/table，只补样式和边界测试 |
| 为提高指标写样本特例 | 评估失真 | 冻结 gold；规则必须是通用 reason code |

## 12. 本周 Definition of Done

只有同时满足以下条件，第三周才算完成：

1. 候选定位不依赖人工预先填写完整 `visual_candidates`；
2. 每个输出数值都能由 fact_id 回查到 DocumentBundle 原始证据；
3. 正式输出通过现有 Visualization Schema；
4. 初评集、评估脚本和指标报告可复现；
5. 三个正向场景和两个拒绝场景通过；
6. 生成的 chart/table 是 PPT 中可检查的原生对象；
7. 单命令能跑通定位、抽取、编译和渲染；
8. 全量测试通过，且不破坏现有 Outline、Manifest、Compiler 和 Renderer 契约。

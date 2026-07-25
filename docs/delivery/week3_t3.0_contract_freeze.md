# Week 3 T3.0 接口与验收口径冻结

- 状态：**已冻结**
- 日期：2026-07-25
- 适用范围：T3.1–T3.8

## 1. 开工基线

- 使用系统 Python 3.12 执行 `python -m pytest -q`：`265 passed in 20.53s`。
- 仓库 `.venv` 记录了已经失效且包含乱码用户名的 Python 3.12 绝对路径，不能作为本周基线解释器。
- 开工时工作区已有 Week 2 未提交修改；Week 3 文件应集中在
  `visualization_generator/`、`data/evaluation/visualization/`、对应测试和文档中，
  避免覆盖既有修改。

## 2. 冻结边界

1. `DocumentBundle document.json + assets/` 是唯一数值事实来源。
2. 正式输出继续使用 `schemas/visualization.schema.json`，不建立平行产品 Schema。
3. `VisualCandidate`、`NumericFact` 和 `ExtractionProposal` 仅为 Python 运行时对象。
4. Renderer 只读取校验通过的 Visualization，不读取 DocumentBundle，不补数或换算。
5. Week 3 不改变 Layout Compiler、Renderer 和 Slide Outline 的职责。
6. `sources` 对所有新生成的 chart/table/image 都是应用层 P0 必填项。当前正式 Schema 为保持
   兼容没有把 chart/table 的 `sources` 列入 `required`；Verifier、Generator 和测试必须执行
   更严格的 100% 来源覆盖策略。

运行时契约由 `visualization_generator/contracts.py` 定义。修改其字段、枚举值或定位语义视为
接口变更，必须同步更新本文、标注指南和契约测试。

## 3. 运行时对象

### 3.1 VisualCandidate

- 只允许 `chart | table`，不得携带 categories、series、values、rows 或 columns。
- `evidence_refs` 至少包含一个存在的 `block` 或 `table`。
- `trigger_ids` 只能使用冻结 reason code。
- `score` 范围为 `[0, 1]`；excerpt 只用于审计和评估，不进入正式 Visualization。
- slide-scoped 模式填写 `slide_id`；corpus-scan 评估模式允许为 `None`。

### 3.2 NumericFact

- `normalized_value` 使用 `Decimal`，不得使用二进制浮点作为事实账本的规范值。
- block 数值必须记录原文字符区间 `[start, end)`。
- complete table 数值必须记录从零开始的 `row_index` 和 `column_index`。
- 两种定位方式互斥；缺少精确定位时不得登记为 fact。
- `fact_id` 必须稳定且以 `fact_` 开头。T3.2a 采用规范化来源键和定位信息生成确定性 ID；
  相同输入重复运行必须产生相同 ID。

### 3.3 ExtractionProposal

- Week 3 MVP chart type 仅限 `line | column | bar | pie`。
- 每个数据点只能是 `fact_id`；Proposal 不存在自由数值字段。
- 每个 series 的 fact 数量必须与 category 数量一致。
- complete table 使用确定性整表转换，不通过 LLM Proposal 重建单元格。
- Verifier 必须解析所有 fact 引用后才组装现有 Visualization JSON。

## 4. Reason code

正向触发：

| Code | 含义 |
|---|---|
| `candidate.outline_suggestion` | 合并 Outline 已给出的语义建议 |
| `candidate.complete_table` | complete table 具备标签列和数值列 |
| `candidate.comparable_numbers` | 至少两个可比较数值 |
| `candidate.time_series` | 明确时间/季度序列 |
| `candidate.category_comparison` | 明确分类比较 |
| `candidate.composition` | 同一总体、非负且合计约 100% |
| `candidate.metric_keyword` | 命中通用指标关键词；不得单独决定生成 |
| `candidate.labels_colocated` | 数值与标签同证据或存在可验证表头关系 |

拒绝原因：

| Code | 含义 |
|---|---|
| `reject.single_number` | 只有一个孤立数字 |
| `reject.administrative_numbers_only` | 只有日期、页码、代码或报告编号 |
| `reject.single_point_signal` | 评级、目标价等无比较关系的单点信息 |
| `reject.mixed_metric_or_unit` | 指标或单位混合且无法证明换算关系 |
| `reject.incomplete_table` | 表格状态不是 complete |
| `reject.non_composition_percentages` | 百分比不属于同一总体 |
| `reject.missing_label` | 无法确定时期、分类或系列标签 |
| `reject.out_of_scope` | 超出 slide evidence/同 section 有限上下文 |

reason code 必须描述通用规则，不得包含报告名、公司名或样本 ID。

## 5. 定位与去重

生产模式严格按以下顺序取证：

1. 扫描 slide `evidence_refs`；
2. 证据不足时扩展至相同 `section_ref`；
3. 扩展只接受与当前指标/展示意图相关的 block 或 complete table；
4. 禁止无约束全篇搜索；
5. Outline suggestion 与主动发现结果按
   `(evidence_refs, visual_type, chart_intent, normalized metric label)` 去重。

corpus-scan 只用于评估，每个标注 evidence unit 独立运行，不代表生产路径允许全篇绑定。

## 6. 校验和拒绝策略

以下任一情况发生时拒绝该 Visualization，而不是猜测或生成部分可信结果：

- Proposal 引用未知 fact；
- fact 来源不存在或精确定位无法回查；
- 同一 series 单位冲突且没有确定性换算规则；
- categories 与 series 长度不一致；
- pie 存在负数、超过 6 项或无法证明属于同一总体；
- 输出缺少 `sources`；
- 正式 Visualization Schema 校验失败。

## 7. 评估口径

标注单位和 JSONL 字段见 `data/evaluation/visualization/README.md`。

- Candidate matching key：
  `source kind/id + visual_type + chart_intent`，不用文本模糊相似度替代。
- Precision、Recall、F1 必须同时报告分子和分母。
- 数值单元格 Exact Match 比较 Decimal 规范值、单位、标签/期间及来源定位。
- 完整对象准确要求必填字段和所有数值同时正确。
- P0 工程门槛：Schema 通过率 100%、sources 覆盖率 100%、无来源数值 0、编造数值 0。

MVP 最低阈值：

| 指标 | 最低门槛 | 目标 |
|---|---:|---:|
| Candidate Precision | 70% | 80% |
| Candidate Recall | 80% | 90% |
| 数值单元格 Exact Match | 90% | 95% |
| 完整对象准确率 | 70% | 85% |
| Schema 通过率 | 100% | 100% |
| sources 覆盖率 | 100% | 100% |
| 编造数值 | 0 | 0 |

## 8. T3.0 完成定义

- 现有测试基线已记录；
- 运行时接口、reason code、搜索边界、拒绝策略已冻结；
- 标注单位、匹配键和指标计算口径已冻结；
- 契约测试能够阻止自由数值进入 Proposal、不可定位 fact 和未知 reason code；
- 未新增正式产品 Schema，未修改 Renderer/Compiler 职责。

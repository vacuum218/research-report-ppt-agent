# Week 3 T3.2 数值事实、结构映射与校验交付记录

- 状态：**已实现**
- 日期：2026-07-25
- 范围：T3.2a Numeric Fact Ledger + T3.2b Structure Mapper / Verifier

## 1. Numeric Fact Ledger

`visualization_generator/numeric_facts.py` 从 DocumentBundle 构建只读事实账本：

- block 数值记录原始字符 `[start, end)`；
- complete table 数值记录零基 `row_index/column_index`；
- 规范值使用 `Decimal`；
- 单位不做未经证明的换算；
- 年份、年度范围、季度和 A/E 期间确定性归一；
- `fact_id` 由 source kind/id 和精确位置生成，重复运行稳定；
- incomplete/image-only table 不登记结构化数值事实。

账本提供 fact ID、source 和 table cell 三种只读索引。相同来源位置不能重复登记。

## 2. Structure Mapper

`visualization_generator/extraction.py` 提供规则优先映射：

- paragraph 时间序列、分类比较和百分比构成；
- complete table 的期间列、多行 series、分类列和构成列；
- 所有数据点均为 `ProposedSeries.fact_ids`；
- Proposal 不包含自由生成的 values；
- table 结构由确定性整表路径处理，不交给 LLM 重建。

可选 `LLMExtractionAdapter` 仅在规则映射失败后调用，输入为限定 evidence 内的 NumericFact，
输出仍必须是冻结的 `ExtractionProposal`。Adapter 不能切换 candidate_id；未知或越界 fact
由 Verifier 拒绝。公共 `generate_visualizations(..., llm_adapter=...)` 可显式注入 adapter。

## 3. Deterministic Verifier

`visualization_generator/verification.py` 在组装 Visualization JSON 前检查：

- candidate_id 与 plan 一致；
- 每个 fact_id 存在且只引用一次；
- fact 来源属于候选 evidence；
- series 和 categories 一一对应；
- fact 单位一致且与 Proposal unit 完全一致；
- pie 只有一个 series、最多 6 项、非负、单位为 `%` 且合计约 100%；
- chart/table 的 `sources` 覆盖率为 100%；
- 最终对象通过现有 `schemas/visualization.schema.json`。

complete table 的每个输出数值单元格都必须存在对应 fact。任何缺失都会拒绝整张结构化表格，
不会输出部分可信结果。

## 4. Generator 接入

有 evidence 的 chart/table 已改为：

```text
VisualizationPlan
  → Numeric Fact Ledger
  → fact-only ExtractionProposal / deterministic table copy
  → Verifier
  → Visualization JSON
```

旧版无 evidence Outline 暂时保留原只读兼容路径，避免破坏已交付样例；T3.1 主动候选和所有新
evidence-backed Outline 不会进入兼容路径。验证失败时 Generator 不产生 artifact，并返回
`verification_failed` issue。

## 5. 测试覆盖

- block Decimal、单位、期间、span 和年度范围；
- table cell 坐标、header unit、incomplete table 拒绝；
- ledger ID 与索引确定性；
- block/table 规则 Proposal 仅引用 fact_id；
- 可选 adapter 的调用边界和 candidate_id 限制；
- unknown fact、跨 evidence、单位冲突、非 100% pie 拒绝；
- complete table 数值逐格审计；
- 主动候选进入现有 Generator 后的数值和 sources 保持。

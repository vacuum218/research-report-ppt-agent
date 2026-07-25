# Week 3 T3.1 Candidate Locator 交付记录

- 状态：**已实现**
- 日期：2026-07-25
- 前置契约：T3.0

## 实现范围

`visualization_generator/candidate_detection.py` 提供两个入口：

- `locate_visual_candidates(slide, snapshot)`：生产使用的 slide-scoped 定位；
- `locate_corpus_candidates(snapshot)`：仅供离线评估的逐 evidence 扫描。

生产入口按以下边界工作：

1. 优先检查 slide 的 block/table `evidence_refs`；
2. block 关联的原生 table 视为直接证据；
3. 直接证据没有候选时，才扩展至相同 `section_ref` 或证据所属 section；
4. 同章节扩展最多检查 12 个 block 和 4 个 table；
5. slide 没有 evidence 和有效 section 时返回空结果，不搜索全篇；
6. title/section 页面和 `figure_page` 不主动发现 chart/table。

## 规则基线

block 候选要求至少两个可比较数值，并存在共同单位、期间或可验证标签关系。支持：

- 年份/季度序列 → `trend`；
- 同单位分类数值 → `comparison`；
- 2–6 个非负百分比且合计在 95%–105% → `composition`。

complete table 候选要求标签列和至少两个数值单元格。支持：

- 多个期间列 → `trend`；
- 标签行和少量数值列 → `comparison`；
- 同一百分比列合计约 100% → `composition`；
- 密集、多指标或混合列单位 → `table`。

关键词只增加分数。单个数字、混合单位 block、非 complete table、缺失标签和无作用域输入不会生成候选。

## 输出与合并

每个结果是 T3.0 冻结的 `VisualCandidate`：

- 稳定的 `cand_` ID；
- 原生 block/table evidence；
- 通用 trigger reason code；
- `[0, 1]` 分数；
- 仅用于审计的 excerpt；
- 不包含 values、categories、series、rows 或 columns。

`plan_visualizations()` 已合并主动发现结果。Outline 显式建议优先；它已覆盖的 evidence 不会被 Locator
重新解释成第二个视觉对象。没有 Outline 建议但存在合格的 slide-scoped evidence 时，Planning 会生成
主动候选对应的 data-free plan。

## 验证

专项测试覆盖：

- paragraph 时间序列和构成占比；
- 单个数字及混合单位拒绝；
- complete table 分类比较和单行多期间趋势；
- incomplete table 拒绝；
- 同章节扩展及跨章节隔离；
- 无作用域时禁止全篇搜索；
- corpus-scan 评估入口；
- Planning 主动发现和 Outline 优先合并；
- 主动候选进入现有确定性 Generator 并保留 `sources`。


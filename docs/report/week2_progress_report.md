# Research Report PPT Agent 第二周工作进展汇报

> 汇报日期：2026-07-20  
> 汇报范围：第二周文本结构化、语义大纲生成、模板化渲染与最小端到端集成

## 1. 项目目标与整体设计思路

本项目面向研究报告的自动演示文稿生成，目标是将 Markdown 或纯文本研报转换为结构清晰、来源可追溯、可继续编辑的 PowerPoint。当前阶段聚焦于验证一条可运行的最小工程链路，而非一次性解决复杂内容理解、通用自动排版和视觉设计问题。

当前代码实现的 Pipeline 为：

```text
Markdown / 纯文本研报
        ↓
文本结构解析
        ↓
Parsed Document JSON
        ↓
LLM 生成 Slide Outline JSON
        ↓
基于 visual_candidates 生成 Visualization JSON
        ↓
固定模板 Layout Mapping 与 Layout Resolver
        ↓
PPT Renderer
        ↓
可编辑 PPTX
```

各模块职责如下：

- `document_parser` 将标题、段落、列表、表格等非结构化文本转换为带 block ID、章节路径和原文位置的 Parsed Document。
- `outline_generator` 调用 DeepSeek，根据 Parsed Document 生成页面级语义大纲，并执行 Schema 与语义校验。
- `visualization_generator` 读取 Outline 中已有的 `visual_candidates`，从 Parsed Document 的表格或段落证据中生成 Chart/Table JSON。
- `ppt_engine.layout_resolver` 根据页面角色、业务类型、可视化类型和布局提示，从固定 Layout Map 中选择模板版式。
- `ppt_engine.renderer` 克隆对应模板页，填充文本、来源、页码、图表和表格，最终保存为 PPTX。

整体设计遵循“内容语义、可视化数据、模板布局、对象渲染”分层。这样可以在不改变 Outline 数据契约的前提下迭代模板和 Renderer，也避免把坐标、字体、颜色等展示属性写入内容 JSON。

## 2. 本周完成工作总结

本周工作覆盖计划中的 T2.1—T2.6。以下总结以当前仓库代码和验收产物为准；其中 T2.6 已完成分阶段端到端 Demo，但尚未实现最初计划中的单命令自动编排。

### T2.1 内容结构化：设计 Slide Outline JSON Schema

已完成 `schemas/slide_outline.schema.json` 及配套语义校验。主要字段包括：

- 页面标识与结构角色：`slide_id`、`page_role`、`slide_type`；
- 页面内容：`title`、`key_message`、`bullet_points`；
- 来源追踪：顶层 `sources` 与页面级 `source_refs`；
- 后续处理提示：可选 `layout_hint` 与 `visual_candidates`；
- 报告元数据：公司名称、股票代码、行业、报告日期等。

当前 Schema 将页面内容语义与 PPT 排版严格分离：Outline 不保存 `layout_id`、Shape 坐标、字体、颜色，也不保存图表的 `categories`、`series`、`values`、`columns` 或 `rows`。这一边界为后续 Visualization、Layout Resolver 和 Renderer 提供了稳定接口。

### T2.2 内容结构化：Markdown/纯文本解析器

已实现 `document_parser/parse_report.py`，支持 Markdown 和纯文本输入，当前具备：

- Markdown ATX/Setext 标题及纯文本编号标题识别；
- 段落、嵌套列表、引用块和代码块解析；
- Markdown 表格、列对齐与图片信息解析；
- 引用标记提取；
- block ID、父标题、章节路径和原文行号记录；
- 编码识别、解析 warning、统计信息及内部一致性检查。

输出为符合 `schemas/parsed_document.schema.json` 的 Parsed Document JSON。该结构将原始研报转换为可校验、可定位的 block 序列，既作为 LLM 大纲生成输入，也作为 Visualization 原文证据来源。

### T2.3 内容结构化：LLM 生成 Slide Outline

已实现 `outline_generator/generate_outline.py`。该模块以 Parsed Document JSON 为输入，结合 system prompt、few-shot 示例和 Slide Outline Schema 调用 DeepSeek，输出语义化 Slide Outline。

当前实现包括：

- 输入 Parsed Document Schema 校验与长文本压缩；
- few-shot Prompt 构造；
- DeepSeek OpenAI-compatible Chat Completions 调用；
- JSON 响应提取；
- 空响应、截断、非法 JSON、网络/API 错误处理；
- 对可恢复问题执行纠错重试；
- 输出 Schema、来源引用和 ID 语义校验；
- 仅在校验通过后原子写入正式 Outline。

`slide_type` 契约覆盖公司概况、行业分析、商业模式、核心竞争力、财务预测、估值分析、投资风险和总结等页面主题。LLM 的职责是理解研报并规划“每页讲什么”，不直接决定模板坐标或生成图表数值。

### T2.4 排版引擎：Outline JSON → PPT

已完成基于 `python-pptx` 的基础 Renderer，核心代码位于 `ppt_engine/renderer.py`、`slide_builder.py` 和 `visualization_renderer.py`。

当前能力包括：

- 校验 Outline、Visualization 和 Layout Map；
- 按解析出的 `template_slide` 克隆固定模板页；
- 保留模板背景、母版关系和已有 Shape；
- 填充封面、标题、核心观点、要点、来源和页码；
- 在模板槽位内生成可编辑图表和表格；
- 移除原始模板示例页并保存最终 PPTX。

基础图表渲染支持 line、column、bar、area 和 pie；表格与图表均为 PowerPoint 原生可编辑对象。该实现完成了结构化大纲到可编辑 PPT 的最小闭环，但尚不包含通用动态排版、完整溢出处理和高级图表美化。

### T2.5 排版引擎：固定模板与版式映射

本周参考 MemSlides 对模板复用和 Template Induction 的思路，完成了适用于当前固定模板的工程化实现，但尚未实现自动学习或归纳新模板。

已完成：

- `ppt_template_parser`：解析 PPTX 页面尺寸、母版、布局、Shape、样式和主题；
- `tools/inspect_template.py`：盘点模板页面、对象、图表、表格和坐标；
- `tools/build_layout_map.py`：构建语义字段到模板对象的映射；
- `templates/template_layout_map.json`：当前模板的运行时 Layout Map；
- `ppt_engine/layout_resolver.py`：校验 Layout Map 并选择 `layout_id`。

当前模板包含 16 个模板页，Layout Map 定义了 17 个语义 layout ID，其中部分语义布局复用同一模板页。Resolver 的实际选择顺序为：

1. 非正文页的 `page_role` 特殊规则；
2. 联合匹配 `slide_type`、视觉类型和 `layout_hint` 的语义可视化规则；
3. `slide_type_defaults`；
4. 全局 fallback，当前为 `executive_summary`。

由此形成三层关系：

```text
Slide Outline JSON：页面讲什么
        ↓
Template Layout Map / Resolver：使用哪个模板页、内容放在哪里
        ↓
python-pptx Renderer：创建并填充实际 PPT 对象
```

### T2.6 全流程集成

已使用真实研报 `data/reports/agent/002544_2025-10-28.md` 完成分阶段端到端 Demo：

```text
002544_2025-10-28.md
        ↓
Parsed Document JSON（82 blocks，0 warning）
        ↓
Slide Outline JSON（11 slides，5 visual_candidates）
        ↓
Visualization JSON（5 个成功产物）
        ↓
Layout Resolver + Renderer
        ↓
output/002544_final_with_visualization.pptx（11 slides）
```

## 4. 当前遇到的问题

### 深色背景下字体颜色适配不足

在部分深色模板页面中，自动填充后的文本可能保持接近黑色或对比度不足的字体颜色，影响可读性。这一问题不影响 PPTX 文件生成和打开，但会影响最终展示质量。
直接修改方案会影响现有：

- Slide Outline JSON结构
- Layout Resolver布局匹配
- 最终PPT生成效果

## 6. 本周成果总结

本周已完成：

- Parsed Document、Slide Outline、Visualization 三层数据契约及校验；
- Markdown/纯文本研报结构解析；
- 基于 DeepSeek 和 few-shot 的 Slide Outline 生成；
- `visual_candidates` 驱动的 Chart/Table 数据生成；
- 固定 PPT 模板解析、Layout Map 与 Layout Resolver；
- Outline、Visualization 与模板结合的可编辑 PPTX 渲染；
- 基于 `002544_2025-10-28.md` 的 11 页真实样例验证；
- 127 项自动化测试通过。

当前系统已经具备“Markdown 研报 → 结构化数据 → 语义大纲 → 可视化数据 → 固定模板可编辑 PPTX”的完整最小闭环。完成程度应理解为可运行的工程原型：核心数据流和模块边界已建立，但字体颜色适配、复杂自动布局、自动 Visualization Policy 和单命令编排仍未实现。

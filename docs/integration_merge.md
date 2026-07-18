# 本地功能合并说明

## 合并原则

本次以 `research-report-ppt-agent` 为目标代码库。目标仓库已有的
`schemas/slide_outline.schema.json` 和 `schemas/visualization.schema.json`
是跨模块接口基线，未被本地旧版 `financial_report_outline_schema.json`
覆盖。

本地旧版大纲把页面语义、图表数据和 `layout_id` 混在同一对象中；
目标仓库将它们拆为：

```text
Parsed Document
→ Slide Outline（页面讲什么）
→ Visualization（展示什么数据）
→ Layout Mapping（如何映射模板）
→ Renderer
```

因此，大纲生成器已适配目标 Slide Outline Schema：

- 删除对旧 `layout_id/content/sections` 结构的依赖；
- `visual_candidates` 只保留意图和来源，不包含数据序列；
- 模板 layout map 由独立工具维护；
- 生成完成后使用目标 Schema 和跨引用规则校验。

## 功能映射

| 本地功能 | 合并位置 | 处理方式 |
|---|---|---|
| Markdown/纯文本解析 | `document_parser/` | 完整迁移，并补充 Document Schema 校验测试 |
| DeepSeek 大纲生成 | `outline_generator/`、`prompts/` | 迁移后适配目标 Slide Outline Schema |
| 旧大纲校验器 | `tools/validate_outline.py` | 重写为目标 Schema + ID/来源交叉校验 |
| 通用 PPT 模板解析 | `ppt_template_parser/` | 保留 partner 公共 API，修复包导入、shape 返回和样式接入 |
| 模板对象盘点 | `tools/inspect_template.py` | 作为 layout-map 上游工具迁移 |
| Layout map 构建 | `tools/build_layout_map.py` | 独立于语义大纲保留 |
| 固定模板与映射 | `templates/` | 迁移模板、说明和 16 页预生成映射 |

新增的 `schemas/parsed_document.schema.json` 只定义此前缺失的上游
Document JSON，不改变或替代目标仓库已有的两个核心 Schema。

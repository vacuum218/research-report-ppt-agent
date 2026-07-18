# Week 2 T2.1–T2.3 及现阶段仓库 Partner 交付说明

## 1. 交付结论

Week 2 的 T2.1–T2.3 已完成开发、自动验证、真实模型调用和人工验收。
项目负责人于 `2026-07-19` 确认：

- T2.1 评审通过；
- T2.3 评审通过。

| 任务 | 交付内容 | 验收结论 |
|---|---|---|
| T2.1 | Slide Outline JSON Schema 评审闭环 | `Completed / Approved` |
| T2.2 | Markdown/纯文本解析器 | `Completed` |
| T2.3 | DeepSeek 大纲生成、校验、重试和真实样例 | `Completed / Approved` |

`research-report-ppt-agent` 中的现有 Schema 是本次交付和后续合并的权威契约。
本次工作未修改 `schemas/slide_outline.schema.json` 或
`schemas/visualization.schema.json`。

## 2. 现阶段仓库状态

项目目前处于前期开发阶段，正式实现直接保存在四个功能目录中，不额外维护
`src` 包或兼容包装层：

| 模块 | 状态 | 正式位置 |
|---|---|---|
| Markdown/纯文本解析 | 已完成 | `document_parser/` |
| DeepSeek 大纲生成 | 已完成 | `outline_generator/` |
| Outline/Visualization 校验 | 已完成 | `tools/` |
| PPT 模板解析与 Layout Map | 已完成 | `ppt_template_parser/`、`tools/` |
| Visualization Detector | 规划中 | 尚无运行时模块 |
| PPT Renderer | 规划中 | 尚无运行时模块 |

当前仓库整理包括：

- 继续使用 `requirements.txt` 管理依赖，通过 `python main.py <command>` 执行流程；
- 四个功能目录均保存完整实现，可以直接阅读、修改和独立运行；
- 文档按 architecture、specs、planning、quality、reviews、delivery 和 archive
  分类，入口为 `docs/README.md`；
- 研报和参考资料归入 `data/`，未删除或修改二进制内容；
- 测试按 unit、integration、fixtures 分类；
- 新增 GitHub Actions，目标环境为 Ubuntu Python 3.10/3.12 和
  Windows Python 3.11。

标准安装方式：

```powershell
python -m pip install -r requirements.txt
python main.py --help
```

## 3. T2.1–T2.3 实现

### T2.1：Schema 评审闭环

- 保持现有 Slide Outline 和 Visualization Schema 不变。
- 明确任务表字段映射：
  - `summary` → `slides[].key_message`
  - `source text` → 顶层 `sources` + 页面 `source_refs`
  - `visual candidates` → `slides[].visual_candidates`
- 复核字段完整性、完整研报表达能力、来源追溯、Schema/Visualization/Layout
  分层以及向后兼容性。
- 评审记录：
  `docs/reviews/T2.1_slide_outline_schema_review.md`。

### T2.2：解析器

- 维持现有实现，不重复开发。
- 支持 Markdown 和纯文本的标题、段落、列表、表格、引用、图片和代码块。
- 保留块 ID、原文行号、章节路径和引用。
- 输出遵循 `schemas/parsed_document.schema.json`。
- 专项测试位于 `tests/unit/test_report_parser.py`。

### T2.3：大纲生成链路

`outline_generator/generate_outline.py` 已补齐以下能力：

- 在调用 API 前校验 Parsed Document；
- 支持 `--max-attempts`，默认值为 2；
- 空内容、非法 JSON、输出截断和输出校验失败可携带纠错上下文重试；
- 429、5xx 和临时网络错误允许重试；
- 401、403 等配置错误不重试；
- 第二次请求包含原任务、上次输出和最多 20 条校验错误；
- 最终输出只有在 JSON、Schema 和语义校验全部通过后才写入正式文件；
- 校验失败时不保存不合格正式产物。

新增测试 `tests/unit/test_outline_generator.py`，覆盖：

- 正常响应；
- 空内容；
- 输出截断；
- 非法 JSON；
- HTTP 401、403、429 和 500；
- 临时网络错误；
- Schema 校验失败；
- 未声明来源引用；
- Parsed Document 输入不合法；
- 纠错重试和不可重试错误。

系统提示词还增加了预测口径约束：同一页不得混用不同机构、不同假设或
不同表格的预测口径，派生指标必须与该页采用的原始数字一致。

## 4. 正式验收样例

- 输入：
  `data/reports/agent/002544_2025-10-28.md`
- 输入 SHA-256：
  `c19c4aa488e4944af0027960d1ee48906a8a597f4f1d81043cb7780b7b9c6f65`
- 模型：`deepseek-v4-pro`
- Thinking：`enabled`
- Reasoning effort：`high`
- 解析结果：82 blocks，0 warning，0 omitted
- 正式输出：11 slides
- 输出文件：
  `examples/generated/002544_2025-10-28_slide_outline.json`
- 输出 SHA-256：
  `793dbb07a2b21f463d7352de9fbdfa6cb440f2c4a94c22be3b609bbf1bcf03a7`
- 校验结果：`VALID: 0 error(s), 0 warning(s)`

逐页预审时发现原文存在两套盈利预测口径。正式产物进行了两处有记录的最小修订：

1. 将 0.97/1.89/2.61 亿元明确标注为“机构一致预期口径”；
2. 删除与 1.08/1.45/2.01 亿元不一致的错误 CAGR，改用民生证券明确给出的
   净利润和 PE 预测。

完整逐页记录见
`docs/reviews/T2.3_002544_outline_review.md`。

## 5. 验证证据

- 全量自动化测试：`108 passed`
- 依赖入口：`requirements.txt`
- 主命令入口：`python main.py <command>`
- 四个功能模块的导入和独立脚本测试：通过
- README、文档链接和关键迁移路径一致性检查：通过
- 正式大纲：`0 error / 0 warning`
- Parsed Document：Schema 校验通过
- 输入选择：82 included / 0 omitted
- `slide_outline.schema.json`：Git blob 未变化
- `visualization.schema.json`：Git blob 未变化
- 敏感信息扫描：未发现 API Key
- 正式产物不包含完整请求、原始响应或 reasoning content
- 正式大纲 SHA-256 保持为
  `793dbb07a2b21f463d7352de9fbdfa6cb440f2c4a94c22be3b609bbf1bcf03a7`

可使用以下命令复核：

```powershell
python -m pytest -q

python main.py validate-outline `
  examples/generated/002544_2025-10-28_slide_outline.json
```

如需重新执行完整生成：

```powershell
$env:DEEPSEEK_API_KEY = "<your-key>"

python main.py parse-report `
  "data/reports/agent/002544_2025-10-28.md" `
  -o "output/002544_2025-10-28_parsed.json"

python main.py generate-outline `
  "output/002544_2025-10-28_parsed.json" `
  -o "output/002544_2025-10-28_slide_outline.json" `
  --model deepseek-v4-pro `
  --thinking enabled `
  --reasoning-effort high `
  --max-input-chars 180000 `
  --max-attempts 2
```

API Key 只能通过环境变量提供，不应写入命令脚本、配置文件、测试、日志或提交记录。

## 6. 合并文件范围

建议 partner 在合并时重点检查以下文件：

- `document_parser/`
- `outline_generator/`
- `ppt_template_parser/`
- `tools/`
- `main.py`
- `requirements.txt`
- `prompts/outline_system_prompt.md`
- `tests/unit/test_outline_generator.py`
- `tests/unit/test_main_entrypoint.py`
- `tests/integration/test_module_entrypoints.py`
- `tests/integration/test_repository_contracts.py`
- `.github/workflows/ci.yml`
- `README.md`
- `docs/README.md`
- `data/README.md`
- `examples/generated/002544_2025-10-28_slide_outline.json`
- `docs/reviews/T2.1_slide_outline_schema_review.md`
- `docs/reviews/T2.3_002544_outline_review.md`
- `docs/reviews/week2_acceptance_status.md`
- `docs/delivery/week2_t2.1-t2.3_partner_handoff.md`

合并时不要用其他项目中的同名 Schema 覆盖本仓库 Schema。调用方如存在旧字段，
应在调用方做适配，保持本仓库正式契约不变。

完整本地提交记录可通过 `git log --oneline` 查看；尚未 push、未创建 PR。

## 7. 未包含事项

- 未提交 API Key、完整 API 请求、原始响应、reasoning content 或临时解析产物。
- 原始 `.xlsx` 任务跟踪表仅移动到 `docs/planning/`，未修改工作簿内容；
  状态同步应在连接 Excel/Spreadsheets 会话后单独执行。
- 本地提交尚未 push，未创建 PR，因此 GitHub Actions 尚未在远端实际触发。

## 8. 后续衔接建议

后续 T2.4/T2.5 或 PPT 渲染模块应直接消费正式 Slide Outline Schema：

- Outline 只描述“每页讲什么”；
- Visualization 层负责图表和表格数据；
- Layout Mapping 层负责模板版式；
- Renderer 层负责坐标、字体、颜色和最终 PPT 对象。

这四层的边界应继续保持，避免将图表数据或模板布局字段重新写入 Outline。

Partner 后续开发应直接使用当前四个功能目录。等核心流程和公共接口稳定后，
再统一评估是否引入 `pyproject.toml`、可安装包和独立 CLI。

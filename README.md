# Research Report PPT Agent

将 PDF、Markdown 或 TXT 研报转换为可编辑 PPTX。当前主链路是：

```text
研报 → DocumentBundle → Document Intelligence → LLM Slide Outline
     → 可视化规划与事实校验 → 布局预检/编译 → PPTX 渲染
```

项目统一使用 Python 3.12。目标架构和后续重构边界见
[重构实施要求](docs/architecture/research_report_ppt_refactor_spec.md)。

## 当前保证

- `DocumentBundle` 是下游唯一事实来源，保留文本、表格、图片和来源定位。
- Outline 由真实 LLM API 生成；图表数值只能来自可追溯的 block/table 事实。
- Markdown 本地图片会复制到 Bundle；远程、缺失和越界路径会明确告警或报错。
- 默认字号不会低于布局声明的最小值；内容放不下时生成 `__cont_XX` 续页，不静默截断。
- Candidate Locator 在完整 Pipeline 中默认 `shadow`：记录候选但不擅自改变成品。
- 内容页建议 1 个视觉、最多 2 个；图页最多 1 个；非内容页不允许视觉。
- 折线图至少需要 4 个时间点；饼图需要 3–6 个非负扇区且合计约 100%。
- Pipeline 只在全部阶段成功后原子发布。失败时写入同级
  `<output>.failure/failure.json`，不会伪造已完成的 PPTX。

## 安装

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

LLM Outline 默认读取以下环境变量：

```powershell
$env:DEEPSEEK_API_KEY = "<your-key>"
$env:DEEPSEEK_MODEL = "<model-name>"       # 可选
$env:DEEPSEEK_BASE_URL = "<base-url>"      # 可选
$env:DEEPSEEK_API_PROVIDER = "deepseek"    # 可选
```

不要把 API Key 写入源码、命令参数、输出 JSON 或 Git 提交。PDF 在线解析另需
`MINERU_API_TOKEN`；仓库内 5 份 Markdown 基线不需要 MinerU。

## 快速开始

先生成模板配置：

```powershell
.\.venv\Scripts\python.exe main.py build-template-profile `
  templates/template_layout_map.json `
  templates/financial_report_template_v1.pptx `
  -o output/template_profile.json
```

用真实 LLM API 跑完整链路：

```powershell
.\.venv\Scripts\python.exe main.py run-pipeline `
  data/reports/agent/002544_2025-10-28.md `
  --template-profile output/template_profile.json `
  --output-dir output/002544_run `
  --outline-timeout 600 `
  --outline-max-attempts 2
```

生产默认使用 `--candidate-mode shadow`。如需验证候选图表实际生成，可显式使用
`--candidate-mode active`；完全关闭则使用 `disabled`。

成功目录包括：

```text
document_bundle/
slide_outline.json
candidate_locator_report.json
layout_preflight.json
numeric_fact_ledger.json
metric_groups.json
numeric_audit.json
visualization_warnings.json
visualizations/
template_profile.json
compiled_layout_plan.json
presentation.pptx
run_manifest.json
```

离线复用已审核 Outline 时可添加：

```powershell
--outline-input path/to/slide_outline.json
```

该选项只用于确定性回归，不能替代真实 API 基线。

## 五份真实研报基线

固定样本为：`000333`、`001309`、`002444`、`002544`、`002821`。配置 API 后运行：

```powershell
.\.venv\Scripts\python.exe tools/run_phase0_baseline.py `
  --template-profile output/template_profile.json `
  --output-root output/phase0_baseline `
  --outline-timeout 600 `
  --outline-max-attempts 2
```

脚本拒绝缺少 `DEEPSEEK_API_KEY` 的执行，不使用 mock、dry-run 或预制 Outline。
最近一次真实基线结果见
[`data/evaluation/phase0_real_api_baseline.json`](data/evaluation/phase0_real_api_baseline.json)。

## 分阶段命令

```powershell
# Markdown/TXT → DocumentBundle
.\.venv\Scripts\python.exe main.py document-bundle from-markdown `
  data/reports/agent/002544_2025-10-28.md `
  output/002544/document_bundle

# 真实 API 生成 Outline
.\.venv\Scripts\python.exe main.py generate-outline `
  output/002544/document_bundle `
  -o output/002544/slide_outline.json

# 生成可视化（默认 shadow）
.\.venv\Scripts\python.exe main.py generate-visualizations `
  output/002544/slide_outline.json `
  output/002544/document_bundle `
  -o output/002544/visualizations
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

CI 在 Ubuntu 和 Windows 上均使用 Python 3.12。自动化测试不会调用真实 LLM API；
真实 API 质量由上述 5 份研报基线单独验收。

## 目录

| 路径 | 职责 |
|---|---|
| `document_bundle/` | 统一输入、Markdown/PDF 解析和资产物化 |
| `document_intelligence/` | 确定性 evidence 索引 |
| `outline_generator/` | 上下文压缩和 LLM Slide Outline |
| `visualization_generator/` | 候选、事实抽取、验证和数值审计 |
| `ppt_engine/` | 视觉预算、布局预检、分页、编译和渲染 |
| `pipeline_runner/` | 原子编排、诊断和发布 |
| `schemas/` | 冻结的数据契约 |
| `tests/`、`examples/` | 单元、集成和受控验收样例 |
| `data/reports/agent/` | 5 份真实 Markdown 研报基线 |

更多文档见 [docs/README.md](docs/README.md)。

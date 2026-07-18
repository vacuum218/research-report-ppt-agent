# Research Report PPT Agent

将中文证券研究报告转换为结构化 PPT 资产的 Python 项目。

当前已实现研报解析、语义大纲生成、Schema/语义校验、PPT 模板解析和
Layout Map 构建。Visualization 数据抽取与最终 PPT Renderer 仍在规划中。

## 当前能力

| 阶段 | 状态 | 权威输出 |
|---|---|---|
| Markdown/纯文本解析 | 已完成 | `parsed_document.schema.json` |
| DeepSeek 幻灯片大纲生成 | 已完成 | `slide_outline.schema.json` |
| Outline/Visualization 校验 | 已完成 | Schema + 语义问题列表 |
| PPT 模板解析与对象盘点 | 已完成 | 模板对象 JSON |
| 语义 Layout Map | 已完成 | `template_layout_map.json` |
| Visualization Detector | 规划中 | `visualization.schema.json` |
| PPT Renderer | 规划中 | `.pptx` |

核心数据流：

```text
Research Report
→ Parsed Document
→ Slide Outline
→ Visualization
→ Layout Mapping
→ PPT Renderer
```

Slide Outline 只描述“每页讲什么”；图表数据、模板坐标和渲染样式分别属于
Visualization、Layout Mapping 和 Renderer，不得混入 Outline。

## 安装

要求 Python 3.10 或更高版本。

```powershell
python -m pip install -e ".[dev]"
```

也可以继续使用兼容入口：

```powershell
python -m pip install -r requirements.txt
```

## 快速开始

安装后推荐使用统一命令 `research-report-ppt`：

```powershell
# 1. 解析研报
research-report-ppt parse-report report.md `
  -o output/report_parsed.json

# 2. 离线构建大纲请求，不调用模型
research-report-ppt generate-outline output/report_parsed.json `
  --dry-run `
  --request-output output/outline_request.json

# 3. 真实生成并自动校验
$env:DEEPSEEK_API_KEY = "<your-key>"
research-report-ppt generate-outline output/report_parsed.json `
  -o output/slide_outline.json `
  --max-attempts 2

# 4. 校验大纲
research-report-ppt validate-outline output/slide_outline.json

# 5. 盘点模板并生成 Layout Map
research-report-ppt inspect-template `
  templates/financial_report_template_v1.pptx `
  -o output/template_objects.json

research-report-ppt build-layout-map output/template_objects.json `
  -o output/template_layout_map.json
```

源码 checkout 中仍支持：

```powershell
python main.py --help
python main.py generate-outline --help
```

旧的 `document_parser`、`outline_generator`、`ppt_template_parser` 和 `tools`
路径保留为兼容层，计划在 Week 4 交付后移除。新代码应直接使用
`research_report_ppt` 包。

## Python API

```python
from research_report_ppt.parsing import parse_file
from research_report_ppt.validation import validate_outline

parsed = parse_file("report.md")
```

主要模块：

- `research_report_ppt.parsing`：Markdown/纯文本解析；
- `research_report_ppt.outline`：DeepSeek 请求、响应处理和纠错重试；
- `research_report_ppt.validation`：Schema 与语义校验；
- `research_report_ppt.templates`：模板解析、盘点与 Layout Map；
- `research_report_ppt.paths`：权威资源路径。

## 项目结构

```text
├── src/research_report_ppt/  # 正式 Python 包
├── schemas/                  # 权威 JSON Schema
├── prompts/                  # LLM Prompt 与 few-shot
├── templates/                # PPT 模板与预生成 Layout Map
├── examples/                 # 合法契约样例和正式生成样例
├── data/                     # 研报测试素材与参考资料
├── docs/                     # 架构、规范、计划、评审和交付文档
├── tests/                    # unit、integration、fixtures
├── main.py                   # 旧源码命令兼容入口
└── pyproject.toml            # 包、依赖、CLI 和 pytest 配置
```

文档入口见 [docs/README.md](docs/README.md)，测试数据说明见
[data/README.md](data/README.md)。

## 测试

```powershell
python -m pytest -q
```

测试不调用真实 DeepSeek API。正式验收样例位于
`examples/generated/002544_2025-10-28_slide_outline.json`。

## 开发规则

- `schemas/slide_outline.schema.json` 和
  `schemas/visualization.schema.json` 是跨模块权威契约；
- 修改 Schema 必须同步规范文档、合法样例和测试；
- API Key 只能通过环境变量提供；
- 不提交完整 API 请求、原始响应、reasoning content 或临时解析产物；
- 新功能必须增加单元测试或集成测试。

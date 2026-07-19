# Research Report PPT Agent

将中文证券研究报告转换为结构化 PPT 资产的 Python 项目。

项目目前处于 Week 2，已实现研报解析、语义大纲生成、Schema/语义校验、
PPT 模板解析、运行时 Layout Mapping 和基础 PPT Engine。Visualization 数据抽取
仍在规划中；Renderer 已可消费现有 Visualization JSON，但不会自行抽取数据。

## 当前能力

| 阶段 | 状态 | 权威输出 |
|---|---|---|
| Markdown/纯文本解析 | 已完成 | `parsed_document.schema.json` |
| DeepSeek 幻灯片大纲生成 | 已完成 | `slide_outline.schema.json` |
| Outline/Visualization 校验 | 已完成 | Schema + 语义问题列表 |
| PPT 模板解析与对象盘点 | 已完成 | 模板对象 JSON |
| 语义 Layout Map 与 Resolver | 已完成 | `template_layout_map.json` |
| Visualization Detector | 规划中 | `visualization.schema.json` |
| 基础 PPT Engine | 已完成 | 可打开的 `.pptx` |

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
python -m pip install -r requirements.txt
```

## 快速开始

项目统一通过 `main.py` 执行当前已有功能：

```powershell
# 1. 解析研报
python main.py parse-report report.md `
  -o output/report_parsed.json

# 2. 离线构建大纲请求，不调用模型
python main.py generate-outline output/report_parsed.json `
  --dry-run `
  --request-output output/outline_request.json

# 3. 真实生成并自动校验
$env:DEEPSEEK_API_KEY = "<your-key>"
python main.py generate-outline output/report_parsed.json `
  -o output/slide_outline.json `
  --max-attempts 2

# 4. 校验大纲
python main.py validate-outline output/slide_outline.json

# 5. 盘点模板并生成 Layout Map
python main.py inspect-template `
  templates/financial_report_template_v1.pptx `
  -o output/template_objects.json

python main.py build-layout-map output/template_objects.json `
  -o output/template_layout_map.json

# 6. 校验固定模板映射
python main.py validate-layout-map templates/template_layout_map.json

# 7. 仅使用 Outline 与 Layout Map 生成基础 PPTX
python main.py render-ppt examples/slide_outline_valid.json `
  -o output/outline_demo.pptx

# 8. 可选：把冻结的 Visualization JSON 绑定到指定 slide_id
python main.py render-ppt examples/slide_outline_valid.json `
  -o output/visual_demo.pptx `
  --visualization slide_002=examples/visualization_valid.json `
  --visualization slide_002=examples/visualization_table_valid.json
```

各模块脚本也可以独立执行，例如：

```powershell
python document_parser/parse_report.py --help
python outline_generator/generate_outline.py --help
python tools/validate_outline.py --help
```

## 当前代码结构

```text
├── document_parser/         # Markdown/纯文本解析
├── outline_generator/       # DeepSeek 大纲生成和纠错重试
├── ppt_template_parser/     # PPT 结构、样式和主题解析
├── ppt_engine/              # Layout Resolver、模板页构建与 PPTX 渲染
├── tools/                   # 校验、模板盘点和 Layout Map
├── schemas/                 # 权威 JSON Schema
├── prompts/                 # LLM Prompt 与 few-shot
├── templates/               # PPT 模板与预生成 Layout Map
├── examples/                # 合法契约样例和正式生成样例
├── data/                    # 研报测试素材与参考资料
├── docs/                    # 架构、规范、计划、评审和交付文档
├── tests/                   # unit、integration、fixtures
├── main.py                  # 当前统一命令入口
└── requirements.txt         # Python 依赖
```

上述四个 Python 目录直接保存完整实现，不存在额外的 `src` 实现层或兼容包装层。

文档入口见 [docs/README.md](docs/README.md)，测试数据说明见
[data/README.md](data/README.md)。

## 测试

```powershell
python -m pytest -q
```

自动测试不会调用真实 DeepSeek API。正式验收样例位于
`examples/generated/002544_2025-10-28_slide_outline.json`。

## 开发规则

- `schemas/slide_outline.schema.json` 和
  `schemas/visualization.schema.json` 是跨模块权威契约；
- 修改 Schema 必须同步规范文档、合法样例和测试；
- API Key 只能通过环境变量提供；
- 不提交完整 API 请求、原始响应、reasoning content 或临时解析产物；
- 新功能必须增加单元测试或集成测试；
- 等核心流程和公共接口稳定后，再评估是否引入可安装包和独立 CLI。

# Research Report PPT Agent

## 研报文本 → 可视化 PowerPoint 自动生成系统

本项目旨在实现一个自动将上市公司研究报告文本转换为专业 PowerPoint 的系统。

输入：

- 上市公司研究报告纯文本
- Markdown 格式文本


输出：

- 结构清晰的 PowerPoint 文件
- 统一的视觉风格
- 自动生成的图表与数据表格


---

## 项目简介

传统 PPT 生成工具通常依赖已有图片、表格或人工排版。

本项目针对研报场景，通过：

- 文本理解
- LLM 内容规划
- 数据抽取
- 自动可视化
- 固定模板渲染

实现：


研报文本

↓

内容解析

↓

幻灯片大纲生成

↓

图表/表格生成

↓

PowerPoint 输出

---

## 核心功能

### 1. 研报文本解析

支持：

- Markdown文本解析
- 标题层级识别
- 段落分析
- 表格解析


### 2. 幻灯片自动规划

利用 LLM 将研报内容转换为 PPT 页面结构。

例如：

- 公司概况
- 行业分析
- 财务表现
- 估值分析
- 风险分析


### 3. 自动可视化

从文本中识别可视化数据：

- 营收趋势
- 利润变化
- 增长率
- 估值比较

并自动生成：

- 折线图
- 柱状图
- 表格


### 4. 固定模板 PPT 渲染

基于：

- python-pptx
- PPT 模板解析

实现：

- 页面布局匹配
- 内容填充
- 图表插入
- 样式统一


---

## 项目参考

参考项目：

MemSlides

https://github.com/huohua325/Memslides


本项目借鉴：

- Template Induction 思路
- python-pptx 渲染方式


主要区别：

| | MemSlides | 本项目 |
|-|-|-|
|输入|论文 PDF|研报文本|
|风格|用户个性化风格|固定模板|
|图片|已有内容|自动生成|
|核心|论文PPT Agent|研报可视化生成|

---

## 当前进展

已完成：

### PPT Template Parser

支持：

- PPT 文件读取
- Slide结构解析
- Shape解析
- 文本框解析
- 图片读取
- 基础样式读取

### Markdown / Text Parser

- Markdown 与纯文本解析
- 多级标题、段落、列表、表格、引用、图片和代码块
- 保留原文行号、块 ID、章节路径和引用
- 输出通过 `schemas/parsed_document.schema.json` 校验

### Slide Outline Generator

- 使用 DeepSeek OpenAI-compatible API 生成语义大纲
- 支持离线 `--dry-run` 请求预览
- 严格使用 `schemas/slide_outline.schema.json`
- 大纲与 Visualization / Layout Mapping 分层，不混入图表数据或模板坐标

### Template Layout Mapping

- 导出模板对象、样式、位置和图表/表格信息
- 依据命名锚点生成 16 种语义 layout map
- 已包含模板文件和预生成的 `templates/template_layout_map.json`

## 快速开始

```powershell
python -m pip install -r requirements.txt

# 1. 解析研报
python main.py parse-report report.md -o output/report_parsed.json

# 2. 离线检查大纲请求
python main.py generate-outline output/report_parsed.json `
  --dry-run `
  --request-output output/outline_request.json

# 3. 调用 DeepSeek 生成并校验大纲
$env:DEEPSEEK_API_KEY = "your-api-key"
python main.py generate-outline output/report_parsed.json `
  -o output/slide_outline.json

# 4. 检查模板并构建 layout map
python main.py inspect-template templates/financial_report_template_v1.pptx `
  -o output/template_objects.json
python main.py build-layout-map output/template_objects.json `
  -o output/template_layout_map.json
```

单独校验现有大纲：

```powershell
python tools/validate_outline.py examples/slide_outline_valid.json
python tools/validate_visualization.py examples/visualization_valid.json
```


---

## 项目结构

```

research-report-ppt-agent/

├── docs/                    # 项目文档
├── ppt_template_parser/     # PPT模板解析
├── reference/               # 参考资料
├── 测试研报/                # 测试数据
├── document_parser/         # 文本解析
├── outline_generator/       # 大纲生成
├── prompts/                 # 大纲生成提示词与少样本
├── schemas/                 # 分层 JSON Schema
├── templates/               # PPT 模板与 layout map
├── tools/                   # 校验和模板盘点工具
├── visualization/           # 图表生成
├── ppt_engine/              # PPT渲染
├── tests/                   # 测试
├── main.py
└── requirements.txt

```

---

## 技术栈

- Python
- python-pptx
- matplotlib
- pandas
- LLM API
- pytest


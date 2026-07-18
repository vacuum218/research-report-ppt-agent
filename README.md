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


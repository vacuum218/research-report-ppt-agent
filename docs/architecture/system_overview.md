# 系统架构说明

## 总体流程

研报文本

↓

Markdown / Text Parser

↓

结构化文档树

↓

Slide Outline Generator

↓

大纲 JSON

↓

Visualization Detector

↓

Chart/Table JSON

↓

Layout Engine

↓

python-pptx Renderer

↓

最终 PPT

## 当前实现状态

| 模块 | 状态 | 当前代码位置 |
|---|---|---|
| Markdown / Text Parser | 已实现 | `research_report_ppt.parsing` |
| Slide Outline Generator | 已实现 | `research_report_ppt.outline` |
| Schema/语义校验 | 已实现 | `research_report_ppt.validation` |
| 模板解析与 Layout Map | 已实现 | `research_report_ppt.templates` |
| Visualization Detector | 规划中 | 尚无运行时模块 |
| PPT Renderer | 规划中 | 尚无运行时模块 |

下文同时描述当前模块和目标架构。标记为“规划中”的部分不得被视为已经交付。

## 模块说明

## 1. 文本解析模块

输入： - Markdown - 普通文本

输出： - 标题层级 - 段落 - 列表 - 表格

## 2. 大纲生成模块

负责：

将研报内容拆分为：

-   公司介绍
-   行业分析
-   核心逻辑
-   财务预测
-   估值分析
-   风险因素

输出必须为 JSON。

## 3. 可视化定位模块

状态：规划中。

这是区别于 MemSlides 的核心模块。

识别：

-   营收增长
-   利润趋势
-   CAGR
-   估值比较
-   市占率
-   财务指标

输出：

chart/table 数据结构。

## 4. PPT 渲染模块

状态：规划中。

技术：

-   python-pptx
-   matplotlib
-   pandas

负责：

-   页面创建
-   图片插入
-   表格生成
-   字体统一
-   样式控制

## 5. 模板模块

固定模板：

包含：

-   母版
-   配色
-   字体
-   placeholder
-   layout

不要设计用户画像系统。

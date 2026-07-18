\# Research Report PPT Agent



\## 项目名称



研报文本 → 可视化 PowerPoint 自动生成系统



\---



\## 项目简介



本项目旨在实现：



输入：

\- 上市公司研究报告纯文本（支持 Markdown）



输出：

\- 风格统一的专业 PowerPoint 文件



系统自动完成：



1\. 研报文本解析

2\. 幻灯片大纲生成

3\. 可视化内容识别

4\. 图表/表格自动生成

5\. 基于固定模板的 PPT 渲染





\---



\## 项目参考



参考项目：



MemSlides



https://github.com/huohua325/Memslides





本项目复用：



\- template induction 思路

\- python-pptx PPT 渲染方式





区别：



MemSlides:

\- 输入论文 PDF

\- 支持用户风格记忆



本项目:

\- 输入研报文本

\- 固定模板风格

\- 自动发现文本中的可视化数据





\---



\## 当前完成模块



\### PPT Template Parser



目录：





当前支持：



\- PPT 页面结构读取

\- Shape解析

\- 文本框解析

\- 图片元素读取

\- 基础样式读取





\---



\## 技术栈



Python



主要依赖：



\- python-pptx

\- matplotlib

\- pandas

\- LLM API

\- pytest





\---



\## 项目结构

research-report-ppt-agent/



├── ppt\_template\_parser/

│

├── document\_parser/

│

├── outline\_generator/

│

├── visualization/

│

├── ppt\_engine/

│

├── tests/

│

├── main.py

└── requirements.txt







\---



\## 环境安装



创建环境：



```bash

python -m venv venv



安装依赖：



pip install -r requirements.txt

运行方式



当前：



python main.py


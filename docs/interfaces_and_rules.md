# 接口规范与开发规则

## 分层接口

系统接口按以下顺序连接：

```text
Document JSON
→ Slide Outline JSON
→ Visualization JSON
→ Layout Mapping
→ PPT Renderer
```

Document JSON 由 `document_parser` 生成，正式定义见 `schemas/parsed_document.schema.json`。

Slide Outline 只描述页面内容语义、来源引用和可视化候选，正式定义见 `schemas/slide_outline.schema.json` 和 `docs/slide_outline_schema.md`。

Visualization JSON 只描述已抽取并核对的 chart/table 数据，正式定义见 `schemas/visualization.schema.json` 和 `docs/visualization_schema.md`。

模板 Layout、坐标、字体、颜色和渲染对象不得进入以上两个 Schema；它们分别属于 Layout Mapping 和 PPT Renderer。

## 开发规则

1.  所有模块必须独立
2.  输入输出必须明确
3.  修改 schema 必须同步文档
4.  新功能必须增加测试
5.  不允许直接修改核心接口导致联调失败

## Codex 工作方式

每次启动：

第一步： 阅读 docs/

第二步： 确认当前任务属于哪个模块

第三步： 查看已有代码

第四步： 修改并测试

第五步： 更新文档

# 测试数据与参考资料

本目录保存项目开发和人工验收需要的素材。文件继续由普通 Git 管理，
当前不使用 Git LFS。

## 目录

```text
data/
├── reports/
│   ├── agent/       # Agent 生成的 Markdown 研报及其 PDF
│   └── human/       # 人工研报 PDF
└── references/      # 项目调研参考资料
```

## 使用规则

- 自动化单元测试优先使用 `tests/fixtures/` 中的小型文本样例；
- `reports/agent/` 用于完整解析、真实大纲生成和人工内容验收；
- `reports/human/` 用于人工对比，不应加入快速单元测试；
- `references/` 仅用于项目调研，不属于运行时依赖；
- 新增二进制文件前应记录用途，避免提交重复版本或临时导出文件；
- 生成的 Parsed Document、API 请求和 PPT 输出应写入被忽略的 `output/`，
  不应写回本目录。

Week 2 T2.3 的正式输入为：

`data/reports/agent/002544_2025-10-28.md`

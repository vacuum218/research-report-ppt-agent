# Week 2 T2.6 最小端到端 Demo 交付说明

## 1. 验收结论

T2.6 已于 2026-07-19 使用真实研报
`data/reports/agent/002544_2025-10-28.md` 完成最小端到端联调：

```text
Markdown 研报
→ Parsed Document JSON
→ DeepSeek Slide Outline JSON
→ Outline/Layout Map validation
→ 模板化 PPTX
→ PowerPoint 逐页人工检查
```

最终 Outline 为 11 页，Schema 与语义校验结果均为 0 error、0 warning。
最终 PPTX 可由 PowerPoint 正常打开，页数与 Outline 一致。

## 2. 复现命令

```powershell
D:\anaconda\python.exe main.py parse-report `
  data/reports/agent/002544_2025-10-28.md `
  -o output/t2.6/002544_parsed.json

D:\anaconda\python.exe main.py generate-outline `
  output/t2.6/002544_parsed.json `
  --dry-run `
  --request-output output/t2.6/002544_outline_request.json

$env:DEEPSEEK_API_KEY = "<your-api-key>"

D:\anaconda\python.exe main.py generate-outline `
  output/t2.6/002544_parsed.json `
  -o output/t2.6/002544_outline.json `
  --max-attempts 2

D:\anaconda\python.exe main.py validate-outline `
  output/t2.6/002544_outline.json

D:\anaconda\python.exe main.py render-ppt `
  output/t2.6/002544_outline.json `
  -o output/t2.6/002544_final_demo.pptx
```

所有运行时产物都位于被 `.gitignore` 排除的 `output/t2.6/`，不会提交 API
请求预览、生成 Outline 或 PPTX。

## 3. 本次 Renderer 修复

- 替换模板文字时保留原段落与 Run 的字体、字号、颜色和粗细。
- 清除摘要指标、公司指标和图表标题中的模板示例内容。
- 修复风险页重复字段键不匹配，正确填充风险条目并清空未使用催化剂。
- 根据 Layout Map 的容量限制截断估值页和摘要页长文本。
- 为纯文本阶段调整 `slide_type_defaults`，避免绝大多数页面退化为
  `executive_summary`。

## 4. 最终版式分布

| `layout_id` | 页数 |
|---|---:|
| `executive_summary` | 3 |
| `company_overview` | 2 |
| `capability_map` | 2 |
| `cover` | 1 |
| `industry_outlook` | 1 |
| `valuation` | 1 |
| `risk_catalyst` | 1 |

共使用 7 种版式，单一版式最多占 3/11。

## 5. 自动化验证

```text
119 passed, 2 warnings
```

两条 warning 均为当前沙箱不能写入 `.pytest_cache`，不影响测试结果。

## 6. 人工检查

- 11 页均由 PowerPoint 成功渲染。
- 封面标题保持白色，与深蓝背景对比正常。
- 未发现空白页、重复页或明显对象重叠。
- 未发现 `[XX]亿元`、示例指标或示例图表标题残留。
- 页面标题、正文、来源和页码均正常显示。

## 7. 当前边界

T2.6 是纯文本最小链路。Visualization Detector 和经原文核对的 chart/table
数据仍属于 T3，因此行业、估值等图表型版式会保留空图表区域，不使用模板示例
数据，也不生成未经核对的数值。

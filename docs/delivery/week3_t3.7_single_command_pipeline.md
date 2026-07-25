# Week 3 T3.7 单命令 Pipeline 与回归

- 日期：2026-07-25
- 实现状态：**代码修改完成**
- 自动测试：**等待用户手动运行**
- 验收产物：**等待用户手动生成**

## 命令

```powershell
python main.py run-pipeline INPUT_DOCUMENT `
  --template-profile TEMPLATE_PROFILE `
  --output-dir OUTPUT_DIRECTORY
```

支持 Markdown、纯文本、PDF 和已有 DocumentBundle。PDF 沿用 `MINERU_API_TOKEN` 与现有
MinerU 配置；未传 `--outline-input` 时，Outline 阶段沿用现有模型配置和
`DEEPSEEK_API_KEY`。离线测试可以传入已审核 Outline：

```powershell
python main.py run-pipeline examples/week3_t3_6/document_bundle `
  --outline-input examples/week3_t3_6/outline.json `
  --template-profile output/week3_t3.6_end_to_end/template_profile.json `
  --output-dir output/week3_t3.7_pipeline
```

较长研报若出现 `DeepSeek output was truncated`，可通过统一命令透传 Outline 输出预算：

```powershell
--outline-max-tokens 24000
```

若第一次响应仍因 `finish_reason=length` 截断且允许第二次尝试，Outline 阶段会保留完全相同
的原始研报上下文，关闭 thinking 后重新请求紧凑、完整的 JSON。重试不会切换到 Context
Compression，也不会把截断的半份 JSON 当作内容依据；最终结果仍执行完整 Schema 与证据校验。

## 原子发布

Pipeline 在输出目录同级创建随机 staging 目录。只有以下阶段全部成功后，staging 才重命名为
最终输出目录：

1. DocumentBundle 构建与加载；
2. Outline 生成或正式 Schema 校验；
3. Visualization 生成；
4. Numeric Fact 审计；
5. Visualization Manifest 加载；
6. Template Profile 与 Layout 编译；
7. Compiled Renderer 生成 PPTX；
8. Run Manifest Schema 校验。

最终输出目录必须不存在或为空。非空目录会在 preflight 阶段被拒绝并原样保留。任一阶段失败
均返回非零码、清理 staging，且不打印 `Pipeline completed` 或 `Presentation`。

## 输出

```text
OUTPUT_DIRECTORY/
├── document_bundle/
├── slide_outline.json
├── numeric_fact_ledger.json
├── numeric_audit.json
├── visualization_warnings.json
├── template_profile.json
├── visualizations/
│   ├── visualization_manifest.json
│   └── *.json
├── compiled_layout_plan.json
├── presentation.pptx
└── run_manifest.json
```

`run_manifest.json` 通过 `schemas/run_manifest.schema.json` 校验，记录输入、全部正式 Schema、
Outline、Visualization Manifest、Template Profile、模板、Compiled Layout Plan、PPTX
和逐文件产物 hash。

候选若无法映射到可证明的 Numeric Fact（`no_traceable_source_data`），无论来自
Candidate Locator 还是 Outline 明确声明，都会写入 `visualization_warnings.json` 并安全
跳过，不阻断整份报告。跳过后 Compiler 会按实际可用的可视化重新选择文本或自适应版式。
显式候选若已进入数值验证但验证失败，仍属于 P0 错误并返回非零状态。

完整的纯文本表格可直接按 DocumentBundle 原生表格来源渲染，不强制要求至少一个 Numeric
Fact；一旦表格含有数值单元格，该单元格仍必须逐格绑定并通过 Numeric Fact 审计。

模型若返回空 `key_message`，Outline 后处理会优先复用该页第一条非空 bullet，若不存在则
复用非空 title。补值后仍执行正式 Outline Schema 和 evidence 校验，不绕过内容门禁。

## 回归测试

新增 `tests/integration/test_run_pipeline.py`：

- 单命令生成完整产物并逐项核对 hash；
- 重开 PPTX 并确认 2 个原生 chart、1 个原生 table；
- 未知 evidence 的 P0 失败返回非零码且不发布目录；
- 模板 hash 不一致时 render 失败且不宣称 PPTX；
- 非空输出目录保持不变；
- staging 目录在失败后被清理。

用户手动执行：

```powershell
python -m pytest tests/integration/test_run_pipeline.py tests/integration/test_week3_t3_6_end_to_end.py -q
python -m pytest tests/unit/test_main_entrypoint.py tests/unit/test_visualization_manifest.py tests/unit/test_layout_compiler.py tests/unit/test_ppt_engine.py -q
python -m pytest -q
```

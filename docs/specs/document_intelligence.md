# Document Intelligence Layer

Document Intelligence 是 DocumentBundle 上的确定性结构访问层，不是内容理解或 PPT 规划层。

输入是 bundle 目录或 `document.json`。输出是当前进程内的只读 snapshot：block、section、
table、figure 索引，reading order，section hierarchy，relationships，evidence locator 和 chunks。

Chunk 按 reading order 遍历，在 section 变化或字符预算边界处切分；不做相关度排序，
每个 block 必须覆盖一次且顺序不变。

模块不得 import Outline Generator 或 LLM 客户端，不得输出 summary、key points、importance、
bullet points 或 slide plan。Snapshot 和 chunk 均不是新的持久化数据标准。

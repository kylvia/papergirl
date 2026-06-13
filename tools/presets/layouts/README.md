# 正文信息图版式库

`cover.py --layout <名字>` 时，对应 .txt 的内容会替换 figure preset 里的 `{layout_block}`
占位行。每个 .txt 就是一段直接拼进生图 prompt 的"要求"条目；layout 块最先替换，
所以块内可以引用 `{brand_color}` 等模板变量，会被后续替换处理。

版式的信息结构蒸馏自 baoyu-skills 的 baoyu-infographic
（MIT, https://github.com/JimLiu/baoyu-skills）——只取版式，不取其视觉风格：
视觉统一走 figure preset 的白板手绘风，保账号识别度。

| 版式 | 适用 |
|---|---|
| binary-comparison | 两方对照、前后对比 |
| comparison-matrix | 多对象 × 多维度对比 |
| linear-progression | 流程、时间线、路线图 |
| hierarchical-layers | 层级、优先级、架构 |
| dashboard | 多指标数据快照 |
| iceberg | 表象 vs 深层（反差揭示型文章首选） |

新增版式：加一个 .txt 即可，cover.py 自动识别，无需改代码。

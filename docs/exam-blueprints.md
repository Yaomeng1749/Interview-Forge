# A / D / G 标准卷蓝图

生产题库上的 `standard` 预设同时满足三组硬约束：40 题、30 单选 + 10 填空、L1/L2/L3 = 12/20/8，以及下列知识分布。组卷器用整数最大流求解，不会在库存不足时静默放宽；不可满足时返回 HTTP 409。

## A / SDE

| Topic | 题数 |
|---|---:|
| `data_structures_algorithms` | 12 |
| `operating_systems` | 7 |
| `networks` | 7 |
| `databases` | 7 |
| `backend_systems` | 7 |

`backend_systems` 覆盖设计文档中的软件工程 / 后端类别。

## D / MLE

| Topic | 题数 |
|---|---:|
| `math_statistics` | 12 |
| `classical_ml` | 9 |
| `mlops_evaluation` | 10 |
| `deep_learning` | 9 |

`math_statistics` 合并概率统计与线性代数；`mlops_evaluation` 合并模型评估与数据处理。

## G / Mixed

| Domain | Topic | 题数 |
|---|---|---:|
| SDE | `data_structures_algorithms` | 6 |
| SDE | `operating_systems` | 3 |
| SDE | `networks` | 2 |
| SDE | `databases` | 3 |
| SDE | `backend_systems` | 6 |
| MLE | `math_statistics` | 2 |
| MLE | `classical_ml` | 3 |
| MLE | `mlops_evaluation` | 2 |
| MLE | `deep_learning` | 3 |
| MLE | `pytorch_training` | 2 |
| MLE | `transformer_llm` | 5 |
| MLE | `ml_systems_inference` | 3 |

总计 SDE 20、MLE 20。生产题库回归测试逐卷断言上述精确计数，并验证 40 个稳定题目 ID 不重复。

基础、强化和高难预设仍严格执行各自的难度与题型矩阵，并保持 A/D/G 域边界；由于当前 seed inventory 的 topic × difficulty 覆盖不均，这三个非默认预设暂不声称同时满足上述精确 topic 配额。

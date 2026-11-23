---
title: 参考：给上游提 issue/PR
parent: 评测教程
nav_order: 10
---

# 参考：给上游提 issue/PR

> 解决什么问题：链路里发现 harness 本体的 bug（不是我们的配置问题），要往上游
> [`allenai/vla-evaluation-harness`](https://github.com/allenai/vla-evaluation-harness) 提。
> 本页是本仓实测跑通的方法，附三个真实案例。操作手册见 [运维 02](../operator/02-duty-dispatch.md)。

## 标准四步

### 1. 发现问题：证据先行，三件套缺一不开帖

| 证据 | #166 实例 | 去哪找 |
|---|---|---|
| spec warning 原文 | `Spec mismatch: action [joints]: benchmark expects it but server doesn't declare it`（orchestrator 启动即打） | run 日志头 20 行 |
| 对照数据（排除链路本身） | X-VLA 0%/75+ep vs 官方 recipe 70/39%；同链路 DB-CogACT grab_roller 92% vs 官方 89%（链路健康） | aggregate.json + 官方 leaderboard |
| 双边根因定位 | server 吐 20-D EE6D 无转换；benchmark 硬截 `act[:14]` 当关节喂 | 上游 `xvla.py` + `benchmark.py` 行号 |

### 2. 问作者确认：给方案不给情绪，附复现路径

issue 模板（照抄可用）：背景（一句话）→ 复现（镜像 tag + serve yaml + 1 条 dispatch 命令）→ 根因（文件 + 行号）→ 提议（参数化方案，默认行为不变）。

本仓时效：#166 当天收到维护者 "Happy to receive PR"；#169（SmolVLA 6-D vs 7-D）当天收到绕行钥匙。
**铁律：先等确认再写大补丁**——方向错了白干。

### 3. 解决问题：fork + 分支 + GPU 实测矩阵

- fork 上游 → 补丁分支 → 统一镜像烘焙验证。
- 验证矩阵（写进 PR description，缺一项 reviewer 就问）：benchmark 镜像 digest × serve 镜像 × 任务 × 集数 × action_type × fast_init。
- #168 数据：6ep 全跑满步数零 ERROR，0/6（判负非链路问题，server 侧 gripper 语义，另开跟踪）；#169 按钥匙换 checkpoint 重跑出分才关（无 run 链接不关）。

### 4. 提交跟进：24h 响应，合并不了就留档

- PR 标题格式：`[WIP]/[ready] <benchmark>: <改动> (fixes #<号>)`；WIP 先占坑，验证完转 ready。
- review 意见 24h 内回；要挪代码位置（benchmark 侧 vs server 侧）照办，逻辑照搬。
- 合并不了：留 fork 分支 + 本仓 docs 注明 + issue 里更新状态。

## 反模式（本仓踩过，附代价）

- **猜作者意图直接开干**：SmolVLA 映射照 pi05 猜，10/10 全 ERROR，烧一轮 GPU + 一天排查——先问后写。
- **无验证关 issue**：#169 差点凭回复就关；规矩：无 run 链接不关（定量结论必须有 artifact）。
- **改 server 还是改 benchmark 拍脑袋**：原则是不动官方件（X-VLA 权重/镜像原样用），转换跟口径走。两边都通时，写进 PR discussion 让 reviewer 选。
- **阈值拍脑袋**：JEV 裁判 0.5 阈值看似合理实则全错（AUC 0.16 反向），0.2 才 20/20——阈值必须靠数据定。

## 回馈清单

- #166（问题）→ #168（PR，已合入上游主线）
- #169（问题 → 钥匙 → 验证 → 关，附 run）
- 分拆验证数据（资产外置 45/50 vs 46/50）已同步上游讨论。

## 相关

- 栈差异对照：[explanation/01-stack-effects.md](../explanation/01-stack-effects.md)
- 精度断崖：[explanation/02-precision-cliff.md](../explanation/02-precision-cliff.md)
- 归档原稿：[old/09-community.md](../old/09-community.md)（含投稿计划等历史信息，只读）

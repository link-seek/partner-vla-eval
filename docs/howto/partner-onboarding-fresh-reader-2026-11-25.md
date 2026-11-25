---
title: 独立读者实测：伙伴接入文档走查（2026-11-25）
nav_exclude: true
status: living
---

# 独立读者实测：伙伴接入文档走查

> 这是 ② 便捷性的**独立读者**证据，不是真人实测。
> 读者是一个**没有本仓上下文**的 AI 子代理（会话 `ses_dec8760caffe1GWuTzKzwcRvJg`），
> 只允许读三份公开文档 + 上游 yaml，不允许看本仓任何文件。

---

## 一、方法与约束

| 项 | 设定 |
|---|---|
| 任务 | 按 `tutorial/partner/01` 把 X-VLA 接入 RoboTwin，产出 serve yaml + 对接表单 + 自检 |
| 可读材料 | 01-serve-yaml / partner-onboarding / 02-full-and-report / 上游 `xvla/robotwin.yaml` |
| 禁止 | 浏览本仓、跑评测、碰 GPU |
| 计时 | 每阶段前后 `date -u +%s` |
| 产物 | `/tmp/opencode/fresh-reader/{xvla-robotwin.yaml,onboarding-form.md,selfcheck.md}` |

## 二、耗时（AI 速度，**不可**当真人估计）

| 阶段 | 秒 |
|---|---|
| 读 01-serve-yaml | 9 |
| 读对接表单 | 7 |
| 读 02-full-and-report | 10 |
| 读上游 yaml + 对照 | 22 |
| 改 serve yaml | 13 |
| 填表单 | 14 |
| 自检 | 16 |
| **合计** | **94 秒** |

AI 读文档是"秒级"，真人是"分钟级"；这组数只说明**文档长度不是瓶颈**，
真正的成本在下面 9 个需要判断的地方。真人 30 分钟的实测仍然缺（见第六节）。

## 三、独立读者卡住的 9 处

| # | 卡点 | 文档现状 | 读者怎么处理 |
|---|---|---|---|
| 1 | `model_path` 是单值，但提示"按 task 分头逐个列齐" | 没说"单仓共享"与"按 task 分目录"是两类模型 | 猜：只写 repo 根 |
| 2 | 要求"精确 commit"，但 yaml 里没有 `revision` 字段 | 没说 commit 落在哪 | yaml 只写 repo，commit 放表单 |
| 3 | X-VLA 的动作维度/旋转表示没给 | 表单要求填 14/16 维、rot6d/quat | 由 14 维反推，注明"猜" |
| 4 | C 例没有 `camera_keys`，B 例有 | 没说相机谁声明 | 猜：由 benchmark 下发 |
| 5 | `send_state` 未说明是 qpos 还是 EE | 只有一句"from the benchmark" | 猜：关节角 |
| 6 | RobotWin 全量 task 清单不在文档里 | 只出现两个 task 名 | 只列两个，其余"待补" |
| 7 | yaml 放哪、叫什么、是否覆盖官方 | 只写"第 5 步" | 猜：不落地，直接交 |
| 8 | `_base.yaml` 不在可读范围 | 说"不动"，但内容可能已变 | 按不读、不校验处理 |
| 9 | 表单 `dtype：不用填` 长得像要填的字段 | 一行标签 + 一行说明 | 空着 |

## 四、据此改掉的文档空白

`docs/tutorial/partner/01-serve-yaml.md` 新增「常见歧义」一节，逐条回答 1–8：

- 单仓共享（X-VLA）vs 按 task 分头（DB-CogACT）怎么判断；
- 精确 commit 只走表单，由我们在 registry / 快照里钉（示例：X-VLA `a157c58…`、CogACT `4c6404…`）；
- 动作 spec 写"原生产出"，不确定就写不确定，由 smoke 暴露，不要求伙伴猜；
- `camera_keys` 只有需要它的 server（如 CogACT）才填，X-VLA 由 benchmark 下发；
- 状态口径由 benchmark 定（RobotWin2 为 14 维关节角）；
- RobotWin 50 task 清单给官方链接；
- 伙伴不落地文件，yaml 发给我们放入 `configs/model_servers/<family>/<benchmark>.yaml`，不覆盖上游。

`docs/partner-onboarding.md` 的 `dtype` 一行改为明确的"跳过"。

## 五、独立读者最该先修的 3 条（已修）

1. **commit 落点**：这是"必须给精确版本"与"yaml 没这个字段"的正面冲突，最容易让伙伴猜。
2. **per-task 映射**：决定 `model_path` 写一个还是多个，猜错直接跑不了。
3. **动作 spec**：文档自己警告"猜错就是全 0 分烧一轮卡"，却让读者从 14 维反推。

## 六、仍然需要真人（② 的剩余缺口）

这次是 AI 独立读者，**不能替代真人**。要升级成"真人 30 分钟实测"，仍需一位没碰过本仓的人，
按改后的 01 走一遍并记录：

1. 从打开文档到交出 yaml 的**总时长**；
2. 每节的**停留时长**（哪节最久）；
3. **卡住次数**及原因（对照本文第三节 9 类）；
4. 需要问人的**问题数**。

四项拿到后，材料里的"30 分钟"才能从文档估算改成真人实测。

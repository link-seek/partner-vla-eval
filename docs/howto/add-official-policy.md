---
title: How-to：接一个新的官方策略（约 30 行）
nav_exclude: true
status: living
---

# How-to：接一个新的官方策略

> 现状：ACT、DP 两个官方基线共用**同一个 Dockerfile**、**同一个适配器文件**，
> 靠 `--build-arg POLICY=act|dp` 区分；动作队列、观测转换已抽成可复用模块。
> 下面这套就是"第三次接入"要走的路径——目标是**写 ~30 行，不改公共逻辑**。

---

## 一、先分清哪部分是"策略专属"

| 模块 | 行数 | 归属 | 新策略要不要动 |
|---|---|---|---|
| `action_queue.py` | 74 | **公共** | 不动（队列语义与策略无关） |
| `robotwin_obs.py` | 153 | **公共**（图像/关节转换） | 只在"图像契约"不同时加分支 |
| `robotwin_policy.py` | 349 | **策略骨架 + 两个 profile** | 加一段 profile（~30 行） |
| `Dockerfile.serve-robotwin` | — | 构建 | 加一个 `POLICY=` tag |

也就是说：**第三次接入 = 一个 profile + 一个镜像 tag**。

---

## 二、新策略要填的 6 个钩子

```python
# 1) 导入官方模型类（相对路径取决于官方仓结构）
from policy.NEWPOLICY.deploy_policy import get_model, reset_model

# 2) 观测 → 官方 encode_obs 期望的 dict（复用 build_policy_obs 的 resizer/to_chw01）
def _to_policy_obs(obs):
    ...

# 3) 动作返回形态：单步 or 整块（决定用不用 ActionQueue）
#    单步：ACT 风格；整块：DP 风格（队列空才推理）

# 4) 权重加载：官方 ckpt 文件名与加载方式（记得断言 missing/unexpected）
#    坑：官方 ckpt 常叫 policy_epoch_<N>_seed<S>.ckpt，而 deploy_policy 只认 policy_last.ckpt
#        → 写错会**静默**用随机权重

# 5) reset：官方有内部时序缓冲（temporal_agg / n_action_steps）必须清

# 6) spec 声明：动作维度与观测键，必须与 benchmark 逐字对齐（下面第三节）
```

---

## 三、四条硬契约（都是踩过的，别再踩）

| # | 契约 | 踩坑记录 |
|---|---|---|
| 1 | **图像尺寸** | 考场 D435 出 240×320；ACT 官方要 640×480，DP **不许 resize**。不做/做错都不会报错，只会 0 分 |
| 2 | **观测键** | DP 显式读三路相机（缺一路 `KeyError`），但 encoder 只消费 `head_cam`。只看一层会来回改 |
| 3 | **动作形态** | 整块 (n,14) 当单步 84 维会报维度错；每步都推理则偏离官方行为 |
| 4 | **相对路径** | 官方 `get_model` 常用相对 CWD + 多段 ckpt 目录 → serve 的 CWD 必须对，ckpt 要挂到官方拼出来的路径 |

**方法论**：判断"要给什么输入"，顺着**调用链**从最外层读到最内层——
最外层（runner）决定**需要哪些键**，最内层（encoder）决定**数值形状**。

---

## 四、验收（必须三层都过）

| 层 | 怎么验 | 通过标准 |
|---|---|---|
| 静态 | `check_contracts.py` | yaml 的 `args` ⊆ 类签名；顶层键合法 |
| 加载 | 容器内 `import policy.NEWPOLICY.deploy_policy` | 构建期自检（Dockerfile 里 `RUN ...`） |
| 真跑 | `smoke_serve.sh --episodes 1` | `num_errors=0`，aggregate 落盘 |

**注意**：`n=1` 只证明链路通，**不作分数结论**。

---

## 五、实际成本（ACT/DP 两次实测）

| 项 | 值 |
|---|---|
| 适配器代码 | 349 行（含两个 profile），新增 profile ≈ 30 行 |
| 公共模块 | 74（队列）+ 153（观测转换） |
| 镜像 | 1 个 Dockerfile 出 2 个 tag（`POLICY=` 切换） |
| 调试轮次 | ACT 5 轮（resize→键→三路→不 resize→动作块），DP 4 轮 |
| 每轮成本 | 单集 smoke ≈ 1 元（7 分钟）；50 集 ≈ ¥200 |

**经验**：真正花时间的不是写代码，是**发现契约**。第二次（DP）之所以快，是因为已经把
"先读调用链再写"变成流程；第三次可以直接照第四节的验收表走。

# 收口设计（先定后改）：B3 / B1 / A5 / 决策 3

> 2026-11-25。这份文档是**执行前的整体设计**，目的是终止"修一处、冒一处"的返工。
> 规则：代码只按本文实施；若发现新事实与本文冲突，**先改本文，再改代码**。
> 本文不含新结论，只把今天已用实测确认的事实固化下来，并给出剩余工作的唯一路径。

---

## 0. 已冻结的契约（实测确认，不再重议）

| 事实 | 证据 | 影响 |
|---|---|---|
| 考场相机是 **D435 = 240×320**；官方 `encode_obs` 必须 resize 到 **640×480** | 缺 resize 连跑 2 次 0/1；补上后 1/1；serve 日志 `image shapes={'head_camera': (240, 320, 3)}` | 适配器 `RESIZE_WH` 不可去 |
| **ACT vs DP 图像契约**：ACT = 三路 + resize 640×480；DP = 三路但**不 resize**（原生 240×320）。DP 的 `DPRunner.get_action` 显式读三路（缺一路 KeyError），encoder 只消费 `head_cam` 且 assert 尺寸=(3,240,320) | 读 `dp_runner.py:91-95`（读三路）+ 载 ckpt 打印 `key_shape_map`（只 head_cam，240×320） | `robotwin_obs.py` 按策略分支 |
| **动作返回形态不同**：ACT 返回单步 `(14,)`；DP 返回整块 `(6,14)`，官方开环执行 6 步再重新推理 | `dp_runner.py:get_action` 返回 `[:n_action_steps]`；`deploy_policy.eval` 是 `for action in actions` | 适配器维护动作队列，队列空才推理 |
| qpos 顺序 = `left_arm(6)+lg+r_arm(6)+rg`，与官方 `joint_action["vector"]` 一致 | `_base_task.py:494` 源码 | 观测转换不再改 |
| ACT 内部自做 qpos 归一化 | `act_policy.py:164` | 我们传原始 qpos 是对的 |
| harness 的 `IMAGE_RGB` 维度=0，**不会**替我们 resize | `specs.py:177` | 必须在适配器层 resize |
| serve 端口只能走 `args.port` 或 `--address`，**顶层 `server.port` 被静默忽略** | 实测绑到 8000 撞车；`vla-eval serve --help` 原文 | serve yaml 不允许出现 `server:` |
| `args.*` 必须是 `__init__` 显式参数 | `unrecognized arguments: --args.left_arm_dim` | 契约测试静态守 |
| DP 推断依赖共 8 个（hydra-core/dill/einops/zarr/numcodecs/numba/atomics/diffusers 0.27.2） | 构建期 `import policy.DP.deploy_policy` 通过 | 已钉进 Dockerfile |
| DP 用相对路径 + 4 段目录 `<task>-<setting>-<num>-<seed>` | `policy/DP/deploy_policy.py:get_model` | serve CWD=`/app/RoboTwin`，ckpt 按该路径挂载 |
| ACT / DP 覆盖考场 **2/5**（`adjust_bottle`、`click_bell`） | ACT 310 ckpt、DP 320 ckpt 的文件清单交集 | 榜单必须标覆盖差异 |
| digest 用 **manifest digest**（`buildx imagetools inspect`） | config.digest 做 FROM 会报 media type | registry/文档只认这个 |
| aggregate 的"有没有报错"看 **`task.num_errors` + 每集 `failure_reason`/`failure_detail`**，不是 `episodes[].error`（没有这个键） | 2026-11-25：DP 1 集报错但旧断言报 errors=0 判 PASS | 后置断言已对齐 |
| 就绪探针必须打 **服务自己的 HTTP `/config`**（实测 200） | serve 日志 `HTTP config endpoint at http://…/config`；`sh`(dash) 不支持 `/dev/tcp`，用它会永远 unhealthy | `smoke_serve.sh` 用 curl 探针 |
| 采集目录命名有三种并存 | `ci_model_matrix.sh` 写 `<task>-<proto>[-<rN>]`；历史有 `<task>-hard`、裸 `<task>` | 采集器兼容，但**禁止跨协议/跨轮回落** |

---

## 1. 剩余工作的唯一路径

### 阶段 B3-serve（当前）
| 项 | 输入 | 动作 | 产物 | 门禁/验收 |
|---|---|---|---|---|
| B3-1 ACT verified | 镜像 `…-act@sha256:12fcc9be…` + ckpt rev `c248f218…` | 镜像内适配器跑 1 task×1ep（共 3 次） | ✅ `status=verified`，smoke 1/3、0 error | `check_registry` OK |
| B3-2 DP smoke | 镜像 `…-dp@sha256:dafe751f…` + `500.ckpt` | 同上 | ✅ `status=verified`，smoke 1/1、0 error | aggregate 落盘 + errors=0 |

工具：`scripts/ci/smoke_serve.sh`（前置断言 + docker healthcheck + 后置 aggregate 断言）。
**不通过就停在 B3，不往下推**——因为 B1 收数和 A5 都不依赖它，但 B3 的结论会被引用。

### 阶段 B1-collect（等 GPU 空闲，约 11-26 01:42Z）
| 步骤 | 命令 | 验收 |
|---|---|---|
| 收数 | `bash scripts/data/collect_matrix.sh x-vla-robotwin2 hard` | 5 个 task 全 `n=50`，无 `missing` |
| 报告 | `python3 scripts/data/gen_reports.py <json> hard` | 19 份报告 `hard_success`/`gap`/`hard_stats` 非空 |
| 榜单 | `python3 scripts/data/make_leaderboard.py <json> hard --run 45503556969` | 生成 `leaderboard/leaderboard.hard.json` |
| 门禁 | `check_reports` / `check_leaderboard`（`n==50` 强制） | 全绿 |
| 提交 | 走 API 推送（本地无 push 凭证） | CI lint 绿 |

### 阶段 A5（B1 结束后同一开机窗口）
| 项 | 设定 | 验收 |
|---|---|---|
| 派单 | `model-matrix.yml`：`models=x-vla-robotwin2`、`protocol=easy`、`replicate=r2`、`resume=1` | run 启动，目录名 `<task>-easy-r2` |
| 收数 | `collect_matrix.sh x-vla-robotwin2 easy matrix r2` | 只读到 `-easy-r2`，`replicate=r2` |
| 榜单 | `make_leaderboard … --replicate-count 2` | `replicate_count: 2`，并给 `rate_min/rate_max` |
| 不达标 | 若两轮差 > 噪声带（n=50 时约 ±8pp） | 报告标注"单轮勿作结论"，不掩盖 |

### 阶段 决策3（¥20 确定性实验，与 A5 同窗口）
| 项 | 设定 | 验收 |
|---|---|---|
| 实验 | 1 task × 3 集 × 3 轮，同种子 | 3 轮 sqlite 逐集比对 |
| 结论 A（逐集一致） | 回归改为"镜像/bin 变更时跑 3 集"（≈¥8） | 写进 `decisions-*.md` |
| 结论 B（不一致） | 回归改为"变更触发 1 task×50ep"（≈¥105/次） | 同上，不做月度例行 |

---

## 2. 明确不做（附触发条件）

| 项 | 为什么不做 | 何时再做 |
|---|---|---|
| trivy + SBOM | 补的是"镜像有无 CRITICAL"，与当前"能否出数"无关 | 镜像要进生产/对外分发前 |
| GHCR 双推 + CI 构建 | 基座 11.3GB 跨境拉，CI 路径不划算；本地基座命中时 6~11s | 适配器进入稳定期（不再频繁改）后一次做完 |
| renovate 管 pin | 版本变更频率低 | pin 数量 > 10 或出现漏升级事故 |
| actionlint 关 shellcheck/pyflakes | 我们已有独立步骤，避免重复报 | 不改变 |

---

## 3. 变更纪律（针对本次的返工）

1. **先设计后编码**：任何涉及 ≥2 个文件或 ≥1 个 gate 的改动，先写进本文"阶段"表，再动手。
2. **新事实先入 §0**：实测发现的契约先进冻结表，再改代码——避免同一事实被两次"发现"。
3. **一层只改一处**：改适配器就不动路径；改路径就不动参数。一次只变一个维度，跑一次验一次。
4. **长跑必须留档**：`tee` 到文件 + 分阶段 timeout；禁止把整段长跑接 `| tail`。
5. **不许手工抄 digest/版本**：只从工具输出（`buildx imagetools`）写回，避免 `config.digest` 类错误。

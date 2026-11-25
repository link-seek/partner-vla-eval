---
title: ACT / DP 适配器：首次 smoke 手册（B3）
nav_exclude: true
---

# ACT / DP 适配器：首次 smoke 手册（B3）

> 状态：**适配器已写、未验证**。2026-11-24 机器被 B1 Hard 评测占用，没跑过 smoke。
> 目标：把"官方 ckpt → 本仓 harness"这条链路一次性打通，之后 R01 的 20 个 ckpt 都能直接上榜。

## 0. 依赖体检（2026-11-24 实测，`vla-eval-robotwin:0.8.0-ee-slim`）

在 robotwin conda 环境里实际导入过官方 policy 包，结论：

| 项 | 结果 | 含义 |
|---|---|---|
| `policy.ACT.deploy_policy` | ✅ 可导入（`get_model/encode_obs/reset_model` 都在） | ACT 走现成 robotwin 镜像即可 |
| `policy.DP.deploy_policy` | ❌ `ModuleNotFoundError: hydra` | DP 需另烘镜像（还缺 `dill`） |
| `diffusion_policy` | ✅ vendored 在 `policy/DP/diffusion_policy`，`dp_model.py` 自己 append 进 sys.path | 不用另装 |
| `IPython` / `torch` / `cv2` / `h5py` | ✅ 都在 | ACT 的模块级 `e = IPython.embed` 只是引用，不阻塞导入 |
| `detr`（顶层） | ❌ 但 ACT 内部 `from .detr.main` 相对导入可用 | 不影响 ACT |

**因此**：
- ACT 优先用 `vla-eval-robotwin:0.8.0-ee-slim` 起 serve（镜像里已有依赖）
- DP 需要 `vla-serve-robotwin-dp`，把 `hydra`、`dill` 烘进去（V100 禁止现场 pip）

## 0.1 ACT 参数体检（2026-11-24 CPU 实测，已跑通前向）

在镜像里用 CPU（`Module.cuda` 打桩）真跑了一遍官方 ACT：

```
camera_names = ['head_cam','left_cam','right_cam']
number of parameters: 31.35M
constructed in 4.0s
call1: raw=(1,14) flat=14 1.6s finite=True     ← 首次推理
call2: raw=(1,14) flat=14 0.0s  finite=True     ← 命中 chunk 复用（query_frequency 生效）
call3: raw=(1,14) flat=14 0.0s  finite=True
reset_model → 再取仍 14 维
ACT_CPU_SMOKE_OK
```

**过程中踩到两个坑（已修进适配器）**：

| 坑 | 现象 | 根因 | 修法 |
|---|---|---|---|
| 缺 `dropout` | `AttributeError: 'Namespace' object has no attribute 'dropout'` | `deploy_policy.yml` 不含 detr parser 的字段，官方靠 task config 补 | 默认值改用 `get_args_parser()` 的默认值打底，再覆盖 yml 项 |
| `camera_names` 为空 | `torch.cat(): expected a non-empty list` | `detr_vae.forward` 按 `args.camera_names` 长度逐个索引摄像机位 | 显式设 `["head_cam","left_cam","right_cam"]` |

> 注意：官方 `build_ACT_model_and_optimizer` 里有硬编码 `model.cuda()`，**CPU 上必挂**——
> 这个 CPU 体检靠 `torch.nn.Module.cuda = lambda self,*a,**k: self` 打桩才跑通。
> 真实部署走 GPU，不需要打桩。

### 真实 ckpt 实测（2026-11-24，官方 `Avada11/RoboTwin-Model-AgileX-ACT`）

下载了 `click_bell/demo_clean-100/100/`（ckpt 321MB + dataset_stats.pkl 6.3KB），CPU 打桩加载：

```
number of parameters: 78.51M          ← hidden_dim=512（比 parser 默认 256 大一倍）
Loaded normalization stats from dataset_stats.pkl
dec_layers=6: missing=0 unexpected=18   ← 少建一层 decoder
dec_layers=7: missing=0 unexpected=0    ← 完全对上
call1: flat=14 2.0s finite=True range=[-0.447,1.011]
```

**四个必须的配置（`deploy_policy.yml` 只给了其中两个）**：

| 项 | 值 | 来源 |
|---|---|---|
| `dropout` | 0.1 | detr parser 默认（yml 没有） |
| `camera_names` | `["head_cam","left_cam","right_cam"]` | act_policy 硬编码（yml 没有，parser 默认空） |
| `hidden_dim` / `dim_feedforward` | 512 / 3200 | yml 有 |
| `dec_layers` | **7** | yml 没有，parser 默认 6 —— 只有比对 ckpt 才知道 |

**还有一个文件名坑**：官方 ckpt 叫 `policy_epoch_6000_seed_100.ckpt`，
而 `deploy_policy` 的加载逻辑只认 `policy_last.ckpt` → 找不到就**告警后继续用随机权重**（静默错误）。
所以适配器加了 `ckpt_file` 参数：显式给了就自己 `load_state_dict`，
并对 `missing`/`unexpected` 严格断言，不一致直接报错而不是静默跑。

### 官方 ACT 仓库的覆盖（影响榜单设计）

该仓库只有 **10 个 task**（adjust_bottle / beat_block_hammer / click_alarmclock / click_bell /
lift_pot / open_laptop / open_microwave / place_container_plate / place_empty_cup / place_shoe），
本考场 5 个里只有 **adjust_bottle、click_bell** 有 ckpt（`grab_roller` / `place_phone_stand` /
`handover_block` 都没有）。

→ ACT 在榜上最多 2/5 格，且与 CogACT 的 3 格、X-VLA 的 5 格都不同，**三家覆盖各不相同**。

### GPU 上真实加载 + 前向（2026-11-24，直接在 GPU0 验，不跑环境）

```
GPU load: 10.5s
model device: cuda:0
predict: shape=(1, 14) dtype=float32 0.73s finite=True
act_ckpt 加载: missing=0 unexpected=0（适配器内 strict 断言通过）
```

所以 ACT 侧**只剩"跑满一整集"没验**（要 SAPIEN 环境，会与正在跑的 Hard 评测抢 GPU）。

### 关于 `vla-eval test -c`：不适用（重要）

试过用 `vla-eval test -c <serve yaml>` 做快速 smoke，**跑不通，且不是我们的 bug**：

```
observation_failed: KeyError: '观测缺 joint_state'
```

原因：该命令造的是**通用**观测 `{"state": zeros(8)}`（`cli/smoke.py:314`），
与 aloha 的 14 维无关。所以 14 维机器人策略**不能用它做 smoke**，
唯一有效路径是 1 task × 1ep 真跑（runbook §3）。

顺带修正一条接口细节：`get_observation_params() → {"send_state": True}`
在**评测路径**生效（日志会出现 `Auto-configured from model server: send_state=True`），
但 `test` 路径不看它；两种都写上最稳（spec 里也加了 `joint_state`）。

## 0.2 前置

- 0002 空闲（`nvidia-smi` 两卡都空；`docker ps` 没有 cogact-serve / kind_*）
- 本地有 `vla-eval-robotwin:0.8.0-ee-slim` 与一个能起 serve 的镜像
  （ACT/DP 依赖 `detr`、`diffusion_policy`，在 robotwin 镜像里；若 serve 镜像缺，
  需先按 `docker/Dockerfile.serve-*` 的套路烘一个 `vla-serve-robotwin-act`）

## 1. 确认官方代码路径

```bash
docker run --rm --entrypoint bash swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-robotwin:0.8.0-ee-slim -c '
  ls -d /app/RoboTwin/policy/ACT /app/RoboTwin/policy/DP
  sed -n "1,40p" /app/RoboTwin/policy/ACT/deploy_policy.yml'
```

要确认三件事（决定 serve yaml 填什么）：
1. `action_dim`（默认 14）
2. `ckpt_dir` 的约定：ACT 读 `<ckpt_dir>/policy_last.ckpt` + `<ckpt_dir>/dataset_stats.pkl`
3. DP 读 `<task>-<ckpt_setting>-<expert_data_num>-<seed>/<checkpoint_num>.ckpt`

## 2. 起 serve（1 task）

```bash
# ACT
docker run -d --name robotwin-act-serve --gpus '"device=0"' --network host \
  -v $PWD/configs:/work/configs:ro -v /root/robotwin-train:/root/robotwin-train:ro \
  -w /work/harness "$SERVE_IMAGE" \
  vla-eval serve -c /work/configs/model_servers/serve-robotwin-act.yaml
docker logs -f robotwin-act-serve      # 等 "serve UP"
```

判据：
- 日志出现 `Loaded policy weights from ...policy_last.ckpt`（ACT）
- 端口 8000 可连
- 不出现 `Spec mismatch`（出现就停手，先对 `reference/action-mapping.md`）

## 3. 跑 1 task × 1 ep

```bash
python3 - <<'PY'  # 或用现成的 run yaml
PY
TASKS=grab_roller EPISODES=1 SHARDS=1 bash scripts/ci/ci_robotwin_full.sh
```

要看的三行：
- `Spec validation passed (server↔benchmark compatible)`
- `[1/1] grab_roller ep0: SUCCESS|FAIL`
- `chunk_exit=0`

## 4. 通过标准（三条全满足才算 B3 完成）

1. serve 起来且权重加载成功（日志有 `Loaded policy weights`）
2. 1ep 跑完不抛异常，`chunk_exit=0`
3. `aggregate.json` 有 `episodes[0].metrics`（哪怕是 fail，也要有判定而不是 error）

> 允许 FAIL：单集会 0 分很常见（噪声 ±100pp）。**不允许的是 ERROR / spec mismatch / 动作维度错**。

## 5. 常见失败与对策

| 现象 | 原因 | 对策 |
|---|---|---|
| `ModuleNotFoundError: detr` / `diffusion_policy` | serve 镜像没烘依赖 | 从 robotwin 镜像派生一个 serve 镜像，或直接用 robotwin 镜像起 serve |
| `KeyError: head_camera` | 考场相机名与 serve 不一致 | 对 `reference/action-mapping.md` |
| `策略返回 15 维动作，与 action_dim=14 不符` | 官方 ckpt 不是 aloha-agilex 14 维 | 换 ckpt 或改 `action_dim` |
| 动作全程不动 | 图像通道/归一化错（CHW vs HWC、0-1 vs 0-255） | 见适配器 `_to_robotwin_obs` 的三个分支 |
| `ACT 需要 usr_args 的 ['task_name']` | DP/ACT 参数混填 | 看 `deploy_policy.yml` 对应段 |

## 6. 跑通之后

1. 在 `configs/registry/model-registry.json` 把 `act-baseline` / `dp-baseline`
   的 `status` 从 `dropped` 改成 `verified`，补 `ckpt_revision`
2. 进 `model-matrix.yml` 跑 5 task（`weight_type` 已是 `finetuned`，会自动与 shared 分组）
3. 更新 `docs/tutorial/leaderboard.md` 的准入表


---

## 附：部分结果救援（2026-11-25 实测通过）

run 中途崩了不要重跑，先救：

```bash
# 机器上（sqlite 还在 results/ 里）
S=$(find results -name 'recording-*.sqlite' | head -1)
TARGET_EPISODES=50 bash scripts/data/rescue_partial.sh "$S" /tmp/rescue
```

实测（正在跑的 Hard grab_roller，12 集时的快照）：

```
[rescue] grab_roller: 8/12 完成度 12/50 (24%) [部分]
[rescue] 注意：这是部分结果，只能进附录，不能当正式数
```

要点：
- 用 `sqlite3 .backup` 取一致性快照（没有 sqlite3 时退化为 `cp`）
- `vla-eval export` 支持增量："Rerun to include subsequently recorded episodes"
- 下次同配置重跑时加 `resume=1`（workflow 输入），会跳过 `results_fresh`，
  sqlite 保留 → 已完成的集数不会被重复跑掉

---

## 坑 7（2026-11-25，最贵的一个）：漏掉官方 encode_obs 的 640×480 resize

**症状**：整集跑完 400 步、无报错、无 Spec mismatch，但结果 **0/1**（连跑两次都是）。

**根因**：考场 `task_config/demo_clean.yml` 里 `head_camera_type: D435` → 相机输出 **320×240**；
官方 `policy/ACT/deploy_policy.py::encode_obs` 会先
`cv2.resize(..., (640, 480), interpolation=cv2.INTER_LINEAR)` 再送策略。
我们的适配器直接把 320×240 转成 CHW 就喂进去——ACT 按 640×480 训练，等于跑半分辨率图。

**证据（对照实验，同配置同种子）**：

| 版本 | 结果 |
|---|---|
| 缺 resize | 0/1（2 次） |
| 补 `resize_bilinear(..., 640, 480)` | **1/1** |

同一次运行的 serve 侧日志坐实了尺寸：
```
[dbg] image shapes={'head_camera': (240, 320, 3), ...}
```

**为什么难发现**：harness 的 `IMAGE_RGB = DimSpec("image", 0, "rgb_hwc_uint8")` 维度是 0，
**不会**替你 resize；DETR/ResNet 主干吃任意尺寸都能跑通，所以既不报错也不 mismatch，
只是分数归零。

**修法**：`scripts/model_servers/robotwin_obs.py::RESIZE_WH = (640, 480)`，
`build_policy_obs` 里 `to_chw01(resize_bilinear(img, *RESIZE_WH))`。
`resize_bilinear` 用 numpy 实现（零依赖，可单测），10 项 resize 单测进 lint。

**排查顺序建议**（下次换策略/换考场时）：
1. 先比对官方 `encode_obs` 的**每一个**预处理步骤（resize / 归一化 / 通道序 / dtype）
2. 再比对 spec 键名
3. 最后才怀疑模型权重

## 坑 8：调试日志用了 os.environ 但没 import os

`NameError: name 'os' is not defined` —— 单测碰不到、`bash -n` 碰不到，只有真跑才崩。
已由 lint 的 `ruff --select F821` 拦住。

---

## 镜像构建：为什么不在 GitHub runner 上打（2026-11-25 实测选择）

`build-serve.yml` 打 robotwin 基座镜像时，runner 需要先把 **11.3GB** 的 bench 镜像从
SWR（cn-north-4）**跨境**拉到 Azure。2026-11-25 实测：跑了 **约 18 分钟**仍停在 `Build + push`
（拉取阶段，日志运行中不可下载，看不到进度条），据此判断跨境拉 11.3GB 不划算，改为在 0002
本机构建（镜像已在本地，无需拉取）+ 推同区 SWR：

| 方式 | 耗时 |
|---|---|
| GitHub runner（跨境拉 11.3GB） | 约 18 min 未完成（已取消；当时无法判断还需多久） |
| 0002 本地构建（COPY + pip） | ACT **6s** / DP **11s**；push 仅传新增层 |

这属于**构建**，不是评测/验证负载（不占 GPU、不起仿真），所以在 0002 上做不违反
"测试负载只跑临时 runner"的约束；B1 仍在 GPU1 上照常跑。

**代价**：`build-serve.yml` 里的两个新 tag 目前只在手动路径验证过，CI 那条路没跑通（跨境拉基座慢）。
如果以后要在 CI 里重建，建议先把基镜像也同步到可快速拉取的位置，或给 runner 加缓存。

## DP 的依赖清单（实测，别再逐个试）

只用 hydra/dill 不够。按报错顺序踩到的坑与最终可用组合：

```
hydra-core 1.3.8, dill 0.4.1, einops 0.8.2, zarr 2.18.3,
numcodecs 0.13.1, numba 0.60.0, atomics 1.0.3, diffusers 0.27.2
```
- `diffusers>=0.34` 会调 `torch.accelerator`（需 torch≥2.6），本镜像 torch 2.4.1 → 必须 0.27.x
- 推断路径**不需要** pytorch3d / r3m / robomimic / wandb / pygame / pymunk（import 测试证明）
- 依赖正确性已写进 Dockerfile 的**构建期自检**：`import policy.DP.deploy_policy` 失败则构建失败

## 坑 9：健康检查用了 `/dev/tcp`，在容器里永远 unhealthy

**症状**：前置检查全过、镜像在本地、端口空闲，但 `serve 未通过健康检查`，看起来像"服务起不来"。
实际服务**好得很**——日志里 `server listening on 0.0.0.0:8031` 清清楚楚。

**根因**：`docker run --health-cmd` 由容器内的 **`/bin/sh`（dash）** 执行，
而 `/dev/tcp/...` 是 **bash 专有**特性：
```
sh: 1: cannot create /dev/tcp/127.0.0.1:8031: Directory nonexistent
```
（同一个容器里 `bash -c '(echo > /dev/tcp/...)'` 是通的 → 说明不是网络问题，是 shell 问题。）

**正确做法**：打服务自己的 HTTP 端点（serve 会打印 `HTTP config endpoint at http://…/config`）：
```bash
--health-cmd "curl -fsS -o /dev/null http://127.0.0.1:$PORT/config || exit 1"
```
实测 `curl … /config` → HTTP **200**。

**方法论**：探针本身也要验证。别假设"等我用 bash 试是通的，健康检查也一定通"——
执行探针的 shell 不是我所在的 shell。

## 坑 10：断言看错了字段，报错的一集被判成 PASS

`click_bell_aggregate.json` 里**没有** `episodes[].error` 这个键。真实的"有没有报错"在：

- task 级：`num_errors`
- 每集：`failure_reason`（如 `model_act`）+ `failure_detail`（traceback）

我的 smoke 后置断言最初只看 `e.get("error")` → 恒为 0 → DP 明明 `⚠ 1 episodes errored` 还打印 `errors=0`、退出码 0。
**这是最坏的一类错：门禁说绿，结果其实挂了。** 已改为读 `num_errors` 与 `failure_*`，有错就非零退出并打印 detail 尾部。

教训：**断言必须读被测系统自己的判定字段**，不能读我"以为"的字段名。

## 坑 11：ACT 的图像处理不能套给 DP（两个策略契约不同）

**症状**：DP 每集 `failure_reason=model_act`，`failure_detail` 先是空消息的 `AssertionError:`，
改一处后又变成 `KeyError: 'left_cam'`。

**真实契约（必须读调用链，别只看一层）**：

| | 送几路相机 | 是否 resize | 依据 |
|---|---|---|---|
| ACT | 3 路（head/left/right） | **是**，→ 640×480 | 官方 `encode_obs` 显式 `cv2.resize` |
| DP | **3 路**（缺一路就 KeyError） | **否**，保持原生 240×320 | `DPRunner.get_action` 里显式读 head/left/right + agent_pos；`obs_encoder` 的 `rgb_keys` 只有 head_cam，且 `key_shape_map={'head_cam': (3,240,320)}` |

两个错我各犯一次：
1. 按 ACT 的做法给 DP 也 resize 到 640×480 → encoder 的 `assert img.shape[1:] == key_shape_map[key]` 失败（**空消息**，极难查）
2. 以为"encoder 只用 head_cam，那就只送 head_cam" → `DPRunner` 在更外层就把 left_cam 取出来了，`KeyError`

**教训（这次是真的可复用）**：判断"要给什么输入"，要顺着**调用链**从最外层读到最内层——
最外层（runner）决定**需要哪些键**，最内层（encoder）决定**数值形状**。只看一层必然来回改。

**另外**：`robot_dp_14.yaml` 里 `shape_meta` 写 `[3,-1,-1]`，那是训练配置占位；
真实期望在 **ckpt** 里，必须载入后打印 `key_shape_map`。

## 坑 12：DP 一次返回 6 步动作，被当成"一步 84 维"

**症状**：`ValueError: 策略返回 84 维动作，与 action_dim=14 不符`（84 = 6×14）。

**根因**：两个策略的返回形态不同，且官方用法也不同：

| 策略 | 返回 | 官方怎么用 |
|---|---|---|
| ACT | 单步 `(14,)` | 每步推理一次（内部有 `query_frequency`/`temporal_agg` 缓冲） |
| DP | 整块 `(n_action_steps, 14)` = `(6,14)` | `for action in actions: take_action(action)` —— **开环执行 6 步后**才重新推理 |

harness 是每步问一个动作，所以适配器必须：
1. 维护动作队列（`deque`）
2. **队列空时才调 `get_action`**（等价官方的"整块开环"；每步都调等于每 6 步浪费 5 次推理，且行为偏离官方）
3. 每步 `popleft` 一个 14 维
4. episode 开始 `_reset` 时清队列（否则跨集会串动作）

切块逻辑做成纯函数 `split_action_chunk(arr, action_dim)`，配 4 项单测（单步/整块/顺序/不整除报错）。

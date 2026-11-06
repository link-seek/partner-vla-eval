---
title: 伙伴 01：配准交付
parent: 评测教程
nav_order: 3
---

# 伙伴 01：认模型，对号入座，配准交付

> 目标：把你训好的模型改成 harness 能直接跑的 serve yaml（不教训模型，只教交模型）。
> 时间：30 分钟 ｜ 前置：读完 `quickstart`。
> 你将得到：改好的 serve yaml + 提交包（权重版本 + ★项 + 表单）。

当前只开 RobotWin。官方已有 RobotWin 配置的只有两族，从对应模板改★项即可，其余字段不动；不在表里的模型先提需求，不要自己写。

与上游的关系：上游 [CONTRIBUTING 六步](https://github.com/allenai/vla-evaluation-harness/blob/main/CONTRIBUTING.md#adding-a-model-server)里，伙伴只涉及第 5 步（`configs/model_servers/<name>/`）；第 1–4 步是实现，官方支持已覆盖；第 6 步由 smoke 代验。卡住时可按节号去上游问。

先把表单拿下来（后面照着填）：

```bash
git clone https://github.com/link-seek/partner-vla-eval.git
cd partner-vla-eval
```

## 官方支持哪些

| 模型族 | 官方 RobotWin 配置 | 备注 |
|---|---|---|
| DB-CogACT（Dexbotic） | `db_cogact/robotwin2.yaml` | 上游官方 |
| X-VLA | `xvla/robotwin.yaml` | RobotWin 支持由 xieyucheng 提供 |
| LeRobot 系（π0/π0.5/GR00T/SmolVLA…） | 无 | 上游有桥和 10 份配置，但全是 LIBERO（单臂 Franka、7 维）口径 |
| CogACT（Microsoft 原版，7-DoF） | 无 | 只有 RT-1/Bridge 配置 |
| 其他（OpenVLA / OFT / Pi0…） | 无 | 上游有 server，但没有 RobotWin 配置 |

没有你的族 → 提需求给 xieyucheng（说明模型、权重、目标榜），官方补上后再回来改 yaml；不要自己写 server 或配置。

## 怎么改：B / C 两例

### B：DB-CogACT

官方 [`db_cogact/_base.yaml`](https://github.com/allenai/vla-evaluation-harness/blob/main/configs/model_servers/db_cogact/_base.yaml)（不动）+ [`robotwin2.yaml`](https://github.com/allenai/vla-evaluation-harness/blob/main/configs/model_servers/db_cogact/robotwin2.yaml)（改★）：

```yaml
# _base.yaml（不动）
script: "src/vla_eval/model_servers/dexbotic/cogact.py"
args:
  port: 8000
  use_text_template: true
```

```yaml
# robotwin2.yaml（改★）
extends: _base.yaml
args:
  model_path: Dexmal/robotwin-db-cogact/adjust_bottle  # ★按 task 分头逐个列
  chunk_size: 16                                        # ★照抄对应榜文件
  camera_keys: '["head_camera", "left_camera", "right_camera"]'  # ★照抄
  use_text_template: false                              # robotwin2 覆写，照抄
```

### C：X-VLA

官方 [`xvla/_base.yaml`](https://github.com/allenai/vla-evaluation-harness/blob/main/configs/model_servers/xvla/_base.yaml)（不动）+ [`robotwin.yaml`](https://github.com/allenai/vla-evaluation-harness/blob/main/configs/model_servers/xvla/robotwin.yaml)（改★）：

```yaml
# _base.yaml（不动）
script: "src/vla_eval/model_servers/xvla.py"
args:
  denoising_steps: 10
  port: 8000
```

```yaml
# robotwin.yaml（改★）
extends: _base.yaml
args:
  model_path: "2toINF/X-VLA-RoboTwin2"  # ★照抄对应榜文件
  benchmark_profile: "robotwin"         # ★照抄
  domain_id: 6                          # ★官方 recipe
  chunk_size: 30                        # ★官方值（不是 16，别按 CogACT 脑补）
```

**填★注意**：

- `model_path` 按 task 分头的逐个列齐，缺头的 task 排不上。
- `chunk_size` 照对应族：B 是 16，C 是 30，别互相套。
- `script`/`extends` 不动；`fast_init` 是 benchmark 侧参数（`action_type: ee` 时自动关），不在 serve yaml 里。
- dtype 不是 yaml 字段：X-VLA 固定 fp32，DB-CogACT 在 V100 用 fp16，填进表单备注。

## 交给我们

有 GPU 先跑 `vla-eval test -c <你的serve.yaml>`；没有 GPU 跳过，smoke 代验。

然后联系 xieyucheng，发三样（标题 `【评测对接】<模型名>`）：①权重版本（Hub ID + 精确 commit，分支名不行；本地目录给快照哈希；OBS 地址保证能拉取；私仓先给 `link-seek` 开授权）②★项 ③对接表单（[docs/partner-onboarding.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/partner-onboarding.md)，不知道的空着）。

xieyucheng 确认后进 smoke（1 task×1ep，1 天内给 spec 对齐报告），通过后进 [02-smoke.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/tutorial/partner/02-smoke.md) 的全量。

**评测从哪一步开始**：从你交来可跑的 yaml 开始——smoke 通过 → 全量。模型不在官方支持列表时，先补支持（提需求），补完再交 yaml。

---
title: 伙伴 01：配准交付
parent: 评测教程
nav_order: 3
---

# 伙伴 01：认模型，对号入座，配准交付

> 目标：把你训好的模型配准成可上榜形态（不教训模型，只教交模型），
> 产出一份 harness 能直接吃掉的 serve yaml。
> 时间：30 分钟 ｜ 前置：读完 `quickstart` ｜ 准备：一台能上网的电脑，python3 即可
> （无第三方依赖，不下权重，不用 GPU）。
> 你将得到：probe 输出 + 路线归位 + ★项配准 + serve yaml + 对接帖。

## 开场：同一个 pi0，两条路（先看省在哪）

| 环节 | 官方原生（Robotwin XPolicyLab/`policy/`） | harness（我们） | 省了什么 |
|---|---|---|---|
| 模型代码 | 手写 `deploy_policy.py` 六函数（约 200 行） | 0 行（bake 好了） | 写代码 |
| 模型环境 | 自装 policy conda env | serve 镜像 pull 即用 | 装 env |
| 仿真环境 | 自装 robotwin env | env 镜像 pull 即用 | 装 env |
| 跑测循环 | `eval.sh` 十几个参数，循环自己写 | 两个 yaml + dispatch | 写循环+记分 |
| 口径信息 | 散三处（代码/yml/sh） | 收拢成 serve ★项 | 不省，但收拢了 |
| 结果 | `eval_result/` 本地 | OBS + aggregate（跨 task 可比） | 可比性 |

合计：200 行代码 + 2 个 env + 10+ 参数 → 2 个 yaml。**省的是实现，不省的是口径**：
`ckpt_setting`（训的哪份数据）vs `task_config`（测的什么环境）在官方命令行里
本来就是两个独立参数。

## 准备

```bash
git clone https://github.com/link-seek/partner-vla-eval.git
cd partner-vla-eval
python3 --version   # 3.8+ 即可
```

## 操作

与上游 [CONTRIBUTING（Adding a Model Server）](https://github.com/allenai/vla-evaluation-harness/blob/main/CONTRIBUTING.md#adding-a-model-server) 六步 1:1 对照：节号即上游节号，缺的是代码实现，留的是填表动作。卡住时拿着节号去上游问。

### §1 定范围：找你的路线

（自己判断）定完再往下读，别的一行都不用看：

| 模型类型 | 走这条路线 |
|---|---|
| LeRobot 系 ckpt（单臂） | 规划接入方向：字段见上游 lerobot README，桥模板换 checkpoint 即可；当前 smoke/全量只开 RobotWin |
| DB-CogACT / CogACT | cogact 模板（§3），`model_path` 按 task 分头 |
| X-VLA 官方 ckpt | X-VLA 模板（EE 口径，§3），`domain_id` 按官方 recipe |
| 上游已接入的其他（OpenVLA / OFT / RDT / Pi0…） | 对应上游模板，表单里注明 |
| 以上都不是 | 三退路：①先套 LeRobot 桥（任意 `PreTrainedPolicy` 即插即用）→ ②照上游 [CONTRIBUTING（Adding a Model Server）](https://github.com/allenai/vla-evaluation-harness/blob/main/CONTRIBUTING.md#adding-a-model-server)（人看）/`add-model-server` skill（agent 用）加 server（约 50 行，我们 [#168](https://github.com/allenai/vla-evaluation-harness/pull/168) 有先例）→ ③直接发帖，表单空着，我们帮你看 |

### §2 备权重：跑 probe 核对

（拿不准时用；路线笃定的可跳过，直接人答★项）：

```bash
python3 scripts/spec_probe.py <本地目录>    # 主用法：只读 config.json + safetensors 文件头，不加载权重体。
                                            # 权重先落盘（你给文件 / 我们从 OBS 拉），probe 只验盘上的东西。
python3 scripts/spec_probe.py <你的HF-ID>   # 备用法：权重在 Hub 上；私仓加 --token $HF_TOKEN
```

权重在 OBS 上：不用跑 probe，直接把地址贴进表单——我们内网拉到 V100 落盘，
落盘后跑的还是上面的本地分支。期望输出（以 `lerobot/pi05_libero_finetuned` 为例）：

```text
## spec_probe: lerobot/pi05_libero_finetuned
- card tags: ['lerobot', 'safetensors', 'vision-language-action', ...]
- gated: False  private: False
- main HEAD: 7152f13e34c6
- config 架构键: {"chunk_size": 50, "n_action_steps": 50, ...}
- index 文件: 无（单文件 safetensors 或其它格式，需整包看头）

## 仍需人答 / smoke 实测（机器读不到）
- 相机名、状态字段需求、chunk 语义、特殊依赖（requirements/model card 无则试）
- 最终口径以 smoke 实测为准（config.json 会撒谎，见 SmolVLA 6-D/7-D）
```

### §3 对口径：填★表

按你的路线表填★项（官方字段是全集，★是准入子集——错一项就 0 分或起不来；
 ★之外的抄官方默认，不动）：

**路线 B：DB-CogACT**（官方 `db_cogact/_base.yaml` + `robotwin2.yaml` 原样）：

| 字段 | 官方 | 怎么填 |
|---|---|---|
| script | `src/vla_eval/model_servers/dexbotic/cogact.py`（base 定死） | 不动 |
| extends | `_base.yaml`（port 8000、use_text_template true 被继承） | 不动 |
| ★ model_path | `Dexmal/robotwin-db-cogact/<task>`（官方逐 task 覆写） | 按 task 分头逐个列；CI 转本地子目录绝对路径 |
| ★ chunk_size | 16（robotwin2） | 照抄对应榜文件 |
| ★ camera_keys | `["head_camera", "left_camera", "right_camera"]` | 照抄 |
| use_text_template | base 默认 true；robotwin2 覆写 false | 照抄对应榜文件 |
| ★ dtype（我方） | 官方 yaml 不写（由镜像定）；V100 单卡走 fp16 | 填 fp16，写进表单 |

**路线 C：X-VLA**（官方 `xvla/_base.yaml` + `robotwin.yaml` 原样）：

| 字段 | 官方 | 怎么填 |
|---|---|---|
| script | `src/vla_eval/model_servers/xvla.py`（base 定死） | 不动 |
| ★ model_path | `2toINF/X-VLA-RoboTwin2`（robotwin.yaml；其他榜见对应文件） | 照抄对应榜文件 |
| ★ benchmark_profile | `robotwin` | 照抄 |
| ★ domain_id | 6（官方 recipe 定 embodiment prompt） | 照抄官方 recipe |
| ★ chunk_size | 30（官方值；不是 16，别按 CogACT 脑补） | 照抄 |
| denoising_steps | 10（base 默认） | 不动 |
| ★ dtype（我方） | 官方 yaml 不写；一律 fp32 | 填 fp32，写进表单 |

注意：`fast_init=false` 是 run 侧 benchmark params，不在 serve yaml 里。

**路线 A：LeRobot 桥**（单臂，规划接入方向）：字段见上游 lerobot README 参数表，桥模板换 checkpoint 即可；★项为 policy_type/checkpoint/image_keys/state_key/chunk_size。

对模板改出 serve yaml（复制 §1 定下来的那一例，只改★项）：

```yaml
# DB-CogACT（官方 db_cogact/robotwin2.yaml + _base.yaml 原样）
script: "src/vla_eval/model_servers/dexbotic/cogact.py"
args:
  model_path: Dexmal/robotwin-db-cogact/<task>   # ★按 task 分头
  chunk_size: 16                                  # ★照抄对应榜文件
  camera_keys: '["head_camera", "left_camera", "right_camera"]'   # ★照抄
  use_text_template: false                        # robotwin2 覆写
```

```yaml
# X-VLA（官方 xvla/robotwin.yaml + _base.yaml 原样）
script: "src/vla_eval/model_servers/xvla.py"
args:
  model_path: "2toINF/X-VLA-RoboTwin2"   # ★照抄对应榜文件
  benchmark_profile: "robotwin"          # ★照抄
  domain_id: 6                           # ★官方 recipe
  chunk_size: 30                         # ★官方值
  denoising_steps: 10                    # base 默认，不动
```

### §4 状态并发：缺省

chunk/state 由模板定，不填。有特殊需求才加：如 GR00T 的 `embodiment_tag`、MolmoAct2 的 `norm_tag` 走 `policy_kwargs`，写进表单备注；`max_rows`/`max_batch_size` 不碰，由 serve 镜像定。

### §5 校验交接：test -c + 发帖

有 GPU 先跑 `vla-eval test -c <你的serve.yaml>`（上游自带冒烟）；无 GPU 直接发帖，smoke 代验。发帖：复制 [partner-onboarding.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/partner-onboarding.md) 里的对接表单，把 probe 输出
 + ★项贴进去，不知道的空着。去[对接区发帖](https://github.com/link-seek/partner-vla-eval/discussions)，标题 `【评测对接】<模型名>`。
 1 天内给 spec 对齐报告，通过进 smoke。

## 检查点

- [ ] probe 输出无 `仓库不可读`？401/403 = 私仓没开权限，先给 `link-seek` 授权（打回 Top 2）。
- [ ] 本地目录无 commits？交付时注明版本（文件夹哈希/时间/自述三选一），否则复现翻车。
- [ ] 分头子目录 probe 报出来了？表单第 6 类（权重）照抄。
- [ ] 发帖 Top 3 避开：确切 commit（probe 第一步就是干这个的）、权重要授权的开好权限、
 按 task 分头的给全（= 权重★项没做）。

## 原理

* **模板来源**：三例都是上游 harness 同名配置，我们只做钉版适配（镜像、mirror、
 本地路径）。上游 20+ 模型 server 分 ✓ 已复现 / ◇ 已接入待复现两档。
* **★即 6 项概念**：权重/动作/相机/状态/chunk/dtype——概念层统一，字段名按路线走。
 6 项不是上游标准，是我们的准入子集（错一项就 0 分/起不来）；全集见各模型 README。
* **serve yaml = 评测态定义**：哪个权重 + 什么参数跑起来，不含训练信息——上游
 "接一次模型" = server 实现（哪一族）+ serve yaml（哪一个）+ 权重。训练口径管分数可比，
 见 03 披露清单，各管一半。
* **dtype**：fp16 不是 fp32 廉价版。X-VLA fp16 首推理即崩（六轮 29/30 vs 0/30，
 精度对照；官方训练用 bf16）；CogACT fp32 首 forward 即 OOM（31GB）。0 分先查 dtype。
* **口径熔断**：EE 当关节喂，benchmark 硬截 `act[:14]`——400 步跑满全 0 分零异常，
 spec warning 见 quickstart 检查点。
* **三段式**：`from_pretrained` 不认 `repo/subdir`，CI 先 snapshot 再 `sed` 生成本地版；
 你写三段式一样能发帖。要跑哪个 task 就用哪个 task 的头。
* **本地校验**：见 §5（`vla-eval test -c` 前置校验）。
* **骨架对照**：本篇 = CONTRIBUTING 六步的 1:1 填表版（§4 缺省走模板默认）；字段语义以官方 yaml/README 为准，本篇只做准入标记（★）。卡住时按节号去上游问，不用只找我们。
* **probe 的边界**：不假设目录结构（有什么报什么）；config.json 数字仅参考
 （训练切分≠serving 节拍；SmolVLA 6-D/7-D 前车之鉴）。最终口径以 smoke 为准。

## 下一步

帖子通过 → [02-smoke.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/tutorial/partner/02-smoke.md)（1 task×1ep，拿 spec 对齐报告）。

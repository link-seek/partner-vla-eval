---
title: 伙伴 01：配准交付
parent: 评测教程
nav_order: 3
---

# 伙伴 01：认模型，对号入座，配准交付

> 目标：把你训好的模型配准成可上榜形态（不教训模型，只教交模型），
> 产出一份 harness 能直接吃掉的 serve yaml。
> 时间：30 分钟 ｜ 前置：读完 `quickstart`。
> 你将得到：路线归位 + serve yaml + 提交包（权重版本 + ★项 + 表单）。

harness 把官方原生要写的（约 200 行适配器 + 两个 env + 十几个参数）收拢成两个 yaml。
**省的是实现，不省的是口径**：`ckpt_setting`（训的哪份数据）vs `task_config`
（测的什么环境）在官方命令行里本来就是两个独立参数。
下文六节与上游 [CONTRIBUTING（Adding a Model Server）](https://github.com/allenai/vla-evaluation-harness/blob/main/CONTRIBUTING.md#adding-a-model-server) 1:1 对照：节号即上游节号，缺的是代码实现，留的是填表动作。卡住时拿着节号去上游问。

先把模板和表单源文件拿下来（后面照着改、对着填）：

```bash
git clone https://github.com/link-seek/partner-vla-eval.git
cd partner-vla-eval
```

### §1 定范围：按模型类型找你的路线，定完再往下读。

<details>
<summary>路线对照表</summary>

| 模型类型 | 走这条路线 |
|---|---|
| LeRobot 系 ckpt（单臂） | 规划接入方向：字段见上游 lerobot README，桥模板换 checkpoint 即可；当前 smoke/全量只开 RobotWin |
| DB-CogACT / CogACT | cogact 模板（§3），`model_path` 按 task 分头 |
| X-VLA 官方 ckpt | X-VLA 模板（EE 口径，§3），`domain_id` 按官方 recipe |
| 上游已接入的其他（OpenVLA / OFT / RDT / Pi0…） | 对应上游模板，表单里注明 |
| 以上都不是 | 三退路：①先套 LeRobot 桥（任意 `PreTrainedPolicy` 即插即用）→ ②照上游 CONTRIBUTING（人看）/`add-model-server` skill（agent 用）加 server（约 50 行，我们 [#168](https://github.com/allenai/vla-evaluation-harness/pull/168) 有先例）→ ③直接联系 xieyucheng，表单空着，我们帮你看 |

模板都是上游 harness 同名配置，我们只做钉版适配（镜像、mirror、本地路径）。
上游 20+ 模型 server 分 ✓ 已复现 / ◇ 已接入待复现两档。
</details>

### §2 备权重：权重按"Hub ID 或本地路径 + 精确版本"交，OBS 地址另算我方补充。

<details>
<summary>交付表与版本规则</summary>

上游原文（SKILL §2 + lerobot README）：权重交 **Hub ID 或本地路径**，版本必须
**精确 revision**（验文件，不验"有个快照就行"）。照抄：

| 交付方式 | 交什么 | 版本怎么定 |
|---|---|---|
| Hub ID（官方） | ID + 精确 commit | `git rev-parse` 那串，分支名不行 |
| 本地路径（官方） | 目录 | 快照哈希；按 task 分头的逐个列 |
| OBS 地址（我方补充，离线链路用） | bucket/path | 权限/有效期要够我们拉取 |

私仓先给 `link-seek` 开授权。`from_pretrained` 不认 `repo/subdir` 三段式——写了也照收，
CI 会 snapshot 转本地路径；要跑哪个 task 就用哪个 task 的头。
交之前自查三行：版本精确？权限开了？分头给全了？缺头的 task 排不上，401/403 直接打回。
</details>

### §3 对口径：照你的路线表填★项（官方字段全集的子集），其余抄默认。

<details>
<summary>三路线★表与模板全文</summary>

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

serve yaml 定义的是模型的评测态身份（哪个权重 + 什么参数跑起来），不含训练信息——
上游"接一次模型" = server 实现（哪一族）+ serve yaml（哪一个）+ 权重。
训练口径管分数可比，见 03 披露清单，各管一半。
dtype 先查后疑：X-VLA fp16 首推理即崩（六轮 29/30 vs 0/30，精度对照；官方训练用 bf16），
CogACT fp32 首 forward 即 OOM（31GB）——0 分先查 dtype，不要先怀疑模型。
口径错配必 0 分：EE 当关节喂，benchmark 硬截 `act[:14]`——400 步跑满全 0 分零异常，
spec warning 见 quickstart 检查点。
</details>

### §4 状态并发：缺省，有特殊走 `policy_kwargs` 写表单备注。

### §5 校验交接：有 GPU 先 `test -c`，然后联系 xieyucheng 交三样。

<details>
<summary>提交包与 Top 3</summary>

有 GPU 先跑 `vla-eval test -c <你的serve.yaml>`（上游自带冒烟，见 [CONTRIBUTING Smoke Tests](https://github.com/allenai/vla-evaluation-harness/blob/main/CONTRIBUTING.md#smoke-tests)）；无 GPU 跳过，smoke 代验。然后联系 xieyucheng，把三样（权重版本+★项+表单）发过去（标题 `【评测对接】<模型名>`）：复制 [partner-onboarding.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/partner-onboarding.md) 里的对接表单，把★项贴进去，不知道的空着。提交 Top 3 避开：确切版本、权重要授权的开好权限、按 task 分头的给全（= 权重★项没做）。xieyucheng 确认后进 smoke（1 天内给 spec 对齐报告）：[02-smoke.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/tutorial/partner/02-smoke.md)（1 task×1ep，拿 spec 对齐报告）。
</details>

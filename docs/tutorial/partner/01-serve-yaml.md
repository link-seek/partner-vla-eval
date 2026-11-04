# 伙伴 01：认模型，对号入座，配准交付

> 目标：把你训好的模型配准成可上榜形态（不教训模型，只教交模型）。
> 时间：30 分钟 ｜ 前置：读完 `quickstart` ｜ 准备：一台能上网的电脑，python3 即可
> （无第三方依赖，不下权重，不用 GPU）。
> 你将得到：probe 输出 + 型号归位 + 6 项配准 + serve yaml + 对接帖。
> 读法：先看开场故事（5 分钟），再跟着跑；每段命令下面都贴了期望输出，对不上先停。

## 开场：同一个 pi0，两条路（5 分钟，先看省在哪）

你手里有个 pi0，想上 RobotWin 测个分。官方原生路要自己写适配器、装两个环境、
传十几个参数；harness 路只填两个 yaml。差多少，看表：

| 环节 | 官方原生（Robotwin XPolicyLab/`policy/`） | harness（我们） | 省了什么 |
|---|---|---|---|
| 模型代码 | 手写 `deploy_policy.py` 六函数（`get_model/encode_obs/eval/update_obs/get_action/reset_model`，约 200 行） | 0 行（上游实现 bake 进 serve 镜像） | 写代码 |
| 模型环境 | 自装 policy conda env（torch/cu/依赖版本自己对） | serve 镜像 `docker pull` 即用 | 装 env |
| 仿真环境 | 自装 robotwin env（SAPIEN/CuRobo/任务代码） | env 镜像 `docker pull` 即用 | 装 env |
| 跑测循环 | `eval.sh` 传 task/task_config/ckpt_setting/demos/seed/gpu 十几个参数，种子递增、UnStableError 跳种、ffmpeg 录像自己写 | run yaml 5 项 + dispatch，orchestrator 全包 | 写循环+记分 |
| 口径信息 | 散三处：代码里的 action_type、yml 里的 ckpt 路径、sh 里的 task_config/seed | 收拢成 serve 6★项 | 不省，但收拢了 |
| 结果 | `eval_result/` 本地目录 | OBS + aggregate JSON（跨 task 可比） | 可比性 |

合计：官方路 200 行代码 + 2 个 env + 10+ 参数 → harness 路 2 个 yaml。
**省的是实现，不省的是口径**：`ckpt_setting`（训的哪份数据）vs `task_config`
（测的什么环境）在官方命令行里本来就是两个独立参数——训练口径和评测环境分开填，
两条路都一样，这就是 03 披露清单的来历。

> **原理**：6★项不是多出来的——官方路里同样的问题散在三处（代码里的
> encode_obs/action_type、yml 里的 ckpt 路径、eval.sh 里的 task_config/seed），
> harness 路把它收拢成 serve yaml 里的 6 个字段。所以不是"多填"，
> 是"代码和环境省了，口径省不掉"。专家看到这里应该点头：原来直接接官方要填
> 这么多，现在只剩 6 项。

## 准备

```bash
git clone https://github.com/link-seek/partner-vla-eval.git
cd partner-vla-eval
python3 --version   # 3.8+ 即可
```

## 第一步：找你的路线（自己判断）

| 模型类型 | 走这条路线 |
|---|---|
| LeRobot 系 ckpt（π0.5 / GR00T N1.7 / SmolVLA / MolmoAct2…） | LeRobot 桥模板（第四步 π0.5 例），`checkpoint` 换你的 |
| DB-CogACT / CogACT | cogact 模板（第四步），`model_path` 按 task 分头 |
| X-VLA 官方 ckpt | X-VLA 模板（EE 口径，第四步），`domain_id` 按官方 recipe |
| 上游已接入的其他（OpenVLA / OFT / RDT / Pi0…） | 对应上游模板，表单里注明 |
| 以上都不是 | 三退路：①先套 LeRobot 桥（任意 `PreTrainedPolicy` 即插即用）→ ②照上游 `add-model-server` skill 加 server（约 50 行，我们 #168 有先例）→ ③直接发帖，表单空着，我们帮你看 |

定完路线再往下读，别的一行都不用看。

> **原理**：模板是上游 harness 的同名配置（`script` 指向的
> `src/vla_eval/model_servers/...` 就是上游实现），我们只做钉版适配
> （镜像、mirror、本地路径）。上游 20+ 模型 server 分两档：✓ 已复现 / ◇ 已接入待复现，
> 小众模型没有是常态——所以退路①的桥覆盖面最广，③永远兜底。

## 第二步：跑 probe 核对（拿不准时用）

路线定了，这步是核对说法（名字会骗人：config 写 6-D 实测 7-D 的 SmolVLA、
EE 当关节喂全 0 分的 X-VLA）；路线笃定的可跳过，直接到第三步按你的路线表填★项。

```bash
python3 scripts/spec_probe.py <本地目录>    # 主用法：只读 config.json + safetensors 文件头，不加载权重体。
                                            # 权重先落盘（你给文件 / 我们从 OBS 拉），probe 只验盘上的东西。
python3 scripts/spec_probe.py <你的HF-ID>   # 备用法：权重在 Hub 上；私仓加 --token $HF_TOKEN
```

权重在 OBS 上：不用跑 probe，直接把地址贴进表单——我们内网拉到 V100 落盘，
落盘后跑的还是上面的本地分支（验货同一套）。

期望输出（以 `lerobot/pi05_libero_finetuned` 为例，你的模型换上同格式）：

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

对不上怎么办：

| 现象 | 含义 |
|---|---|
| `仓库不可读` + 401/403 | 私仓没开权限，先给 `link-seek` 授权再跑（打回 Top 2） |
| `config.json: 读不到` | 仓里没 config，按"人答"走，不卡死 |
| commits 段缺失 | API 限流，重跑一次即可 |
| 本地目录无 commits | 精确版本靠交付时注明（文件夹哈希/时间/自述三选一），否则复现必翻车 |
| 本地有按 task 分头的子目录 | probe 会逐个报出来，表单第 6 项照抄即可（分头情况机器一次看清） |

> **原理**：probe 不假设目录结构——config.json 有就读、没有就过；
> 顶层 `*.safetensors` 逐个读头；含权重文件的子目录报为疑似分头。
> 标准只到 safetensors 文件格式为止（8 字节头长 + JSON 头），目录布局每家都不同，
> 所以 probe 的输出是"发现清单"不是"验收结论"，最终口径以 smoke 为准。
> 走 Hub 时 probe 顺带证明三件事：仓库可读（权限）、精确 commit 存在
> （拒绝"只写分支名"）、dtype/动作维有线索。`config.json` 的数字只能参考：
> 上例 `chunk_size: 50` 是训练切分，我们 serve 用 10；SmolVLA 更出现过
> config 写 6-D 实测 7-D——probe 只是把 smoke 前能排除的错先排掉。

## 第三步：按路线填官方字段（★是必对项）

官方字段是全集（上游各模型目录的 yaml + README 参数表），★是我们的准入子集——
错一项就 0 分或起不来。★之外的先抄官方默认，不动。只看你的路线：

**路线 B：DB-CogACT**（官方 `db_cogact/_base.yaml` + `robotwin2.yaml` 原样）：

| 字段 | 官方 | 怎么填 |
|---|---|---|
| script | `src/vla_eval/model_servers/dexbotic/cogact.py`（base 定死） | 不动 |
| extends | `_base.yaml`（port 8000、use_text_template true 被继承） | 不动 |
| ★ model_path | `Dexmal/robotwin-db-cogact/<task>`（官方逐 task 覆写，如 adjust_bottle） | 按 task 分头逐个列；CI 转本地子目录绝对路径 |
| ★ chunk_size | 16（robotwin2；其他榜看对应文件，CALVIN 7） | 照抄对应榜文件 |
| ★ camera_keys | `["head_camera", "left_camera", "right_camera"]` | 照抄 |
| use_text_template | base 默认 true；robotwin2 覆写 false（CALVIN 用 true） | 照抄对应榜文件 |
| ★ dtype（我方） | 官方 yaml 不写（由镜像定）；V100 单卡走 fp16（fp32 必 OOM，见精度对照） | 填 fp16，写进表单 |

**路线 C：X-VLA**（官方 `xvla/_base.yaml` + `robotwin.yaml` 原样）：

| 字段 | 官方 | 怎么填 |
|---|---|---|
| script | `src/vla_eval/model_servers/xvla.py`（base 定死） | 不动 |
| ★ model_path | `2toINF/X-VLA-RoboTwin2`（robotwin.yaml；其他榜见对应文件） | 照抄对应榜文件 |
| ★ benchmark_profile | `robotwin` | 照抄 |
| ★ domain_id | 6（官方 recipe 定 embodiment prompt） | 照抄官方 recipe |
| ★ chunk_size | 30（官方值；不是 16，别按 CogACT 脑补） | 照抄 |
| denoising_steps | 10（base 默认） | 不动 |
| ★ dtype（我方） | 官方 yaml 不写；一律 fp32（fp16 首推理即崩，见精度对照） | 填 fp32，写进表单 |

注意：`fast_init=false` 是 run 侧（benchmark params），不在 serve yaml 里——
旧版把这一项写在 serve 模板注释里是错的，已纠正（配 EE run 配置，
见 `configs/run-robotwin-xvla-*.yaml`）。

**路线 A：LeRobot 桥**（官方 lerobot README 参数表全集，★标必对）：

| 字段 | 官方 | 怎么填 |
|---|---|---|
| ★ policy_type | 注册名：pi05 / groot / molmoact2 / smolvla / xvla… | 对表选 |
| ★ checkpoint | Hub ID 或本地路径 | 你的 ckpt |
| ★ image_keys | 考场相机→policy 特征；可省（按位置自动映射） | `{agentview: image, wrist: image2}` 或省 |
| ★ state_key | 本体特征名，或 null | `observation.state` 或 null |
| ★ chunk_size | 数字，或 null（= checkpoint 自带 n_action_steps） | 10 或 null |
| device / compile_model | 默认 cuda / 跟 checkpoint 走 | 不动（调速才碰，见官方 README 实测数） |
| policy_kwargs / features / preprocessor_overrides / quat_no_antipodal | 各家特殊需求（gated tokenizer 本地化等） | 有特殊才填 |

> **原理**：★项正好对应 6 项概念（权重/动作/相机/状态/chunk/dtype）——概念层统一，
> 字段名按路线走。★之外的字段抄官方默认：调优（如 compile_model 提速 4.4×）
> 是官方 README 的事，配准阶段不动。
> **原理·dtype**：fp16 不是 fp32 廉价版，0 分先查这项，不要先怀疑模型。
> **原理·口径**：EE 当关节喂，benchmark 硬截 `act[:14]`——400 步跑满全 0 分零异常，
> spec warning 是熔断器，见 quickstart 检查点。

## 第四步：对模板改出 serve yaml

本篇的产出就是这一个文件：harness 能直接吃掉的 serve yaml（`script` 对上上游
实现，`args` 对上你家模型的口径）。复制第一步定下来的那一例，
只改★项，别的不动（★之外的抄官方默认）：

```yaml
# DB-CogACT（官方 db_cogact/robotwin2.yaml + _base.yaml 原样；★4 项要改）
script: "src/vla_eval/model_servers/dexbotic/cogact.py"
args:
  model_path: Dexmal/robotwin-db-cogact/<task>   # ★按 task 分头；CI 用本地子目录绝对路径
  chunk_size: 16                                  # ★照抄对应榜文件
  camera_keys: '["head_camera", "left_camera", "right_camera"]'   # ★照抄
  use_text_template: false                        # robotwin2 覆写；CALVIN 用 true
```

```yaml
# π0.5（LeRobot 桥；★5 项要改，其余抄官方 README 默认）
script: "src/vla_eval/model_servers/lerobot.py"
args:
  policy_type: pi05                              # ★注册名对照
  checkpoint: lerobot/pi05_libero_finetuned      # ★你的 ckpt
  image_keys: {agentview: image, wrist: image2}  # ★可省（自动映射）
  state_key: observation.state                   # ★或 null
  chunk_size: 10                                 # ★或 null（= ckpt 自带）
```

```yaml
# X-VLA（官方 xvla/robotwin.yaml + _base.yaml 原样；★5 项要改）
script: "src/vla_eval/model_servers/xvla.py"
args:
  model_path: "2toINF/X-VLA-RoboTwin2"   # ★照抄对应榜文件
  benchmark_profile: "robotwin"          # ★照抄
  domain_id: 6                           # ★官方 recipe
  chunk_size: 30                         # ★官方值（不是 16）
  denoising_steps: 10                    # base 默认，不动
# fast_init=false 配在 run 侧 benchmark params，不在这里
```

> **原理**：serve yaml 定义的是模型的评测态身份（哪个权重 + 什么参数跑起来），
> 不含训练信息——上游"接一次模型"= server 实现（哪一族）+ serve yaml（哪一个）
> + 权重三件套。训练怎么来的管的是分数可比，见 03 披露清单的训练说明，各管一半。
> **原理**：`from_pretrained` 不认 `repo/subdir` 三段式（只认单仓或本地路径），
> 所以 CI 先 snapshot 再 `sed` 生成本地路径版——你写三段式一样能发帖，
> CI 会处理；但 smoke 跑哪个 task 就要用哪个 task 的头（model_path 对上），
> 这是模板里 `<task>` 占位符的含义。
> 有 GPU 的伙伴可本地先验：`vla-eval test -c <你的serve.yaml>`（上游自带冒烟，
> 需 uv + 权重 + GPU；无 GPU 直接发帖，smoke 代验）。
> 通用字段语义与 spec 分级方法的英文版见 `docs/upstream/serve-yaml-onboarding.md`
> （拟投上游，待维护者确认后再 PR；本篇是面向伙伴的中文宣讲版，引用它）。

## 第五步：发帖（交作业）

复制 `docs/partner-onboarding.md` 里的对接表单，把 probe 输出 + ★项贴进去，
不知道的空着。在本仓 Discussion 发帖，标题 `【评测对接】<模型名>`。
1 天内给 spec 对齐报告，通过进 smoke。

## 检查点：会被打回的 Top 3（= 权重★项没做）

1. 只给了模型名没给确切 commit（probe 第一步就是干这个的）。2. 权重要授权的没开权限。
3. 按 task 分头的只给了部分头。

## 下一步

帖子通过 → `02-smoke.md`（1 task×1ep，拿 spec 对齐报告）。

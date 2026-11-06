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

harness 把官方原生要写的（适配器代码 + 两个 env + 十几个参数）收拢成一份 serve yaml。
**省的是实现，不省的是口径**：权重（训的哪份 ckpt）和评测环境（测的哪个 task_config）
本来就是两件事，harness 不在 yaml 里替你合并。
下文六节与上游 [CONTRIBUTING（Adding a Model Server）](https://github.com/allenai/vla-evaluation-harness/blob/main/CONTRIBUTING.md#adding-a-model-server) 1:1 对照：节号即上游节号。卡住时拿着节号去上游问。
已有现成模板的模型只做 §1（找路）→ §5（填 yaml）→ §6（校验），§2–§4 跳过不写代码。

先把表单和示例配置拿下来；模板以上游 `configs/model_servers/` 为准（§5 给了两例全文）：

```bash
git clone https://github.com/link-seek/partner-vla-eval.git
cd partner-vla-eval
```

### §1 建文件：先查现成模板，有就不用建

对应官方第 1 步（[`src/vla_eval/model_servers/<name>.py`](https://github.com/allenai/vla-evaluation-harness/blob/main/src/vla_eval/model_servers/cogact.py)，uv script + PEP 723）。

**操作**：先对号入座，再往下读：

当前只开 RobotWin。上游 `model_servers/` 有 15 个族目录，但**有 RobotWin 配置的只有两份**（`db_cogact/robotwin2.yaml`、`xvla/robotwin.yaml`）：

| 模型类型 | RobotWin 配置 | 走这条路线 |
|---|---|---|
| DB-CogACT（Dexbotic） | 有 | B（官方 `db_cogact/`），`model_path` 按 task 分头 |
| X-VLA 官方 ckpt | 有 | C（官方 `xvla/`），EE 口径，`domain_id` 按官方 recipe |
| LeRobot 系（π0/π0.5/GR00T/SmolVLA…） | 无 | 上游 `lerobot/` 桥和配置都在，但 10 份全是 LIBERO（单臂 Franka、7 维）口径；RobotWin 是双臂 14D 关节 / 16D EE + 三相机，官方也没提供这一份；桥本身能接（`image_keys`/`state_key`/`chunk_size` 可配），缺的是 yaml + 实测（规划中） |
| CogACT（Microsoft 原版，7-DoF） | 无 | 只有 RT-1/Bridge 配置；要报 RobotWin 需适配，走「以上都不是」 |
| 上游其他（OpenVLA / OFT / Pi0…） | 无 | 上游有 server 不等于有 RobotWin 配置：先查该族目录，没有就走适配 |
| 以上都不是 | — | 三退路：①先套 LeRobot 桥（任意 `PreTrainedPolicy` 即插即用）→ ②照上游 [CONTRIBUTING](https://github.com/allenai/vla-evaluation-harness/blob/main/CONTRIBUTING.md#adding-a-model-server)（人看）/`add-model-server` skill（agent 用）加 server（约 50 行，我们 [#168](https://github.com/allenai/vla-evaluation-harness/pull/168) 有先例）→ ③直接联系 xieyucheng，表单空着，我们帮你看 |

然后看上游 [`configs/model_servers/`](https://github.com/allenai/vla-evaluation-harness/tree/main/configs/model_servers) 下有没有你这一族（cogact、db_cogact、xvla、lerobot、openvla、oft、pi0…共 15 个目录）。有 → 定下来是哪一族、哪一份 yaml，直接去 §5。没有 → 才新建文件：顶部 PEP 723 依赖块照抄 [`cogact.py`](https://github.com/allenai/vla-evaluation-harness/blob/main/src/vla_eval/model_servers/cogact.py) 的文件头，类架子见 §2。

**检查点**：你能说出“我用哪一族、哪一份 yaml”。当前 smoke/全量只开 RobotWin，LIBERO/CALVIN 标注规划中——yaml 里看到 libero/calvin 文件也不用管。

**原理**：上游按模型族分目录，一族一目录、一考场一 yaml。路线不是我们分的，是货架原样摆过来。

### §2 继承：没有现成模板才写，有就跳过

对应官方第 2 步（继承 `PredictModelServer`，见 [`src/vla_eval/model_servers/predict.py`](https://github.com/allenai/vla-evaluation-harness/blob/main/src/vla_eval/model_servers/predict.py)）。

**操作**：新文件照抄你这条路线的 server 类架子——B 看 [`dexbotic/cogact.py`](https://github.com/allenai/vla-evaluation-harness/blob/main/src/vla_eval/model_servers/dexbotic/cogact.py)，C 看 [`xvla.py`](https://github.com/allenai/vla-evaluation-harness/blob/main/src/vla_eval/model_servers/xvla.py)，新族看官方最小例 [`cogact.py`](https://github.com/allenai/vla-evaluation-harness/blob/main/src/vla_eval/model_servers/cogact.py)（Microsoft CogACT）：

```python
from vla_eval.model_servers.predict import PredictModelServer

class MyModelServer(PredictModelServer):
    def __init__(self, model_path: str = "...", *, chunk_size: int = 16, **kwargs):
        super().__init__(chunk_size=chunk_size, **kwargs)
        # 在这里 load 模型（不许懒加载，见下）
```

**检查点**：模块 import 无报错、类能实例化（依赖装齐、`__init__` 里模型 load 完）。

**原理**：权重在 `__init__` 里一次 load 好（官方明确 no lazy-load hook）。首推理必须已是稳态延迟，warm up（compile 等）也在 `__init__` 或 `reset_episodes` 里做完——runner 是 `reset_episodes` 一返回就起表计时的。

### §3 实现推理：只实现 predict 或 predict_batch 之一

对应官方第 3 步（`Implement predict(obs, row) -> dict or predict_batch(obs, rows) -> Batch. Load the model inside __init__ (no lazy-load hook)`）。

**操作**：不同族写法不同，先按路线选参考实现：

| 路线 | 参考文件 | 它怎么出动作 |
|---|---|---|
| B DB-CogACT | [`dexbotic/cogact.py`](https://github.com/allenai/vla-evaluation-harness/blob/main/src/vla_eval/model_servers/dexbotic/cogact.py) | `CogACTForCausalLM.inference_action`；`_convert_actions` 把累计 delta 转绝对关节（14D） |
| C X-VLA | [`xvla.py`](https://github.com/allenai/vla-evaluation-harness/blob/main/src/vla_eval/model_servers/xvla.py) | `generate_actions`；`benchmark_profile: robotwin` 出 16D EE |
| 其他/新族 | [`cogact.py`](https://github.com/allenai/vla-evaluation-harness/blob/main/src/vla_eval/model_servers/cogact.py)（Microsoft CogACT，官方指定最小例） | `load_vla` + `predict_action` |

落到代码只有两件事。

① 实现 `predict`——取图、取语言、调模型、返回 dict（调用那行换成你参考文件里的写法）：

```python
def predict(self, obs, row):
    pil_image = self._obs_to_pil(obs)             # obs["images"] 里取图
    prompt = obs.get("task_description", "")      # 语言指令
    actions, _ = self._model.predict_action(...)  # B/C 换成 inference_action / generate_actions
    return {"actions": actions}                   # dict
```

② （可选）要合批才实现 `predict_batch`，照参考文件的写法（B/C 都有现成实现）；不实现则引擎逐行调 `predict`。

模型加载放 `__init__`（官方原文后半句 no lazy-load hook），照参考文件（B 是 `from_pretrained`，C 是 `AutoModel.from_pretrained`）。

**检查点**：
- 返回 `{"actions": <[T, D]>}`，`T` = §5 填的 `chunk_size`。
- `get_action_spec` / `get_observation_spec` 照你参考文件（B 返回 `{"actions": RAW}`；C 的 robotwin 档返回 `ee_pose`）。基类默认抛 `NotImplementedError`，serve 端静默跳过：不写也能起，但拿不到口径错配 warning。

**原理**：
- 一行 = 一个 episode。`obs` 是这一行这一帧的观测，`row` 是这一行的句柄（`row.id`/`row.step`/`row.is_first`）。
- `chunk_size` 是“一次推理出几个动作”：T 个动作里第一个立刻发，其余 T-1 步从 per-episode buffer 发，不再进模型——填错就是动作节奏错（见 §5）。
- no lazy-load 的原因：runner 在 `reset_episodes` 返回那一刻就起表计时，第一次推理必须已是稳态延迟；warm up（`torch.compile` 等）要在 `__init__` 或 `reset_episodes` 里做完。
- 所有 hook 在一条模型线程上按到达顺序执行，线程绑定状态（CUDA graph、JAX）也在 `__init__` 或首次 `reset_episodes` 里建。
- B 的 `_convert_actions` 是口径的关键：模型出的是累计 delta，RoboTwin 要绝对关节——没有它，动作全错但不报错。

### §4 入口与并发：照抄一段，参数缺省

对应官方第 4 步（[`run_server`](https://github.com/allenai/vla-evaluation-harness/blob/main/src/vla_eval/model_servers/serve.py)）+ 底下并发说明。

**操作**：文件尾只写这段，不手写 argparse：

```python
if __name__ == "__main__":
    from vla_eval.model_servers.serve import run_server
    run_server(MyModelServer)
```

`chunk_size`/`max_batch_size`/`max_rows`/`max_wait_time` 有特殊才填，否则抄同族 yaml 默认。有现成模板的本节直接跳过。

**检查点**：`python <name>.py --help` 能列出 `run_server` 的统一项（`--config`/`--address`/`--port`）和你的构造参数（`--args.<字段>`）。

**原理**：`max_batch_size` 封顶每次合批几行，`max_wait_time` 等凑批，`max_rows` 封顶并发几 episode。缺省即模板值，调错只影响吞吐不影响分数——分数只看 §5 的口径项。

### §5 加配置：抄一份 yaml，只改★项

对应官方第 5 步（`configs/model_servers/<name>/`，`extends: _base.yaml` 继承公共项）。**无论有没有现成 server，这一步都要做。**

**操作**：复制 §1 定下来的那一例，只改★项，其余照抄、不动。

DB-CogACT（官方 [`db_cogact/_base.yaml`](https://github.com/allenai/vla-evaluation-harness/blob/main/configs/model_servers/db_cogact/_base.yaml) + [`robotwin2.yaml`](https://github.com/allenai/vla-evaluation-harness/blob/main/configs/model_servers/db_cogact/robotwin2.yaml) 原样）：

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

X-VLA（官方 [`xvla/_base.yaml`](https://github.com/allenai/vla-evaluation-harness/blob/main/configs/model_servers/xvla/_base.yaml) + [`robotwin.yaml`](https://github.com/allenai/vla-evaluation-harness/blob/main/configs/model_servers/xvla/robotwin.yaml) 原样）：

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

LeRobot 系：上游 `lerobot/` 桥和 10 份配置都在，但全是 LIBERO（单臂 Franka、7 维）口径——RobotWin 要双臂 14D 关节 / 16D EE + 三相机，官方也没提供这一份；桥本身能接（`image_keys`/`state_key`/`chunk_size` 可配），缺的是 yaml + 实测（规划中）。字段见上游 [lerobot README](https://github.com/allenai/vla-evaluation-harness/blob/main/configs/model_servers/lerobot/README.md) 参数表。同族特有字段走 `args.policy_kwargs`，如 GR00T 的 `embodiment_tag`、MolmoAct2 的 `norm_tag`。

**检查点**：`script`/`extends` 与上游同名文件一致；`model_path` 按 task 分头的逐个列齐（缺头的 task 排不上）；`fast_init` 是 benchmark 侧参数（`action_type: ee` 时自动关，走 CuRobo 规划），不在 serve yaml 里找。

**原理**：serve yaml 定义模型的评测态身份（哪个权重 + 什么参数跑起来），不含训练信息。官方字段是全集，★是准入子集——错一项就 0 分或起不来。dtype 不是 yaml 字段（官方 yaml 都没有），是我们起服务时定的、写进表单：X-VLA 用 fp32（fp16 首推理即崩），DB-CogACT 在 V100 单卡用 fp16（fp32 首 forward 即 31GB OOM）。0 分先查 dtype，不要先怀疑模型。

### §6 校验交接：有 GPU 先 `test -c`，然后联系 xieyucheng

对应官方第 6 步（`vla-eval test -c <yaml>`，见 CONTRIBUTING Smoke Tests）+ 我方交接。

**操作**：

```bash
vla-eval test -c configs/model_servers/<你的serve.yaml>  # 有 GPU 才跑；无 GPU 跳过，smoke 代验
```

然后联系 xieyucheng，把三样发过去（标题 `【评测对接】<模型名>`）：①权重版本（Hub ID + 精确 commit，分支名不行；本地目录给快照哈希；OBS 地址保证能拉取；私仓先给 `link-seek` 开授权）②★项 ③对接表单（复制本仓 `docs/partner-onboarding.md` 里的表，不知道的空着）。

**检查点**：`test -c` 过，或明确写“无 GPU、等 smoke 代验”；三样齐了再发，缺权重版本/缺分头直接打回。

**原理**：`test -c` 是上游自带冒烟（1 episode，真模型要 GPU）。交接是我们的（上游没有排队概念）：xieyucheng 确认后进 smoke（1 天内给 spec 对齐报告），再进 02。

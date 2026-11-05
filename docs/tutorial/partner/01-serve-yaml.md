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
下文六节与上游 [CONTRIBUTING（Adding a Model Server）](https://github.com/allenai/vla-evaluation-harness/blob/main/CONTRIBUTING.md#adding-a-model-server) 1:1 对照：节号即上游节号。卡住时拿着节号去上游问。
已有现成模板的模型只做 §1（找路）→ §5（填 yaml）→ §6（校验），§2–§4 跳过不写代码。

先把模板和表单源文件拿下来（后面照着改、对着填）：

```bash
git clone https://github.com/link-seek/partner-vla-eval.git
cd partner-vla-eval
```

### §1 建文件：先找有没有现成模板，有就不用写代码

对应官方第 1 步（`src/vla_eval/model_servers/<name>.py`，uv script + PEP 723）。

**操作**：看上游 `configs/model_servers/` 下有没有你这一族（cogact、db_cogact、xvla、lerobot、openvla、oft、pi0…共 15 个目录）。有 → 定下来是哪一族、哪一份 yaml，直接去 §5。没有 → 才新建文件，文件头照抄参考实现（见 §2）。

**检查点**：你能说出“我用哪一族、哪一份 yaml”。当前 smoke/全量只开 RobotWin，LIBERO/CALVIN 標规划中——yaml 里看到 libero/calvin 文件也不用管。

**原理**：上游按模型族分目录，一族一目录、一考场一 yaml。路线不是我们分的，是货架原样摆过来。

### §2 继承：没有现成模板才写，有就跳过

对应官方第 2 步（继承 `PredictModelServer`，见 `src/vla_eval/model_servers/predict.py`）。

**操作**：新文件照抄参考实现 `src/vla_eval/model_servers/cogact.py` 的类架子：

```python
from vla_eval.model_servers.predict import PredictModelServer

class MyModelServer(PredictModelServer):
    def __init__(self, model_path: str = "...", *, chunk_size: int = 16, **kwargs):
        super().__init__(chunk_size=chunk_size, **kwargs)
        # 在这里 load 模型（不许懒加载，见下）
```

**检查点**：类名能被 `run_server` 导入，`__init__` 里模型已 load 完。

**原理**：权重在 `__init__` 里一次 load 好（官方明确 no lazy-load hook）。首推理必须已是稳态延迟，warm up（compile 等）也在 `__init__` 或 `reset_episodes` 里做完——runner 是 `reset_episodes` 一返回就起表计时的。

### §3 实现推理：一次观测进，一组动作出

对应官方第 3 步（`predict(obs, row) -> dict` 或 `predict_batch`）。

**操作**：二选一，抄 `cogact.py`：

```python
def predict(self, obs, row):
    # obs: {"images": {...}, "task_description": "..."}；return {"actions": actions}
```

批量更快才写 `predict_batch(obs, rows)`（obs 按列切分，一行一 episode）；不写则引擎逐行调 `predict`。

**检查点**：单步能返回 `[T, D]` 动作；`get_action_spec`/`get_observation_spec` 照抄同族实现。

**原理**：一行即一 episode。`chunk_size` 是每次推理产几个动作、剩下的进 per-episode buffer 接着发；per-episode 状态按 `row.id` 存（id 会复用，`reset_episodes` 里清）。`max_rows=1` 只给全局状态模型（自带 action queue 那种）用。

### §4 入口与并发：照抄三行，参数缺省

对应官方第 4 步（`run_server`）+ 底下并发说明。

**操作**：文件尾只写这三行，不手写 argparse：

```python
if __name__ == "__main__":
    from vla_eval.model_servers.serve import run_server
    run_server(MyModelServer)
```

`chunk_size`/`max_batch_size`/`max_rows`/`max_wait_time` 有特殊才填（`policy_kwargs` 走表单备注，如 GR00T 的 `embodiment_tag`），否则抄同族 yaml 默认。有现成模板的本节直接跳过。

**检查点**：`python <name>.py --help` 是 `run_server` 的统一参数，不是你自己的。

**原理**：`max_batch_size` 封顶每次合批几行，`max_wait_time` 等凑批，`max_rows` 封顶并发几 episode。缺省即模板值，调错只影响吞吐不影响分数——分数只看 §5 的口径项。

### §5 加配置：抄一份 yaml，只改★项

对应官方第 5 步（`configs/model_servers/<name>/`，`extends: _base.yaml` 继承公共项）。**这是没模板之外的所有伙伴都要做的一步。**

**操作**：复制 §1 定下来的那一例，只改★项，其余照抄、不动。

DB-CogACT（官方 `db_cogact/_base.yaml` + `robotwin2.yaml` 原样）：

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

X-VLA（官方 `xvla/_base.yaml` + `robotwin.yaml` 原样）：

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

LeRobot 系走桥模板（字段见上游 lerobot README 参数表，换 checkpoint 即可；单臂，规划接入方向）。

**检查点**：`script`/`extends` 与上游同名文件一致；`model_path` 按 task 分头的逐个列齐（缺头的 task 排不上）；`fast_init=false` 是 run 侧参数，不在 serve yaml 里找。

**原理**：serve yaml 定义模型的评测态身份（哪个权重 + 什么参数跑起来），不含训练信息。官方字段是全集，★是准入子集——错一项就 0 分或起不来。dtype 官方 yaml 不写（由镜像定，写进表单）：X-VLA 一律 fp32（fp16 首推理即崩），CogACT 在 V100 单卡走 fp16；0 分先查 dtype，不要先怀疑模型。

### §6 校验交接：有 GPU 先 `test -c`，然后联系 xieyucheng

对应官方第 6 步（`vla-eval test -c <yaml>`，见 CONTRIBUTING Smoke Tests）+ 我方交接。

**操作**：

```bash
vla-eval test -c configs/model_servers/<你的serve.yaml>  # 有 GPU 才跑；无 GPU 跳过，smoke 代验
```

然后联系 xieyucheng，把三样发过去（标题 `【评测对接】<模型名>`）：①权重版本（Hub ID + 精确 commit，分支名不行；本地目录给快照哈希；OBS 地址保证能拉取；私仓先给 `link-seek` 开授权）②★项 ③对接表单（复制本仓 `docs/partner-onboarding.md` 里的表，不知道的空着）。

**检查点**：`test -c` 过，或明确写“无 GPU、等 smoke 代验”；三样齐了再发，缺权重版本/缺分头直接打回。

**原理**：`test -c` 是上游自带冒烟（1 episode，真模型要 GPU）。交接是我们的（上游没有排队概念）：xieyucheng 确认后进 smoke（1 天内给 spec 对齐报告），再进 02。

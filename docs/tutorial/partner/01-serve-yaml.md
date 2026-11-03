# 伙伴 01：跑 probe，配准 serve 口径

> 目标：把你训好的模型配准成可上榜形态（不教训模型，只教交模型），
> 拿着 probe 输出写出一份一次过审的 serve yaml。
> 时间：30 分钟 ｜ 前置：读完 `quickstart` ｜ 准备：一台能上网的电脑，python3 即可
> （无第三方依赖，不下权重，不用 GPU）。
> 你将得到：probe 输出 + 6 项配准 + serve yaml + 对接帖。
> 读法：跟着跑，每段命令下面都贴了期望输出，对不上先停。

## 准备

```bash
git clone https://github.com/link-seek/partner-vla-eval.git
cd partner-vla-eval
python3 --version   # 3.8+ 即可
```

> **原理**：后面跑的是 `scripts/spec_probe.py`，纯标准库，只读 HF 元数据。
> 它不回答全部问题——它把"机器能读到的"和"必须人答的"分开，6 项配准就是这么来的。

## 第一步：跑 probe，看清自己的模型

```bash
python3 scripts/spec_probe.py <你的HF-ID>   # 私仓加 --token $HF_TOKEN
```

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
| 手里是本地权重、没推 Hub | probe 只认 Hub ID（只调 API 读元数据，一字节权重都不下）；本地请先 push 到 Hub，或跳过 probe 直接人答 6 项 |

> **原理**：probe 只证明三件事——仓库存在且可读（权限）、精确 commit 存在
> （拒绝"只写分支名"）、dtype/动作维有线索。`config.json` 的数字只能参考：
> 上例 `chunk_size: 50` 是训练切分，我们 serve 用 10（serving 节拍是另一回事）；
> SmolVLA 更出现过 config 写 6-D 实测 7-D——**最终口径以 smoke 实测为准**，
> probe 只是把 smoke 前能排除的错先排掉。

## 第二步：机器一半 + 人一半，拼出 6 项

probe 输出直接填一半表单，另一半必须人答：

| # | 项 | probe 给 | 人答 |
|---|---|---|---|
| 1 | 动作维度+含义 | 动作头形状 heuristic（候选） | 关节 qpos 还是末端 EE？EE 注明 rot6d/quat、含不含 gripper |
| 2 | 相机名 | 给不出 | 照实写（如 head_camera），错了直接黑图 |
| 3 | 状态字段 | 给不出 | 关节角 / 末端位姿 / 不需要 |
| 4 | chunk size | config 参考值 | 和 benchmark 节拍对齐（RobotWin 16，CALVIN 7，LIBERO 10） |
| 5 | dtype | index.json 线索 | X-VLA 一律 fp32，DB-CogACT 走 fp16（见下） |
| 6 | 权重确切产物 | commits 列表选一个 + HEAD | 按 task 分头的逐个列出 |

> **原理·第 5 项**：fp16 不是 fp32 廉价版。X-VLA fp16 首推理即崩
> （`float vs Half bias`，六轮 29/30 vs 0/30，实验 B；官方训练用 bf16）；
> CogACT 反过来 fp32 首个 forward 即 OOM（31GB，实验 B2）。0 分先查 dtype。
> **原理·第 1 项**：EE 当关节喂，benchmark 硬截 `act[:14]` 当关节执行——
> 400 步跑满，全 0 分，零异常。spec warning 是熔断器，见 quickstart 检查点。

## 第三步：对模板改出 serve yaml

复制最像的一例，只改 6 项对应的字段，别的不动：

```yaml
# DB-CogACT（关节口径，双臂+CALVIN）
script: "src/vla_eval/model_servers/dexbotic/cogact.py"
args:
  model_path: Dexmal/<repo>/<task>   # 按 task 分头；CI 用本地子目录绝对路径
  chunk_size: 16                      # RobotWin；CALVIN 用 7
  camera_keys: '["head_camera", "left_camera", "right_camera"]'
  use_text_template: false            # RobotWin；CALVIN 用 true
```

```yaml
# π0.5（LeRobot 桥，单臂 LIBERO）
script: "src/vla_eval/model_servers/lerobot.py"
args:
  policy_type: pi05
  checkpoint: lerobot/pi05_libero_finetuned
  image_keys: {agentview: image, wrist: image2}
  state_key: observation.state
  chunk_size: 10
```

```yaml
# X-VLA（EE 口径，action_type=ee，domain_id 按官方 recipe，fast_init 必须 false）
# 镜像默认 qpos，config 切 ee；serve 侧声明 ee_pose（advisory warning 可照常跑）
```

> **原理**：`from_pretrained` 不认 `repo/subdir` 三段式（只认单仓或本地路径），
> 所以 CI 先 snapshot 再 `sed` 生成本地路径版——你写三段式一样能发帖，
> CI 会处理；但 smoke 跑哪个 task 就要用哪个 task 的头（model_path 对上），
> 这是模板里 `<task>` 占位符的含义。

## 第四步：发帖（交作业）

复制 `docs/partner-onboarding.md` 里的对接表单，把 probe 输出 + 6 项贴进去，
不知道的空着。在本仓 Discussion 发帖，标题 `【评测对接】<模型名>`。
1 天内给 spec 对齐报告，通过进 smoke。

## 检查点：会被打回的 Top 3（= 第二步第 6 项没做）

1. 只给了模型名没给确切 commit（probe 第一步就是干这个的）。2. 权重要授权的没开权限。
3. 按 task 分头的只给了部分头。

## 下一步

帖子通过 → `02-smoke.md`（1 task×1ep，拿 spec 对齐报告）。

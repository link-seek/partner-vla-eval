# 伙伴 01：认模型，对号入座，配准交付

> 目标：把你训好的模型配准成可上榜形态（不教训模型，只教交模型）。
> 时间：30 分钟 ｜ 前置：读完 `quickstart` ｜ 准备：一台能上网的电脑，python3 即可
> （无第三方依赖，不下权重，不用 GPU）。
> 你将得到：probe 输出 + 型号归位 + 6 项配准 + serve yaml + 对接帖。
> 读法：跟着跑，每段命令下面都贴了期望输出，对不上先停。

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
EE 当关节喂全 0 分的 X-VLA）；路线笃定的可跳过，直接到第三步人答 6 项。

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

## 第三步：机器一半 + 人一半，拼出 6 项

probe 输出直接填一半表单，另一半必须人答：

| # | 项 | probe 给 | 人答 |
|---|---|---|---|
| 1 | 动作维度+含义 | 动作头形状 heuristic（候选） | 关节 qpos 还是末端 EE？EE 注明 rot6d/quat、含不含 gripper |
| 2 | 相机名 | 给不出 | 照实写（如 head_camera），错了直接黑图 |
| 3 | 状态字段 | 给不出 | 关节角 / 末端位姿 / 不需要 |
| 4 | chunk size | config 参考值 | 和 benchmark 节拍对齐（RobotWin 16，CALVIN 7，LIBERO 10） |
| 5 | dtype | index.json 线索 | X-VLA 一律 fp32，DB-CogACT 走 fp16（见下） |
| 6 | 权重确切产物 | Hub：commits 列表选一个 + HEAD；文件：目录 + 版本注明（哈希/时间/自述）；OBS：地址（bucket/path，权限/有效期要够我们拉取） | 按 task 分头的逐个列出 |

> **原理·第 5 项**：fp16 不是 fp32 廉价版。X-VLA fp16 首推理即崩
> （`float vs Half bias`，六轮 29/30 vs 0/30，实验 B；官方训练用 bf16）；
> CogACT 反过来 fp32 首个 forward 即 OOM（31GB，实验 B2）。0 分先查 dtype。
> **原理·第 1 项**：EE 当关节喂，benchmark 硬截 `act[:14]` 当关节执行——
> 400 步跑满，全 0 分，零异常。spec warning 是熔断器，见 quickstart 检查点。

## 第四步：对模板改出 serve yaml

本篇的产出就是这一个文件：harness 能直接吃掉的 serve yaml（`script` 对上上游
实现，`args` 对上你家模型的口径）。复制第一步定下来的那一例，
只改 6 项对应的字段，别的不动：

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
> 有 GPU 的伙伴可本地先验：`vla-eval test -c <你的serve.yaml>`（上游自带冒烟，
> 需 uv + 权重 + GPU；无 GPU 直接发帖，smoke 代验）。
> 上游没有"怎么写兼容文件"的用户教程（只有开发者向的 CONTRIBUTING + 各模型
> README 参数表）——本篇就是补这一块的，模板与口径表以本篇为准。

## 第五步：发帖（交作业）

复制 `docs/partner-onboarding.md` 里的对接表单，把 probe 输出 + 6 项贴进去，
不知道的空着。在本仓 Discussion 发帖，标题 `【评测对接】<模型名>`。
1 天内给 spec 对齐报告，通过进 smoke。

## 检查点：会被打回的 Top 3（= 第三步第 6 项没做）

1. 只给了模型名没给确切 commit（probe 第一步就是干这个的）。2. 权重要授权的没开权限。
3. 按 task 分头的只给了部分头。

## 下一步

帖子通过 → `02-smoke.md`（1 task×1ep，拿 spec 对齐报告）。

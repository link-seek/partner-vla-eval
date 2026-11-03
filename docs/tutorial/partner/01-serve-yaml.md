# 伙伴 01：交出权重和 serve 配置

> 目标：一次交齐评测所需全部信息，不被打回。
> 时间：填表 30 分钟 ｜ 前置：读完 `quickstart` ｜ 你将得到：一条可进队列的对接帖。
> 读法：照`操作`填表发帖；`原理`讲每个字段为什么错了会烧钱。

## 操作：三步进队列

1. 复制 `docs/partner-onboarding.md` 里的对接表单，逐项填写（不知道的空着，我们帮你看）。
2. 在本仓 Discussion 发帖，标题格式 `【评测对接】<模型名>`，把表单贴进去。
3. 等 spec 对齐报告（1 天内）：通过进 smoke，不过打回补信息，不烧大钱。

> **原理**：我们不碰你的训练代码，只跑分。你要交的就两样——权重地址 + 一个
> serve yaml（`configs/serve-*.yaml`，见下）。表单的每一项都对应 serve 起不来
> 或必 0 分的真实死法（见 08 排障表），填得越准，烧的卡越少。

## 操作：表单关键项怎么填（含三个模板）

**权重**：给确切产物，不是名字。HuggingFace ID + 精确 commit（`git rev-parse`
那串，不要只写分支名）；私仓先给 `link-seek` 开授权；按 task 分头的逐个列出。

> **原理**：一名多版是复现翻车第一原因；`from_pretrained` 不认 `repo/subdir`
> 三段式，CI 会 snapshot 后用本地子目录绝对路径（quickstart 步骤二已验证）。
> 只给部分头的 task 排不上——权重即排期依据。

**动作口径**（最关键，错了必 0 分还浪费一轮卡）：维度（如 14 / 16 / 7）+ 含义
（关节 qpos / 末端 EE / 其它）+ EE 的话注明 rot6d 还是 quat、chunk 内含不含 gripper。

> **原理**：serve 吐什么维度、什么含义，benchmark 就按什么吃。EE 当关节喂，
> benchmark 硬截 `act[:14]` 当关节执行——400 步跑满，全 0 分，零异常（X-VLA
> 就是这么发现的，见 08 第 1 条）。`action_dim` / `image_keys` / `state_key` /
> `chunk_size` 四项就是 06 的口径映射表，episode 起点的 `Spec mismatch`
> warning 是熔断器，看到先停手对表。

serve yaml 三例（同段式：定位/口径/权重/备注，摘自 06，细节以 06 为准）：

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

**dtype**：跑分先报 dtype。X-VLA 一律 fp32，DB-CogACT 走 fp16（V100 单卡语境）。

> **原理**：fp16 不是 fp32 的廉价版（指数位少 3 位）。X-VLA fp16 首推理即崩
> （`float vs Half bias`，LIBERO 六轮 29/30 vs 0/30，实验 B）；官方训练用
> `accelerate --mixed_precision bf16`，fp16 属数值越界，bf16 复刻待 H100。
> CogACT 反过来：fp32 首个 forward 即 OOM（31GB，V100 单卡不可行，实验 B2）。
> 0 分先查这张表，不要先怀疑模型。

**输入**：相机名照实写（对不上直接黑图，一样跑满全程）；chunk size 和 benchmark
节拍对齐；特殊依赖写版本号（烘进 serve 镜像，不现场装）。

## 检查点：会被打回的 Top 3

1. 只给了模型名没给确切 commit。2. 权重要授权的没开权限。3. 按 task 分头的只给了部分头。

## 下一步

帖子通过 → `02-smoke.md`（1 task×1ep，拿 spec 对齐报告）。

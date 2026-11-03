# 伙伴 01：配准 serve 口径

> 目标：写出一份一次过审的 serve yaml，不被打回。
> 时间：自查 30 分钟 ｜ 前置：读完 `quickstart` ｜ 你将得到：6 项全勾的自查 + 一条可进队列的对接帖。
> 读法：`操作一`是动手核对（教程本体），`操作二`发帖只是交作业。

## 操作一：按 6 项清单自查 serve yaml（逐项打勾）

拿你的 serve yaml（照下方三例格式），逐项核对。每一项都对应一个真实死法，
勾完再发帖——过审率就是这么来的。

- [ ] **1. 动作维度 + 含义**：维度（如 14 / 16 / 7）对不对？含义是关节 qpos
 还是末端 EE？EE 的话注明 rot6d 还是 quat、chunk 内含不含 gripper。
- [ ] **2. 相机名**：`image_keys` 照实写（如 head_camera/camera1…）。
- [ ] **3. 本体状态**：`state_key` 要什么（关节角 / 末端位姿 / 不需要）？
- [ ] **4. chunk size**：一次出几个动作，和 benchmark 节拍对齐（RobotWin 16，CALVIN 7，LIBERO 10）。
- [ ] **5. dtype**：X-VLA 一律 fp32，DB-CogACT 走 fp16（V100 单卡语境），先报再跑。
- [ ] **6. 权重路径**：HuggingFace ID + 精确 commit（`git rev-parse` 那串）；
 按 task 分头的逐个列出；私仓先给 `link-seek` 开授权。

> **原理·错了会怎样**：1~4 错 = 口径错配，EE 当关节喂则 benchmark 硬截
> `act[:14]` 当关节执行——400 步跑满，全 0 分，零异常（X-VLA 就是这么发现的，
> spec warning 是熔断器，见 quickstart 检查点）。相机名错 = 直接黑图，一样跑满
> 全程。5 错 = X-VLA fp16 首推理即崩（`float vs Half bias`，六轮 29/30 vs 0/30，
> 实验 B；官方训练用 bf16，fp16 属数值越界）；CogACT 反过来 fp32 首个 forward
> 即 OOM（31GB，实验 B2）——fp16 不是 fp32 廉价版，0 分先查 dtype 不要先怀疑模型。
> 6 错 = `from_pretrained` 不认 `repo/subdir` 三段式（`HFValidationError`），
> 或权重下不了（Xet 401 要 token）；一名多版是复现翻车第一原因。

serve yaml 三例（同段式：定位/口径/权重/备注，对着抄）：

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

## 操作二：填表发帖（交作业）

复制 `docs/partner-onboarding.md` 里的对接表单，把 6 项自查结果填进去，
不知道的空着（我们帮你看）。在本仓 Discussion 发帖，
标题格式 `【评测对接】<模型名>`，把表单贴进去即进队列，1 天内给 spec 对齐报告。

## 检查点：会被打回的 Top 3（= 自查第 6/6/6 项没勾）

1. 只给了模型名没给确切 commit。2. 权重要授权的没开权限。3. 按 task 分头的只给了部分头。

## 下一步

帖子通过 → `02-smoke.md`（1 task×1ep，拿 spec 对齐报告）。

# 06 模型接入

> 版本：v1.2（2026-11-03，dtype 红线 + B/B2 收官）。伙伴交两样：权重地址 + 一个 serve yaml。执行统一镜像 `0.8.0-ee-slim`（直连上游主线 EE，已合 #168）；V100 job 零 checkout（payload 镜像 SWR 拉）。

## dtype 红线（V100，B/B2 已证伪，必读）

| 模型 | 用什么 | 为什么 |
|---|---|---|
| X-VLA | 一律 fp32 | fp16 首推理即崩 `float vs Half bias`，LIBERO 三榜六轮 29/30 vs 0/30 一致；官方训练 `accelerate --mixed_precision bf16`，fp16 属数值越界；bf16 复刻待 H100 |
| DB-CogACT | fp16 | fp32 首个 forward 即 OOM（31GB，V100 单卡不可行）；全链 fp16 是 V100 限定接受项，见 99 |
| 通用 | 跑分先报 dtype | fp16 不是 fp32 廉价版（指数位少 3 位）；0 分先查本表 + 08 第 4 条，不要先怀疑模型 |

表单里 dtype 一栏：X-VLA 填 fp16 直接打回（除非指明 H100 复刻）。

## serve yaml 模板（三例同段式：定位/口径/权重/备注）

### DB-CogACT（关节口径，双臂+CALVIN）

```yaml
script: "src/vla_eval/model_servers/dexbotic/cogact.py"   # 上游主线已有对应实现
args:
  model_path: Dexmal/<repo>/<task>   # 按 task 分头；from_pretrained 不认 repo/subdir，CI 用本地子目录绝对路径
  port: 8000
  chunk_size: 16                      # RobotWin；CALVIN 用 7
  camera_keys: '["head_camera", "left_camera", "right_camera"]'
  use_text_template: false            # RobotWin；CALVIN 用 true
```

### π0.5（LeRobot 桥，单臂）

```yaml
script: "src/vla_eval/model_servers/lerobot.py"
args:
  policy_type: pi05
  checkpoint: lerobot/pi05_libero_finetuned
  image_keys: {agentview: image, wrist: image2}   # LIBERO；Molmo 系换相机名
  state_key: observation.state
  chunk_size: 10
```

### X-VLA（EE 口径，已合入上游主线 #168）

EE 参数走 `action_type=ee`（镜像默认 qpos，config 切 ee）；`domain_id` 按官方 recipe（RobotWin
用 6）；fast_init 必须 false（EE 走 plan_path）。serve 用 `serve-robotwin.yaml`
（benchmark_profile=robotwin + domain_id=6 + model_path `2toINF/X-VLA-WidowX`；serve 侧需声明
`ee_pose`，warning advisory，动作实测是通的，见 #1）。

## 口径映射表（出 0 分先查这张）

| 项 | 说明 | 错了会怎样 |
|---|---|---|
| `action_dim` | 14 关节 / 16 EE / 7 单臂 | 截断补零变垃圾动作 |
| `image_keys` | 相机名映射，各家不一样 | 看错相机，照样跑满 400 步 |
| `state_key` | 本体状态字段 | 首步 proprio 即错 |
| `chunk_size` | 和 benchmark 节拍对齐 | 越界或卡顿 |
| 权重路径 | 单仓直指 / 分头走本地子目录 | `HFValidationError` 起不来 |

## spec warning 读法

episode 起点刷 `Spec mismatch` = 口径错配预警，先停手对表，不要烧卡硬跑。
`action [ee_pose]: benchmark expects it but server doesn't declare it` 只是 advisory，
400 步执行可照常（X-VLA EE 已验证）；真拦路的是 unknown kwarg（旧镜像，已退役）。

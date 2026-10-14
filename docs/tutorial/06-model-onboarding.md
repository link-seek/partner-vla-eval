# 06 模型接入

> 版本：v1.0（2026-10-14）。伙伴交两样：权重地址 + 一个 serve yaml。

## serve yaml 模板（三例同段式：定位/口径/权重/备注）

### DB-CogACT（关节口径，双臂+CALVIN）

```yaml
script: "src/vla_eval/model_servers/dexbotic/cogact.py"
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

### X-VLA（EE 口径，parked）

benchmark 只要关节，X-VLA 出 EE——现在接上必 0 分，等上游 issue #166。
`domain_id` 按官方 recipe（RobotWin 用 6）。

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

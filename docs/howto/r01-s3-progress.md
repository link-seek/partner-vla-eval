---
title: R01 S3 进度（长分支）
nav_exclude: true
status: living
---

# R01 S3 进度

> 工作方式（2026-11-28 起）：S3/S4 期间的脚本、文档、deck 修改**全部累积在长分支** `ops/r01-s3-2026-11`，
> 不再每个小修开一个 PR。等 ACT/DP 训练与验证到一个里程碑，再一次性开 PR 合并。
> 例外：必须立即生效的 workflow / payload 修复，仍单独合并（它们无法只在分支生效）。

---

## 计划

| 项 | 内容 |
|---|---|
| ACT | 5 task ×（clean_50 / randomized_500）= 10 ckpt，每个 40k 步 |
| DP | 同 10 个；入口已就绪（`scripts/r01/s3_train_dp.sh`，1 epoch 干跑通过） |
| 训练入口 | `scripts/r01/s3_train_act.sh` / `s3_train_dp.sh`（自动换算 epochs、`--ipc=host`、产物校验） |
| 评测入口 | `smoke_serve.sh` 新增 `--task-config`（Easy/Hard）与 `--ckpt-layout serve`（DP 训练产物） |
| 链条 | `scripts/r01/s3_act_chain.sh` / `s3_dp_chain.sh`（顺序跑、已有 ckpt 跳过、失败即停） |
| 镜像 | `vla-robotwin-train:dev`（einops + dm_control） |
| 数据 | `/data/robotwin-train`（5 task，A=50 / B=550） |
| 产物 | `/root/r01/r01-ckpt/<task>-<regime>-s0/policy_last.ckpt` |

## 进度

| task / regime | 状态 | 备注 |
|---|---|---|
| grab_roller / clean_50 | ✅ | 3h35m；GPU1 1 集 smoke **1/1 success** |
| grab_roller / randomized_500 | ✅ | 3h10m；Hard 1 集 smoke **1/1 success** |
| adjust_bottle / clean_50 | ✅ | 3h38m；Easy 1 集 smoke **1/1**（bundled seeds） |
| adjust_bottle / randomized_500 | ✅ | 3h30m；Hard 1 集 smoke **1/1** |
| place_phone_stand / clean_50 | ✅ | 3h38m；Easy 1 集 0/1（num_errors=0，链路正常） |
| place_phone_stand / randomized_500 | ✅ | 3h31m；Hard 1 集 0/1（num_errors=0） |
| click_bell / clean_50 | 🔄 | 2026-11-28 18:53Z 起 |
| click_bell / randomized_500 | ⏳ | |
| handover_block / clean_50 | ⏳ | |
| handover_block / randomized_500 | ⏳ | |

## DP 入口（2026-11-28 干跑）

`bash scripts/r01/s3_train_dp.sh --task grab_roller --regime clean_50 --gpu 1 --epochs 1 --dry-run`

- 36 batch/epoch（batch=128, N=50）→ 40k 步约 1112 epoch，预计 **~7.4h/ckpt**
- ckpt 落点修正：`save_checkpoint` 的路径相对 CWD（`policy/DP/checkpoints/`），不在 hydra.run.dir；
  脚本会取出并复制成 serve 期望的 `serve/<task>-<clean_50>-50-0/50.ckpt`
- 干跑产出：`50.ckpt` **1.5G** + `run.json`
- serve 加载验证（GPU1，1 集）：**num_errors=0**（1 epoch 未训练，success 0/1 属预期）
- serve 加载验证（GPU1，1 集）：**num_errors=0**（1 epoch 未训练，success 0/1 属预期）

## 实测吞吐

- 40k 步（5715 epoch，clean_50）≈ **3h35m**
- 10 个 ckpt 预计 **36–45 小时**（ACT）
- 总周期（含 S4）预计 **4–6 天**，预算约 **¥3500–5000**

## 怎么查

```bash
ssh root@114.116.228.0 'tail -5 /root/r01/r01-ckpt/logs/chain.log'
ssh root@114.116.228.0 'for d in /root/r01/r01-ckpt/*-s0; do
  [ -f "$d/policy_last.ckpt" ] && echo "DONE $(basename $d)"; done'
```

## S4 准备

- `smoke_serve.sh` 已支持 `--task-config demo_clean|demo_randomized` 与 `--skip-expert false`（bundled seeds）——S4 必须用 bundled，否则会出现 `UnStableError`（seed 100000 的 bottle 不稳定，2026-11-28 实测）
- `smoke_serve.sh` 支持 `--task-config demo_clean|demo_randomized`（2026-11-28），
  每个 ckpt 可跑 Easy/Hard 两列
- 计划：20 ckpt × 2 难度 × 50 ep = 2000 集；按 ckpt 逐条跑，聚合进 R01 表

## 合并计划

- 里程碑 1：ACT 10 个 ckpt 完成 + 至少 3 个 serve 1 集 smoke → 开 PR
- 里程碑 2：DP 完成 + S4 评测 → 再开 PR（含最终报告）

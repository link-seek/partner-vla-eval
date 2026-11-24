# ACT / DP 适配器：首次 smoke 手册（B3）

> 状态：**适配器已写、未验证**。2026-11-24 机器被 B1 Hard 评测占用，没跑过 smoke。
> 目标：把"官方 ckpt → 本仓 harness"这条链路一次性打通，之后 R01 的 20 个 ckpt 都能直接上榜。

## 0. 依赖体检（2026-11-24 实测，`vla-eval-robotwin:0.8.0-ee-slim`）

在 robotwin conda 环境里实际导入过官方 policy 包，结论：

| 项 | 结果 | 含义 |
|---|---|---|
| `policy.ACT.deploy_policy` | ✅ 可导入（`get_model/encode_obs/reset_model` 都在） | ACT 走现成 robotwin 镜像即可 |
| `policy.DP.deploy_policy` | ❌ `ModuleNotFoundError: hydra` | DP 需另烘镜像（还缺 `dill`） |
| `diffusion_policy` | ✅ vendored 在 `policy/DP/diffusion_policy`，`dp_model.py` 自己 append 进 sys.path | 不用另装 |
| `IPython` / `torch` / `cv2` / `h5py` | ✅ 都在 | ACT 的模块级 `e = IPython.embed` 只是引用，不阻塞导入 |
| `detr`（顶层） | ❌ 但 ACT 内部 `from .detr.main` 相对导入可用 | 不影响 ACT |

**因此**：
- ACT 优先用 `vla-eval-robotwin:0.8.0-ee-slim` 起 serve（镜像里已有依赖）
- DP 需要 `vla-serve-robotwin-dp`，把 `hydra`、`dill` 烘进去（V100 禁止现场 pip）

## 0.1 前置

- 0002 空闲（`nvidia-smi` 两卡都空；`docker ps` 没有 cogact-serve / kind_*）
- 本地有 `vla-eval-robotwin:0.8.0-ee-slim` 与一个能起 serve 的镜像
  （ACT/DP 依赖 `detr`、`diffusion_policy`，在 robotwin 镜像里；若 serve 镜像缺，
  需先按 `docker/Dockerfile.serve-*` 的套路烘一个 `vla-serve-robotwin-act`）

## 1. 确认官方代码路径

```bash
docker run --rm --entrypoint bash swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-robotwin:0.8.0-ee-slim -c '
  ls -d /app/RoboTwin/policy/ACT /app/RoboTwin/policy/DP
  sed -n "1,40p" /app/RoboTwin/policy/ACT/deploy_policy.yml'
```

要确认三件事（决定 serve yaml 填什么）：
1. `action_dim`（默认 14）
2. `ckpt_dir` 的约定：ACT 读 `<ckpt_dir>/policy_last.ckpt` + `<ckpt_dir>/dataset_stats.pkl`
3. DP 读 `<task>-<ckpt_setting>-<expert_data_num>-<seed>/<checkpoint_num>.ckpt`

## 2. 起 serve（1 task）

```bash
# ACT
docker run -d --name robotwin-act-serve --gpus '"device=0"' --network host \
  -v $PWD/configs:/work/configs:ro -v /root/robotwin-train:/root/robotwin-train:ro \
  -w /work/harness "$SERVE_IMAGE" \
  vla-eval serve -c /work/configs/model_servers/serve-robotwin-act.yaml
docker logs -f robotwin-act-serve      # 等 "serve UP"
```

判据：
- 日志出现 `Loaded policy weights from ...policy_last.ckpt`（ACT）
- 端口 8000 可连
- 不出现 `Spec mismatch`（出现就停手，先对 `reference/action-mapping.md`）

## 3. 跑 1 task × 1 ep

```bash
python3 - <<'PY'  # 或用现成的 run yaml
PY
TASKS=grab_roller EPISODES=1 SHARDS=1 bash scripts/ci/ci_robotwin_full.sh
```

要看的三行：
- `Spec validation passed (server↔benchmark compatible)`
- `[1/1] grab_roller ep0: SUCCESS|FAIL`
- `chunk_exit=0`

## 4. 通过标准（三条全满足才算 B3 完成）

1. serve 起来且权重加载成功（日志有 `Loaded policy weights`）
2. 1ep 跑完不抛异常，`chunk_exit=0`
3. `aggregate.json` 有 `episodes[0].metrics`（哪怕是 fail，也要有判定而不是 error）

> 允许 FAIL：单集会 0 分很常见（噪声 ±100pp）。**不允许的是 ERROR / spec mismatch / 动作维度错**。

## 5. 常见失败与对策

| 现象 | 原因 | 对策 |
|---|---|---|
| `ModuleNotFoundError: detr` / `diffusion_policy` | serve 镜像没烘依赖 | 从 robotwin 镜像派生一个 serve 镜像，或直接用 robotwin 镜像起 serve |
| `KeyError: head_camera` | 考场相机名与 serve 不一致 | 对 `reference/action-mapping.md` |
| `策略返回 15 维动作，与 action_dim=14 不符` | 官方 ckpt 不是 aloha-agilex 14 维 | 换 ckpt 或改 `action_dim` |
| 动作全程不动 | 图像通道/归一化错（CHW vs HWC、0-1 vs 0-255） | 见适配器 `_to_robotwin_obs` 的三个分支 |
| `ACT 需要 usr_args 的 ['task_name']` | DP/ACT 参数混填 | 看 `deploy_policy.yml` 对应段 |

## 6. 跑通之后

1. 在 `configs/registry/model-registry.json` 把 `act-baseline` / `dp-baseline`
   的 `status` 从 `dropped` 改成 `verified`，补 `ckpt_revision`
2. 进 `model-matrix.yml` 跑 5 task（`weight_type` 已是 `finetuned`，会自动与 shared 分组）
3. 更新 `docs/tutorial/leaderboard.md` 的准入表

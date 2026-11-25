# Workflows 索引

> GitHub **只识别 `.github/workflows/*.yml`**，不支持子目录。所以"拆分"只能靠命名与本文档分类，
> 不能靠建 `manual/` 子目录（原 C5 方案有误，已改）。

## 能点（生产，常规派活）

| 文件 | 用途 | 参数 |
|---|---|---|
| `model-matrix.yml` | 基模榜单：逐模型 × 逐 task 出数，自动开关机，落 OBS `leaderboard/` | models / tasks / episodes / shards / video / obs_prefix |
| `pi0-robotwin-full.yml` | RobotWin 全量 chunk（按 task 50ep） | tasks / episodes / shards / video / obs_prefix |
| `r01-prep.yml` | R01 训练数据下载/解包/manifest | tasks / data_root |
| `pi0-robotwin-smoke.yml` | RobotWin smoke（1 task×1ep，只验链路） | 无 |
| `pi-libero-smoke.yml` | LIBERO smoke | 无 |
| `pi-calvin-smoke.yml` | CALVIN smoke | 无 |
| `pi0-molmo-smoke.yml` | Molmo 路 smoke（待转 SWR serve） | 无 |

## 镜像（外网构建机，别在 V100 上点）

| 文件 | 用途 |
|---|---|
| `build-serve.yml` | 打 `vla-serve-*`（含 X-VLA 的 `-ee16` 变体） |
| `build-benchmark-slim.yml` | 打 RobotWin 统一 slim 镜像 |
| `build-payload.yml` | 打 `vla-payload`（V100 取脚本用） |
| `sync-images.yml` | skopeo 直拷 ghcr→SWR（不落盘） |
| `mirror-swr-ghcr.yml` | SWR→GHCR 公开镜像（对外可拉） |
| `export-assets.yml` | 资产打包（一次性） |

## 底座（开关机与维护）

| 文件 | 用途 |
|---|---|
| `power.yml` | 可复用开关机（被上面各 workflow `uses:`，勿单独点） |
| `power-selftest.yml` | 开关机自检 |
| `repair-v100.yml` / `repair-v100-0001.yml` | runner 掉线修复（token 现开现删） |
| `ts-join-v100.yml` | tailnet 加入 |
| `audit-v100.yml` | 机器审计（可复用，登记为 rare） |

## 排障（一次性，用完即弃）

| 文件 | 用途 |
|---|---|
| `secret-hygiene.yml` | gitleaks 真值扫描（每个 PR 必跑） |

## 门禁

| 文件 | 用途 |
|---|---|
| `lint.yml` | push 即跑：语法、版本 pin、榜单 schema、路径、报告自洽、registry、覆盖（7 道） |
| `queue-conductor.yml` | 只记账不推进（单驾驶员模式的观测器） |

---

**约定**：新增 workflow 请在上面对应小节补一行，并在 `scripts/gates/infra-inventory.json` 登记 `kind`。
**一次性排障不要提交 workflow**——开分支做完即删（见 CONTRIBUTING 第二节）；
确有长期价值的排障能力收敛进 `ops.yml`（一个入口 + 多 action），登记 `rare` 并写 owner/触发条件。

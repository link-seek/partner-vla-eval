---
title: How-to：运维入口 ops.yml（4 个 action）
nav_exclude: true
---

# How-to：运维入口 `ops.yml`

> 4 个原先独立的一次性 workflow 已收敛成一个常驻入口：
> `audit` / `repair-0002` / `repair-0001` / `tailnet-join`。
> 逻辑在 `scripts/ops/*.sh`，可本地执行（`ACTION=audit V100_SSH_PASS=... bash scripts/ops/run.sh`）。

## 每个 action 该跑在哪个 runner

**2026-11-25 实测：原 `hw21` runner 已不在线**（组织级只剩 `ecs-0002`，仓级只剩 `ecs-0001`）。
所以 `runner` 是输入参数，不是写死的。

| action | 推荐 runner | 原因 |
|---|---|---|
| `audit` | `V100-0001`（或 `V100-0002`） | 只读；从 0001 也能 SSH 到 0002 |
| `repair-0001` | `V100-0002` | 到 0001 的 22 通 |
| `repair-0002` | `V100-0001` | **不能**在 0002 自己身上重配 agent——会把自己踢下线，job 直接死 |
| `tailnet-join` | 需要在 tailnet 上的 runner | 要经 hw41 `100.91.222.51` 跳板 |

**已知缺口**：`tailnet-join` 目前没有可用 runner（hw21 下线后，tailnet 上没有可跑 Actions 的节点）。
真要用时，先在 tailnet 上恢复一个 runner，或按 `docs/howto/tailnet-join.md` 手工执行。

**另一个坑**：`V100-0002` 是**唯一**能跑 `model-matrix` 的 runner，长评测期间会被占满
（`busy=true`），此时 `ops.yml` 会在队列里等。要修机器就把 `runner` 指到 `V100-0001`。

## 首次实证（2026-11-25）

```
run 45606352244  ops / action=audit / runner=V100-0001
结论             success
远端             [ops] remote(114.116.228.0) exit=0
```

关键输出（说明它真的进了 V100 并执行了只读命令）：

```
=== disk ===
/dev/vda1  295G  54G  230G  19% /
/dev/vdb  1007G 559G  397G  59% /data

=== /data top ===
146G /data/checkpoints   96G /data/docker   56G /data/yjd
 51G /data/hf_cache      51G /data/gh-runner-0002   35G /data/datasets

=== gpu ===
0, Tesla V100-PCIE-32GB,  4248 MiB, 32768 MiB,   0 %   ← 空闲
1, Tesla V100-PCIE-32GB, 26142 MiB, 32768 MiB, 100 %   ← B1 在跑
```

## 四个 action 的 dry-run 实证（2026-11-25）

`DRY_RUN=true`（workflow 输入 `dry_run`）：只做目标解析 + TCP 22 探测 + 打印将执行的远端脚本，
**跳过** hcloud 开机 / token mint / `config.sh` / `tailscale up`。全部跑在 `V100-0001`。

| action | run | 结果 | 关键输出 |
|---|---|---|---|
| `audit` | 45606352244 | ✅ success | `remote(114.116.228.0) exit=0`，输出 df / du / docker images / nvidia-smi |
| `repair-0001` | 45608298221 | ✅ success | `target=root@1.94.192.234`、`tcp 22: open`、`PROD_GH_TOKEN 在位（长度 40）`、`OBS 凭证在位（长度 20）` |
| `repair-0002` | 45609058394 | ✅ success | `target=root@114.116.228.0`、`tcp 22: open`、`将通过 PROD_GH_TOKEN 现场 mint（dry-run 不真的 mint）`、打印完整远端脚本 |
| `tailnet-join` | 45609069686 | ✅ success | `跳板 hw41=100.91.222.51 tcp 22: **closed**`、`目标 V100 tcp 22: open`、`TS_API_KEY 在位（长度 61）` |

`tailnet-join` 那条 "closed" 就是前面说的**结构性缺口**：从 0001 到 hw41 不通，
所以这个 action 的 dry-run 能证明"参数拼装对了"，但**不能**证明"能真的把 V100 拉回 tailnet"。
要用它，得先有一个在 tailnet 上的 runner（或手工按 `docs/howto/tailnet-join.md` 做）。

### 试跑中发现并修掉的两个真问题

| 问题 | 表现 | 根因 | 修法 |
|---|---|---|---|
| `repair-0002` 一开始直接失败 | `FAIL: 缺环境变量 V100_REG_TOKEN` | 该 secret 早已被删——**这个修复能力在重构前就已经坏了** | 改成与 `repair-0001` 一致：用 `PROD_GH_TOKEN` 现场 mint |
| `tailnet-join` 卡住不返回 | run 一直 in_progress | `tcp_check` 用 `/dev/tcp` **没有超时**，对不可达的 hw41 等到系统 TCP 超时 | `tcp_check` 加 `timeout 5` |

## 排错记录（都是实测踩到的）

| 现象 | 原因 | 解法 |
|---|---|---|
| 排队不动 | 指定了 `hw21`，但该 runner 已不存在 | `runner` 用实际在线的标签（`V100-0001`/`V100-0002`） |
| `EACCES ... rmdir '/data/gh-runner/_work/...'` | self-hosted workspace 被 docker `-v` 建成 root 属主，`checkout` 清不掉 | 已改为**不 checkout**，用 curl 取 tarball 到 `/tmp/ops-repo` |
| `gh: command not found` | 0001 runner 没装 gh CLI | 已改为 `curl -H "Authorization: Bearer $GITHUB_TOKEN"` |

**原则**：运维入口必须在"环境已经坏了"时也能跑，所以不能依赖 workspace、不能依赖 `gh`。

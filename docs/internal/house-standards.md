# 本仓遵循的 house 标准（镜像 / workflow / 门禁）

> 2026-11-25。起因：我在 ACT/DP 镜像这条线上连续自造了四套东西（本机构建脚本、digest 手抄、
> 端口轮询、nohup 盯任务），都是"能跑就行"。对照 `link-seek/docker-images` 和 `link-seek/infra`
> 已有的做法后发现：**这些坑人家早就标准化了，正确动作是抄，不是发明**。
> 本文只记"我们抄了哪条、为什么、落在本仓哪个文件"，不复制对方的实现细节。

## 一、抄了什么

| 问题 | 我的自造做法（已废弃/降级） | house 标准 | 本仓落点 |
|---|---|---|---|
| 取镜像 manifest digest | `docker inspect .RepoDigests \| sed`（还会和 `config.digest` 混淆） | `docker buildx imagetools inspect --format '{{.Manifest.Digest}}'` | `build-serve.yml`（临时 tag → digest → 不可变校验 → 转正） |
| 版本 tag 被重打 | 无守卫，tag 可静默挪走 | **tag 不可变**：临时 tag 构建 → 取 digest → 与现有 tag 比对 → 不同则红，`force_retag=true` 才放行 | `build-serve.yml`（沿用 `docker-images/bake-stack.yml` 的语义） |
| 转正到正式 tag | `docker push` 重传 | `docker buildx imagetools create -t <正式> <临时>`（registry 侧改 tag，不重传层），跨境失败重试 3 次 | 同上 |
| workflow 静态校验 | 只 `yaml.safe_load` | **actionlint**（`raven-actions/actionlint@v2.2.0`，工具 pin `1.7.12`，shellcheck/pyflakes 关） | `.github/workflows/actionlint.yml` |
| 镜像供应链扫描 | 无 | trivy（CRITICAL/HIGH `--exit-code 1`）+ SBOM(cyclonedx) + `.trivyignore` 白名单 | **未做**，列为后续（见三） |
| 跨境拉基座慢 | 干脆搬到 0002 本机构建 | CI 构建 + **双推 GHCR/SWR**，境外 runner 走 GHCR（同 digest、同字节） | **未做**，列为后续（见三） |
| 盯长任务 | `nohup bash 循环` | `gh run watch --exit-status`；巡检交给 Actions `schedule` | 本次改用 `gh run watch` |
| 等容器就绪 | 手写 TCP 轮询 | Docker 原生 `--health-cmd` + 轮询 `.State.Health.Status` | `scripts/ci/smoke_serve.sh` |

## 二、本仓自己的东西（这些不是"非标"，是领域数据）

- `configs/registry/model-registry.json`：我们的模型/考场真源，schema 是本仓定义的，别人没有。
  digest 只能由**构建链路**写回这个文件，不能人眼抄。
- `scripts/ci/smoke_serve.sh`：这是**测试**，不是基础设施。它把"接缝契约"变成断言
  （输出目录必须落在预期路径、端口必须空闲、容器必须 healthy、aggregate 必须在）。
- `scripts/gates/check_contracts.py`：纯静态契约门禁（task 清单不硬编码 + serve yaml 顶层键 ⊆ 允许集、
  args ⊆ `__init__` 参数、script 必须是镜像内路径）。不需要 GPU/docker。

## 三、还没做到的（明确欠账，不假装完成）

1. **trivy 扫描 + SBOM**：bake-stack 有，我们 `build-serve.yml` 没有。真空档：无法回答
   "这个 serve 镜像有没有 CRITICAL 漏洞"。补法：在 build 后加 trivy 步骤 + 仓内 `.trivyignore`。
2. **CI 构建路径没跑通**：`FROM swr…@digest` 在 GitHub runner 上要跨境拉 11.3GB 基座。
   house 的解法是双推 GHCR 后从 GHCR 拉。要做的话：把 bench 镜像镜像到 GHCR（一次），
   Dockerfile 的 `ARG BASE` 默认指向 GHCR（digest 不变，因为内容相同），CI 就能在几分钟内构建。
   在此之前，robotwin 基座镜像只能在 0002 上构建（本机基座命中，6~11 秒）。
3. **renovate**：`infra` 有 `renovate.json` 管 pin 升级。我们的版本 pin（harness ref、镜像 tag）
   还是手工维护。

## 四、判据

> 遇到"要写个脚本解决"的时候，先做两件事：查本仓有没有，再查 `docker-images` / `infra` 有没有。
> 两边都没有，才自己写，并在这里登记"为什么必须自建"。

## 五、合并记录（2026-11-25 晚）

一天里为每个事故加一个脚本，等于把事故固化成结构。做了一次合并：

| 原 | 现 | 说明 |
|---|---|---|
| `gates/check_task_list.py` + `model_servers/test_serve_contract.py` | `gates/check_contracts.py` | 同一类问题（配置契约），一个入口 |
| `ci/rebuild_serve.sh` | `build-serve.yml` | 构建只有一条路：CI + 不可变守卫；不再有"本机构建脚本" |
| `data/backfill_stats.py` | `gen_reports.py --backfill` | 报告相关只有一把工具 |
| lint.yml 里 10 个门禁步骤 | `gates/run_all.py`（一步） | 一条命令看全部门禁结果 |

原则：**一个事故不新增一个脚本**；先看能否并入既有入口。

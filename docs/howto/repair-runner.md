---
title: How-to：V100 runner 装机 / 修复
nav_exclude: true
---

# How-to：V100 runner 装机 / 修复

> **什么时候用**：GitHub 上的 runner 变 offline；或换机器后要重新注册 agent。
> **用错会怎样**：`config.sh remove` 用错 token 会把正常 agent 踢掉；两台机器（0002/0001）
> 的 agent 互斥，别把 0002 的凭证写到 0001 上。
>
> 自动化入口：`.github/workflows/ops.yml`，`action=repair-0002`（0002 双 agent）/ `repair-0001`（0001 单 agent）。
> 逻辑在 `scripts/ops/repair-0002.sh`、`scripts/ops/repair-0001.sh`（可本地执行，凭证走环境变量）。
> 本文是它们的**手工等价步骤**——workflow 挂了就照这里做。

## 0. 先确认现状

```bash
gh api repos/link-seek/partner-vla-eval/actions/runners \
  --jq '.runners[]|"\(.name)\t\(.status)\t\(.busy)\t\([.labels[].name]|join(","))"'
```

预期（2026-11 现状）：

| 机器 | agent 目录 | 名称/标签 |
|---|---|---|
| 0002 `114.116.228.0` | `/data/gh-runner`、`/data/gh-runner2` | `V100,V100-0002` |
| 0001 `1.94.192.234` | 单 agent | `ecs-0001-org`、`V100,V100-0001` |

offline 且重启 `svc.sh` 无效 → 通常是凭证被回收，需要重新注册。

## 1. 取注册 token（有效期 1 小时）

```bash
TOKEN=$(gh api -X POST repos/link-seek/partner-vla-eval/actions/runners/registration-token --jq .token)
```

## 2. 装机（0001 单 agent；0002 对两个目录各做一次）

```bash
ssh root@<host>            # 0002: 114.116.228.0 / 0001: 1.94.192.234
id runner 2>/dev/null || useradd -m -s /bin/bash runner

VER=$(curl -sS https://api.github.com/repos/actions/runner/releases/latest | python3 -c 'import json,sys;print(json.load(sys.stdin)["tag_name"].lstrip("v"))')
mkdir -p /data/gh-runner && cd /data/gh-runner
curl -fsSL -o r.tar.gz "https://github.com/actions/runner/releases/download/v${VER}/actions-runner-linux-x64-${VER}.tar.gz"
tar xzf r.tar.gz && chown -R runner:runner /data/gh-runner

# config 必须以 runner 身份跑（agent 文件属 runner）；svc 启停用 root
su -s /bin/bash runner -c "cd /data/gh-runner && ./config.sh --unattended \
  --url https://github.com/link-seek --token '$TOKEN' \
  --name V100-0002 --labels V100,V100-0002 --work /data/gh-runner/_work --replace"
cd /data/gh-runner && ./svc.sh install runner && ./svc.sh start
```

**0002 的第二个 agent**：把 `/data/gh-runner` 换成 `/data/gh-runner2`、`--name` 换成 `V100-0002-2`。

## 3. 验收

```bash
gh api repos/link-seek/partner-vla-eval/actions/runners --jq '.runners[]|"\(.name) \(.status)"'
systemctl status 'actions.runner.*' | head -20      # 机器上
```

`status: online` 即成功。再跑一次最小 workflow 确认能派单。

## 坑（都踩过）

| 坑 | 现象 | 解法 |
|---|---|---|
| 用 root 跑 `config.sh` | agent 目录属主混乱，`svc.sh` 起不来 | config 必须 `su -s /bin/bash runner -c` |
| token 用仓库 token | `config.sh` 报 404/401 | 必须用 `actions/runners/registration-token` |
| 0002 两个 agent 同名 | 后注册的把前一个顶掉 | `--name` 必须不同（`--replace` 只替换同名） |
| runner 用户无 `/data` 写权限 | `_work` 创建失败 | `chown -R runner:runner /data/gh-runner*` |
| 忘装依赖 | `sudo: command not found` | 该机 sudo 不可用；用 root 执行 svc 操作 |

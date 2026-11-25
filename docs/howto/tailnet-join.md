---
title: How-to：V100 加入 tailnet
nav_exclude: true
---

# How-to：V100 加入 tailnet

> **什么时候用**：runner 重装系统后 `tailscale status` 里看不到它；或换机后需要重新入网。
> **用错会怎样**：key 一旦写进机器磁盘就等于泄漏；本文的 key **只在命令行传参**，不落盘、不进日志。
>
> 自动化入口：`.github/workflows/ts-join-v100.yml`（登记为 `rare`）。
> 本文是它的手工等价步骤。

## 前提

- V100 已装 tailscale（2026-11-09 装过一次，`tailscale version` 有输出即可）
- 组织 secret `TS_API_KEY`（tailnet admin key）可用；本地用 `$TS_API_KEY` 引用
- 有跳板：hw41 `100.91.222.51`（V100 在入网前不可直连，需经跳板）

## 1. 现场 mint 一个一次性 authkey

```bash
KEY=$(curl -sS -u "$TS_API_KEY:" -H 'Content-Type: application/json' \
  -d '{"capabilities":{"devices":{"create":{"reusable":true,"ephemeral":false,"preauthorized":true}}},"expirySeconds":3600}' \
  https://api.tailscale.com/api/v2/tailnet/-/keys | python3 -c 'import json,sys;print(json.load(sys.stdin)["key"])')
```

## 2. 经跳板让 V100 入网

```bash
ssh root@100.91.222.51 \
  "ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@114.116.228.0 \
   'tailscale up --authkey=$KEY --hostname=v100-0002 --accept-routes'"
```

要点：
- **key 走命令行参数**，不要 `scp` 一份到机器上
- `--hostname` 固定成 `v100-0002`，否则重装后 tailnet 里会出现同名多设备

## 3. 验收

```bash
# 在本机（容器）看
tailscale status | grep -i v100

# 在机器上确认能出网
ssh root@<v100-tailnet-ip> 'tailscale status | head -3; curl -sS -m 5 https://api.github.com >/dev/null && echo egress-ok'
```

## 坑

| 坑 | 现象 | 解法 |
|---|---|---|
| 直接从本机 ssh V100 | 超时（未入网） | 必须经 hw41 跳板 |
| key 写进文件 | 磁盘上留真值 | 只在命令行传，`expirySeconds` 给短 |
| 重装后 hostname 变化 | tailnet 里出现重复设备 | 固定 `--hostname` |
| 忘了 `--accept-routes` | 访问不到 tailnet 内其他段 | 加上；否则只能被访问 |

---
title: How-to：核对/调整 OBS 桶生命周期
nav_exclude: true
---

# How-to：核对/调整 OBS 桶生命周期

> **什么时候用**：怀疑产物被误删；或要改保留策略（例如把 `下载/` 从 7 天改成 3 天）。
> **用错会怎样**：`lifecycle -method=put` 会**整份替换**规则集（不是追加）；写错前缀会误删线上产物。
> 改之前务必先 `-method=get` 导出、备份到仓外。

## 在哪执行

只能在内网机器上（0002 有 `obsutil` + `/root/.obsutilconfig`）。仓库容器里没有 obsutil。

```bash
ssh root@<v100-host>
obsutil version          # 5.8.3 / obssdk 3.24.12
```

## 1. 查看当前规则（只读）

```bash
obsutil lifecycle obs://so101-sim-pipeline -method=get -localfile=/tmp/lifecycle.json
cat /tmp/lifecycle.json
```

2026-11-25 实测（已存档 `docs/adr/evidence/obs-lifecycle-2026-11-25.json`）：

```json
{"Rules":[{"ID":"auto-delete-download-7d","Prefix":"下载/","Status":"Enabled",
           "Expiration":{"Days":7}}]}
```

也就是说：**只有 `下载/` 前缀 7 天过期；`eval/`、`assets/` 没有任何规则 = 默认永久保留。**

## 2. 看某个前缀占多大

```bash
obsutil ls obs://so101-sim-pipeline/eval -s -du
# → [DU] Total prefix [eval] size: 167.77MB
```

（这个 obsutil 版本没有 `du` / `bucketversioning` 子命令，用 `ls -s -du` 替代。）

## 3. 改规则（谨慎）

先把现有 JSON 备份：

```bash
cp /tmp/lifecycle.json /tmp/lifecycle.$(date +%F).bak.json
```

编辑后再 `put`——**是整份替换**，所以 JSON 里必须包含所有要保留的规则（包括 `下载/` 那条）：

```bash
obsutil lifecycle obs://so101-sim-pipeline -method=put -localfile=/tmp/lifecycle.new.json
obsutil lifecycle obs://so101-sim-pipeline -method=get -localfile=/tmp/after.json   # 回读确认
```

## 4. 当前策略的理由（别随手删）

- `eval/` 永久保留：ADR-0002 决定"sqlite + 产物全留"，因为它们是唯一能重算 aggregate、逐集复核、崩溃救援的载体
- 成本可忽略：`eval/` 167.77MB ≈ **¥0.017/月**
- `下载/` 7 天：那是 url2hc 的中转目录，属临时件

要重新评估保留策略，先改 ADR，再改桶——**顺序不能反**。

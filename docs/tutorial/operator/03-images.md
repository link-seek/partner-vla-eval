---
title: 运维 03：镜像查版
parent: 评测教程
nav_order: 7
---

# 运维 03：镜像从哪来、钉哪个版

> 目标：说出任意镜像的来源、版本真源、用哪个。
> 时间：10 分钟 ｜ 前置：`02-duty-dispatch.md` ｜ 你将得到：查版三板斧 + 升级流程。
> 读法：本篇只查版，镜像清单和各镜像的分工见 [01-system-and-run.md](./01-system-and-run.md#镜像从哪来为什么不是官方原图)。

## 操作：查版三板斧

1. **看真源**：`docker/versions.yaml` 是唯一版本真源。Dockerfile 只许用 ARG 引用它，不许手写版本号；漂移会被 lint 拦下（`check_versions.py`）。
2. **对表找 tag**：benchmark 用 `vla-eval-robotwin:0.8.0-ee-slim`（**唯一生产**），serve 按模型用 `vla-serve-<名>:0.8.0`；**X-VLA 例外，必须用 `vla-serve-xvla:0.8.0-ee16`**——`0.8.0` 是旧适配器（只出 20D），喂给 EE benchmark 会直接报 `action_type='ee' takes a 16D action, got 20D`，这个坑 11-23 已经踩过一次。一律钉版本，不用 `latest`。
3. **确认离线前提**：V100 只拉不打。要新镜像，走下面「升级流程」，不要在 V100 上动手。

## 操作：升级流程

要新版镜像，按顺序走：

1. 改 `docker/versions.yaml` 的 pin。
2. 外网构建机重打：`sync-images`（skopeo 直拷 ghcr→SWR，不落盘）、`build-serve` 或 `build-payload`。
3. 推 SWR，V100 拉新 tag。

V100 上永远不打镜像、不装包——现场装 = 不可复现。

## 原理：serve 镜像烘焙三件套

`Dockerfile.serve-*` 都按同一个套路烘焙：

1. harness 源码 + 模型桥依赖 clone 进镜像（V100 不许 git）。
2. V100 补丁烘入（torch 钉 cu126 系、requires-python 放宽、fp16 等），不再运行时 sed。
3. `uv run <server.py> --help` 跑一次暖缓存；运行时 `UV_OFFLINE=1`。

**烘焙 = 改镜像 = 版本化**：每次改动单独记一笔，并用同一组任务跑 stock vs slim 对照，确认分数不变（实测 18/20 vs 18/20，差 0）。

## 检查点

- [ ] V100 报缺包？回免费机烘进镜像重打，不要现场装。
- [ ] 版本对不上？先看 `versions.yaml`，再看镜像 tag，最后看 lint——上次出问题就是镜像 tag 和实际源码对不上，V100 上没有 checkout 可兜底。
- [ ] 镜像传不动（28GB）？skopeo 直拷不落盘 + SWR 内网拉，不要跨洋推大包。

## 下一步

* 对外分发：`ghcr.io/link-seek/<名>:<tag>`（镜像已全部转 public）；论文里贴 digest 不贴 tag，sha256 记在 `docs/reproducibility.md`。
* 栈差异对照的来龙去脉 → [explanation/01-stack-effects.md](../explanation/01-stack-effects.md)。
* 15 条排障 → [reference/error-codes.md](../reference/error-codes.md)。

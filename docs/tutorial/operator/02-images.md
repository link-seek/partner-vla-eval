---
title: 运维 02：镜像查版
parent: 评测教程
nav_order: 7
---

# 运维 02：镜像从哪来、钉哪个版

> 目标：说出任意镜像的来源、版本真源、用哪个。
> 时间：20 分钟 ｜ 前置：`01-machines-ci.md` ｜ 你将得到：查版三板斧。
> 读法：`操作`是查版手册；`原理`讲 4→1 收官和烘焙逻辑。

## 操作：查版三板斧

1. 看 `docker/versions.yaml`——**唯一真源**。harness 全系 0.8.0，
 Dockerfile 只许 ARG 引用，不许手写版本号；lint 门禁漂移（`check_versions.py`）。
2. 对表找镜像：bench 用 `vla-eval-robotwin:0.8.0-ee-slim`（**唯一生产**），
 serve 按模型用 `vla-serve-<名>:0.8.0`，tag 钉版不对 `latest`。
3. 要新版/新镜像：dispatch 免费机的 `sync-images`（skopeo 直拷 ghcr→SWR，
 不落盘）或 `build-serve`/`build-payload`；V100 只拉不打。

## 操作：本地编排（`docker-compose.verify.yml`）

bridge 网，`1 serve + 1 benchmark`，profile 按榜切。
server 地址一律 `--server-url` 覆盖，yaml 里不动。benchmark 容器挂 docker.sock
（harness `run --docker` 自己起环境容器，上游机制）。

## 原理：清单（4→1 收官，10-27）

| 镜像 | 说明 |
|---|---|
| `vla-eval-libero:0.8.0`（~6GB）/ `calvin:0.8.0`（~9.6GB） | 单臂/长程考场，skopeo 直拷 |
| `vla-eval-robotwin:0.8.0`（~28GB） | 回滚位（不动，只救命） |
| `vla-eval-robotwin:0.8.0-ee-slim`（~11GB） | **唯一生产**：slim 三刀 + EE 烘进 + P2 烘进，qpos 默认 |
| `vla-payload:latest/:<sha>`（几 MB） | V100 执行侧唯一代码来源（scripts+configs+versions.yaml），零 checkout |
| `vla-serve-<cogact/pi05/xvla/smolvla/pi0>:0.8.0` | 依赖全烘 + uv 预热，V100 离线跑；权重**不进**镜像（15GB/头，盘缓存） |
| `vla-verify:0.1`（小） | 预热/杂活（`hf-download` 钉别名） |

对外可拉：`ghcr.io/link-seek/<名>:<tag>`（SWR→GHCR mirror 全量 success，11 包 public）；
论文贴 digest 不贴 tag（`docs/reproducibility.md` 补 sha256）。

## 原理：serve 烘焙三件套（`Dockerfile.serve-*` 通式）

1. harness 源码 + 模型桥依赖 clone 进镜像（V100 不许 git）。
2. V100 补丁烘入（torch 钉 cu126 系、requires-python 放宽、fp16 等），不再运行时 sed。
3. `uv run <server.py> --help` 跑一次暖缓存；运行时 `UV_OFFLINE=1`。

烘焙 = 改镜像 = 版本化 + 差值单列（A3 自证：stock vs slim 18/20 vs 18/20，差 0）。

## 检查点

- [ ] V100 报缺包？回免费机烘进镜像重打，不要现场装（现场装=不可复现）。
- [ ] 版本对不上？先看 `versions.yaml`，再看镜像 tag，最后看 lint（8 号规则零 checkout 那次就是版本漂移）。
- [ ] 镜像传不动（28GB）？skopeo 直拷不落盘 + SWR 内网拉，不要跨洋推大包。

## 下一步

栈差异对照的来龙去脉 → `explanation/`（待写）；15 条排障 → `reference/error-codes.md`（待写）。

# 05 镜像与部署集成

> 版本：v1.1（2026-10-27）。SWR：`swr.cn-north-4.myhuaweicloud.com/link-seek`，
> tag 钉版不对 `latest`（与 HARNESS_REF 对齐）；版本唯一真源 `docker/versions.yaml`。

## 镜像清单（4→1 收官，10-27）

| 镜像 | 来源 | 体积 | 说明 |
|---|---|---|---|
| `vla-eval-libero:0.8.0` | skopeo 直拷 ghcr | ~6GB | 单臂基线考场 |
| `vla-eval-calvin:0.8.0` | 同上 | ~9.6GB | 长程考场 |
| `vla-eval-robotwin:0.8.0` | 同上 | ~28GB | 回滚位（不动，只救命） |
| `vla-eval-robotwin:0.8.0-ee-slim` | 本仓打（Dockerfile.robotwin-unified） | ~11GB | **唯一生产**：slim 三刀 + EE 烘进 + P2 烘进，qpos 默认 |
| `vla-payload:latest/:<sha>` | 本仓打（Dockerfile.payload，scratch） | 几 MB | V100 执行侧唯一代码来源（scripts+configs+versions.yaml），零 checkout |
| `vla-serve-cogact:0.8.0` | 免费机构建 | 中 | 依赖全烘+uv 预热，V100 离线跑 |
| `vla-serve-pi05:0.8.0` | 同上 | 中 | 同上，pi05/Lerobot 系 |
| `vla-serve-xvla:0.8.0` / `-fp16` | 同上（DTYPE 构建参） | 中 | 精度对照组（fp16 全崩已证伪） |
| `vla-serve-smolvla:0.8.0` | 同上 | 中 | SmolVLA（libero finetune pin a24f1f） |
| `vla-serve-pi0:0.8.0` | 同上 | 中 | pi0（链路绿，checkpoint 待定） |
| `vla-verify:0.1` | 同上（SWR 拉，不本地构建） | 小 | 预热/杂活（hf-download 别名钉死） |

## serve 烘焙三件套（Dockerfile.serve-* 通式）

1. harness 源码 + 模型桥依赖 clone 进镜像（V100 不许 git）。
2. V100 补丁烘入（torch 钉 cu126 系、requires-python 放宽、fp16 等），不再运行时 sed。
3. `uv run <server.py> --help` 跑一次暖缓存；运行时 `UV_OFFLINE=1`。
4. 权重**不进**镜像（15GB/头太大），mirror 下到 V100 盘缓存永久有效。

## 编排

- `docker-compose.verify.yml`：bridge 网，`1 serve + 1 benchmark`，profile 按榜切。
  server 地址走 `--server-url` 覆盖，不写死。
- CI（`.github/workflows/`）：`pi-*-smoke`（单榜）/`pi0-robotwin-full`（分块全量，
  tasks/episodes/shards/video/bench_tag/skip_expert 全参数化）/`sync-images`/`build-serve`/`repair-v100`。
- 开关机 job 跑 hw21，GPU job 跑 V100，`if: always()` 保证关机。

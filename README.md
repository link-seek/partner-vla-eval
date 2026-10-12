# partner-vla-eval

伙伴模型评测：`vla-evaluation-harness`（`v0.7.0`）统一执行，
`RobotWin（双臂基线）+ LIBERO（单臂基线）+ CALVIN（单臂长程）` 三件套。
方案与口径见 [Discussion #1](https://github.com/link-seek/partner-vla-eval/discussions/1)（过程问题记评论，教程后统稿）。

## 机器 / 网络分工（铁律）

只有 GitHub 免费 runner 有完整外网，其余都是内网。下载只能发生在有外网处：

| 机器 | 网络 | 只干 |
|---|---|---|
| GitHub 免费机 | 外网 | 打镜像（serve/benchmark 同步）→ SWR；下权重子集 → OBS 标准桶 |
| hw21 常驻机 | 几乎内网 | V100 开关机（hcloud API） |
| V100（`jushenzhineng-0002`，北京四） | 几乎内网 | 离线跑：SWR 内网拉镜像、OBS 内网拖权重、`UV_OFFLINE=1`，零下载 |

V100 上禁止：`pip/uv` 装包、git clone、HF 下载、ghcr 拉取。缺东西一律回免费机烘进镜像（见 `docker/`）。

## 仓库结构

```
configs/                  serve-*.yaml（模型）+ run-*.yaml（考场）
  serve-robotwin-cogact.yaml   DB-CogACT 双臂（当前参考模型，关节口径）
  serve-robotwin.yaml          X-VLA（EE 口径，benchmark 未接，parked）
docker/
  Dockerfile.verify       通用底座（torch/lerobot/vla-eval CLI）
  Dockerfile.serve-cogact DB-CogACT serve 镜像（依赖全烘，uv 预热，V100 离线跑）
scripts/
  ci_smoke.sh / ci_robotwin.sh / ci_robotwin_full.sh   三条 CI 编排（bash 只编排）
  upstream/run_sharded.sh                              上游分片脚本（v0.7.0 vendor）
.github/workflows/       smoke/full/sync/repair 四类 workflow
```

## 跑法

- smoke（单 task×1ep）：dispatch `pi0-molmo-smoke` / `pi0-robotwin-smoke`
- 全量（1 task×50ep/轮）：dispatch `pi0-robotwin-full`（tasks/episodes/shards/video 参数化）
- 镜像同步：dispatch `sync-images`（skopeo 直拷 ghcr→SWR）
- runner 掉了：dispatch `repair-v100`（token 现开、用完删 secret）

## Pin

- `vla-eval`: `v0.7.0`（镜像 tag 对齐 `0.7.0`，不跟 `latest`）
- 基准镜像：`swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-<libero|calvin|robotwin>:0.7.0`
- 权重：OBS 标准桶（V100 内网 endpoint 拖）

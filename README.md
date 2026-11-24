# partner-vla-eval

伙伴模型评测：`vla-evaluation-harness`（`v0.8.0`）统一执行，
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

> 划分现状与改进方案见 [docs/reports/layout-review.md](docs/reports/layout-review.md)。
> 本节由 CI 的 `scripts/gates/check_paths.py` 兜底：这里写的路径必须真实存在，否则 lint 红。

```
configs/                  serve-*.yaml（8，模型侧）+ run-*.yaml（13，考场侧）+ model-registry.json（榜单真源）
docker/
  Dockerfile.*            基座/benchmark/serve/payload 镜像（版本钉死走 docker/versions.yaml）
  versions.yaml           唯一版本真源（harness 0.8.0 / torch 2.6.0+cu126 / 上游 ref 40-hex）
  entrypoint-robotwin.sh  统一镜像入口（STATE_PATCH 激活补丁）
  robotwin-ee.patch       EE 通路补丁（上游 #168 合入前的本地兜底）
scripts/
  ci/                     6 条 CI 编排（bash 只编排，不写业务）+ ci/lib/common.sh
  gates/                  5 道门禁：check_versions / check_paths / check_registry /
                          check_reports / check_coverage
  data/                   prepare_robotwin_data.sh（R01 数据下载/解包/manifest）
  paths_allowlist.txt     允许"计划中/上游仓"路径的白名单
leaderboard/              自包含（对齐上游布局）
  leaderboard.json        榜单条目（一行一个 model×task×protocol）
  leaderboard.schema.json 结构约束（必填 ckpt_revision / weight_type / n / success）
  scripts/check_leaderboard.py  门禁：schema + 与 docs/data 对账
docs/                     GitHub Pages 源（just-the-docs）
  tutorial/               对外教程（Diátaxis：quickstart / operator / partner / reference / explanation）
  reports/                叙事报告（R01、工程化检视、目录检视）
  data/                   结果 JSON（每份报告一份，机器读）
  decks/                  汇报 deck（html + exports/pptx）
  internal/               内部过程稿（整改计划、上游草稿）
  archive/                论文 tex 等历史归档
.github/workflows/        25 个 workflow（生产 + 镜像构建 + 一次性排障）
```

**约定**：`README` 里出现的每个路径都受 lint 校验；新增目录请同步本节，否则 `check_paths.py` 会报 `PATH-DRIFT`。

## 跑法

- smoke（单 task×1ep）：dispatch `pi0-molmo-smoke` / `pi0-robotwin-smoke`
- 全量（1 task×50ep/轮）：dispatch `pi0-robotwin-full`（tasks/episodes/shards/video 参数化）
- 镜像同步：dispatch `sync-images`（skopeo 直拷 ghcr→SWR）
- runner 掉了：dispatch `repair-v100`（token 现开、用完删 secret）

## Pin

- `vla-eval`: `0.8.0`（唯一真源 `docker/versions.yaml`，镜像 tag 对齐，不跟 `latest`）
- 基准镜像：`swr.cn-north-4.myhuaweicloud.com/link-seek/vla-eval-<libero|calvin|robotwin>:0.8.0`（RobotWin 生产用 `0.8.0-ee-slim`）
- 权重：OBS 标准桶（V100 内网 endpoint 拖）

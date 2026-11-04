---
title: 运维 01：开卡排障
parent: 评测教程
nav_order: 6
---

# 运维 01：开卡、排队、收产物

> 目标：亲手开一轮评测（dispatch → 等 → 到 OBS 收），不断线。
> 时间：操作 10 分钟 + 等卡（看队列） ｜ 前置：读完 `quickstart` ｜
> 你将得到：一轮跑完的产物（OBS）+ 对"三机分工"的理解。
> 读法：`操作`是值班手册；`原理`讲为什么机器是这么分的。

## 操作：开一轮（四步）

1. 进 Actions，选 workflow：smoke 选 `*-smoke`（无参数或 few），全量选
 `RobotWin Full (chunked)`（填 tasks/episodes/shards/video/obs_prefix，见 03）。
2. 点 dispatch，去干别的。hw21 自动开机（~12 分钟内 ACTIVE），V100 开跑。
3. 前有队列就排队：GPU job 串行（`concurrency: gpu-ecs-pi0-smoke`），
 `gh run list --status in_progress` 看谁在跑。
4. 跑完到 OBS 收：`<obs_prefix>/<榜>-<smoke|full>/`（flat 打平）。关机自动
 （`if: always()`，跑崩也关，不留空转烧钱）。

## 操作：runner 掉了（修法背下来）

症状：开机后 runner 不上线（V100 离线超期被 GitHub 回收注册）。
修法：dispatch `repair-v100`（token 现开、用完删 secret；流程：安全组放行 →
跳板 SSH → `svc uninstall` → `config remove` → 新 token 重配 → 重装 service）。

## 原理：三机分工（铁律：下载只能发生在有外网处）

| 机器 | 网络 | 只干 |
|---|---|---|
| GitHub 免费机 | 外网 | 打镜像→SWR；小文件/一次性下载 |
| hw21 常驻机 | 几乎内网 | V100 开关机（hcloud API 内网可达） |
| V100（北京四） | 几乎内网 | 离线跑：SWR 内网拉镜像、mirror 拖权重、`UV_OFFLINE=1` |

V100 上禁止：`pip/uv` 装包、git clone、HF 下载、ghcr 拉取。缺东西一律回免费机
烘进镜像（见 `02-images.md`）。铁律两个例外（实测结论）：SWR 同步不走 url2hc
中转（中转镜像 7 天老化，常驻镜像要活数周，属"中转不适用"，skopeo 直拷）；
权重不同步 OBS（15GB 跨洋太慢，走 mirror+token 直下 V100）；OBS 只收小结果。

## 原理：超时与串行

* chunk 超时 10080（7 天；easy50 完整对照约 2~3 天；旧 24h 帽已退役）。
* 单卡串行是故意的：多 SAPIEN 上下文抢单卡会 hang（见分片对照），serve 独占卡 0、
 分片放卡 1。想快加卡，不加分片。

## 检查点

- [ ] dispatch 后 15 分钟 V100 到 ACTIVE？不到看 start-ecs 日志（hcloud 内网 API）。
- [ ] 结果没进 OBS？先看 workflow 日志尾（validation 红→地址错；upload `|| true`
  吞错→去 issue #8 的测试项对）。
- [ ] 跑完没关机？stop-ecs 是 `if: always()`，除非 hw21 runner 本身掉了。

## 下一步

镜像从哪来、钉哪个版 → `02-images.md`。

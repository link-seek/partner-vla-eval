---
title: 运维 02：开跑与收产物
parent: 评测教程
nav_order: 6
---

# 运维 02：派完就走，回来收菜

> 解决什么问题：评测是无人值守的——dispatch 之后机器自动开、跑完自动关、产物自动进 OBS。你派完就可以走，回来只做一件事：收菜。
> 和 01 的分工：日常派活走 CI（本篇）；手动开卡、换镜像这种底层操作见 [01-system-and-run.md](./01-system-and-run.md)。
> 时间：派活 2 分钟 + 收菜 5 分钟 ｜ 前置：读完 `quickstart`。

## 操作：派活（两分钟）

1. 进 Actions，选 workflow：smoke 选 `*-smoke`（无参数或 few），全量选
   `RobotWin Full (chunked)`（填 tasks/episodes/shards/video/obs_prefix，见 [partner/02-full-and-report.md](../partner/02-full-and-report.md)）。
2. 点 dispatch，走人。

剩下的它自己干：自动开机（GitHub 托管 runner 调华为云 API，~12 分钟到 ACTIVE）→ V100 开跑 → 跑完自动关机
（`if: always()`，跑崩也关，不留空转烧钱）。

排队也不用管：GPU job 串行（`concurrency: gpu-ecs-0002-smoke`），前一个没跑完后一个自己等。

## 操作：收菜

跑完到 OBS 收：smoke 在 `<obs_prefix>/robotwin-smoke/`，全量在
`<obs_prefix>/robotwin-full/results/robotwin-<chunk>-x<ep>/`（都保留 `episodes/` 结构）。

收的时候看三样：

- 产物齐不齐：aggregate + 逐 episode 的 json / sqlite / mp4。
- 分数对不对：先看 `errors`，再看 `mean_success`。
- 机器关了没：stop 日志有记录。

## 例外：只有三种情况需要人动手

设计目标是零盯守，所以正常路径上没有"看着"这一步。只有这三种情况会打断你：

1. **15 分钟没到 ACTIVE** → 看 start-ecs 日志（hcloud 内网 API）：配额、安全组、region。
2. **runner 不上线** → dispatch `repair-v100`（token 现开、用完删 secret；流程：安全组放行 → 跳板 SSH → `svc uninstall` → `config remove` → 新 token 重配 → 重装 service）。
3. **结果没进 OBS** → 看 workflow 日志尾部：validation 步骤红 = 地址错；上传报错被 `|| true` 吞掉 = 去 issue #8 的测试项对。

## 原理：为什么能开完不管

- **关机是兜底的**：stop-ecs 用 `if: always()`，成功失败都关。
- **串行是排队不是抢占**：同一时刻只跑一个 GPU job，两个 run 不会抢同一张卡。
- **产物直落 OBS**：结果不在 V100 磁盘上过夜，机器关了也不丢。
- **超时给足**：chunk 限 10080 分钟（7 天），easy50 完整对照 2~3 天够用。
- **下载都在外网侧完成**：SWR 用 skopeo 直拷、权重走 mirror 直下，V100 只管跑。

## 下一步

镜像从哪来、钉哪个版 → `03-images.md`。

链路里发现 harness 本体的 bug（不是配置问题）→ [参考：给上游提 issue/PR](../reference/contribute-upstream.md)。

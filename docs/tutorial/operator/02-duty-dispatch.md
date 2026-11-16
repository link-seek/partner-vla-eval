---
title: 运维 02：开跑、排队、收产物
parent: 评测教程
nav_order: 6
---

# 运维 02：开跑、排队、收产物

> 解决什么问题：你接手一轮评测，要从 dispatch 一路跟到 OBS 收产物，中途不能掉链子。本篇就是这条路的操作手册。
> 和 01 的分工：日常开跑都走 CI（本篇）；手动开卡、换镜像这种底层操作见 [01-system-and-run.md](./01-system-and-run.md)。
> 目标：亲手开一轮评测（dispatch → 等 → 到 OBS 收）。
> 时间：操作 10 分钟 + 等卡（看队列） ｜ 前置：读完 `quickstart`。
> 你将得到：一轮跑完的产物（OBS）+ 对"三机分工"的理解。
> 读法：`操作`是操作手册；`原理`讲为什么机器是这么分的。

## 操作：开一轮（四步）

1. 进 Actions，选 workflow：smoke 选 `*-smoke`（无参数或 few），全量选
 `RobotWin Full (chunked)`（填 tasks/episodes/shards/video/obs_prefix，见 [partner/02-full-and-report.md](../partner/02-full-and-report.md)）。
2. 点 dispatch，去干别的。hw21 自动开机（~12 分钟内 ACTIVE），V100 开跑。
3. 前有队列就排队：GPU job 串行（`concurrency: gpu-ecs-pi0-smoke`），
 `gh run list --status in_progress` 看谁在跑。
4. 跑完到 OBS 收：`<obs_prefix>/<榜>-<smoke|full>/`（flat 打平）。关机自动
 （`if: always()`，跑崩也关，不留空转烧钱）。

## 操作：runner 掉了（修法背下来）

症状：开机后 runner 不上线（V100 离线超期被 GitHub 回收注册）。
修法：dispatch `repair-v100`（token 现开、用完删 secret；流程：安全组放行 →
跳板 SSH → `svc uninstall` → `config remove` → 新 token 重配 → 重装 service）。

## 原理：三机分工

铁律：**下载只能发生在有外网的地方**。三机各自负责什么，见 [01-system-and-run.md](./01-system-and-run.md#系统长什么样)，本篇不重复。

操作中最需要多记两条实测例外：

* **SWR 同步不用 url2hc 中转**：中转镜像 7 天老化，常驻镜像要活数周，所以用 skopeo 直拷。
* **权重不走 OBS**：15GB 跨洋太慢，走 mirror+token 直下 V100；OBS 只收小结果。

## 原理：超时与串行

* chunk 超时 10080 分钟（7 天，够跑完 easy50 完整对照的 2~3 天）；早年的 24 小时上限已经不够用，退役了。
* 单卡串行是故意的：多个 SAPIEN 环境同时抢一张卡会 hang（试过，见 [01-system-and-run.md](./01-system-and-run.md#系统长什么样) 的卡分配）。想快加卡，不加分片。

## 检查点

- [ ] dispatch 后 15 分钟 V100 到 ACTIVE？不到看 start-ecs 日志（hcloud 内网 API）。
- [ ] 结果没进 OBS？先看 workflow 日志尾部：validation 步骤红 = 地址错了；上传步骤报的错被 `|| true` 吞掉 = 去 issue #8 的测试项对。
- [ ] 跑完没关机？stop-ecs 是 `if: always()`，除非 hw21 runner 本身掉了。

## 下一步

镜像从哪来、钉哪个版 → `03-images.md`。

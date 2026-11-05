---
title: Quickstart：跑通第一条双臂链路
parent: 评测教程
nav_order: 1
---

# Quickstart：跑通第一条双臂链路

> 目标：跑通 RobotWin smoke（grab_roller×1ep），亲眼看到双臂链路是绿的。
> 时间：操作 10 分钟 + 等卡 0.5~2 小时 ｜ 前置：无（不用懂镜像，不用装依赖）
> 你将得到：`smoke_exit=0` + OBS 落盘 + 一次 spec 对齐确认。

## 链路全景

```mermaid
flowchart LR
    S["模型 serve · cogact-serve 容器 · GPU<br/>vla-serve-cogact:0.8.0<br/>vla-eval serve"]
    C["考场 client · harness run 编排 · 跑完即焚（--rm）<br/>vla-eval-robotwin:0.8.0-ee-slim<br/>发观测收动作记分"]
    E["考场 env · SAPIEN 模拟器<br/>布景/执行/判分全在此"]
    S <-->|"WebSocket/msgpack<br/>ws://localhost:8000"| C
    C -->|"docker.sock 拉起"| E
```

三容器：模型 serve（权重变服务）←→ 考场 client（发观测收动作记分）→ 经 docker.sock 拉起考场 env（SAPIEN 模拟器，判分在此）。详见 [anatomy.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/tutorial/anatomy.md)。

## 操作

1. 发起一次评测运行：打开 `RobotWin Smoke (DB-CogACT)`，确认参数后运行（本轮无参数）。之后全自动：hw21 开机 → V100 跑
 `scripts/ci_robotwin.sh`（5 步）→ 跑完自动关机。单卡串行，前有队列就排队。

2. 等 5 步跑完。V100 日志里看到下面 6 行即正常：

```text
[2/5] bench + serve 镜像 (SWR 内网拉取)
[3/5] verify 镜像
[4/5] 预热 DB-CogACT 权重 (grab_roller 头, mirror, 带重试)
[4b/5] 启动 DB-CogACT serve (GPU0, 后台) ... serve UP
[5/5] 跑 RobotWin smoke (grab_roller 1ep, 用 robotwin 镜像当 client)
smoke_exit=0
```

3. 到 OBS 收产物：`<obs_prefix>/robotwin-smoke/`（默认
 `obs://so101-sim-pipeline/eval/robotwin-smoke/`，flat 打平无子目录；
 dispatch 自填了前缀就去自填的地址）。对着检查点打勾。

## 检查点

- [ ] `robotwin-smoke.log` 尾部 1/1（只验链路，不计分）。
- [ ] `cogact-serve.log`：serve 端完整日志。
- [ ] 录像 mp4：出 0 分时亲眼看，不要只看数字。
- [ ] `serve UP` 在探测内出现？3 次重试都起不来，先看 serve 尾日志
 （已自动存 `results/serve-debug-attempt*.log`），不要先怀疑 benchmark。
- [ ] 日志头 20 行无 `Spec mismatch`？有 → **停手**，先对
 [06-model-onboarding.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/tutorial/old/06-model-onboarding.md) 口径映射表，不要烧卡硬跑。
- [ ] 权重预热 `Xet 401`？预热传 token + `HF_HUB_DISABLE_XET=1`（脚本里已有）。
 修不好的完整 15 条表在 [08-troubleshooting.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/tutorial/old/08-troubleshooting.md)（将迁入 `reference/error-codes.md`）。

**出 0 分先查链路，不查模型**（grab_roller 是已驯服 task，全量 92%，0 分几乎不可能是能力问题）：
1. 日志头有 `Spec mismatch` → 口径（必现），对表改配置；
2. 无 `serve UP` → infra/权重，看 serve 尾日志；
3. 都绿还 0 → 重跑一次（seed 0 是校验种子，剩下的多是 infra 偶发）；
4. 还 0 → 按 15 条排障表走，这时才值得怀疑人生。

## 原理（你刚才干了什么）

* **你只点了一下，什么都没填**——两个 yaml 是预置好的，自己填是 01 的事。你之所以点一下就能跑，是因为模型和考场互相不知对方存在（上游论文 §II-A），中间是标准协议：适配器代码和两个 conda env 都 bake 在镜像里了，你不需要写。
* **你点的 dispatch 没有拉代码**——V100 平时关机（省卡钱），开机关机走 hw21 调华为云内网 API；V100 几乎没有外网，代码经 `vla-payload` 镜像从 SWR 内网取，不从代码仓拉取。**下载只能发生在有外网处**，这是全仓铁律。
* **你等的那几分钟，是在下 grab_roller 的专用权重包**（约 15GB，经 HF 镜像源进 V100 盘永久缓存；mirror 是下别人权重的加速通道，OBS 是存我们产物的仓库，两码事）。权重进不了镜像（传不动），serve 镜像只烘依赖；运行时 `UV_OFFLINE=1`，缺东西直接失败，不许现场装。
* **serve UP 等了 20 分钟是正常的**——7B 加载分钟级，120 轮×10 秒上限是算过的；3 次重试 cover 冷启动偶发 CUDA 初始化失败，重试完还起不来再看日志。
* **你刚跑的是全量的 1/50**——smoke 与全量同一套配置（`test_num=1` + `skip_expert_check=true`），只差集数。绿了说明口径权重 serve 落盘四个变量一次对齐，再跑 49 遍就行。
* **你看到的 0 分先别骂模型**——`fail` 才是没做出来，`error`（infra/坏种子抛异常）单列不怪模型。0/30 全 ERROR 但 exit 0（精度断崖的教训），先看 errors 列。
* **日志头的 warning 是在救你的卡**——episode 起点自动比对口径，`Spec mismatch` 不停手的话，EE 当关节喂能烧完 400 步拿 0 分还零异常。唯一的例外是 advisory 级 warning（X-VLA `ee_pose` 未声明但动作照通）。

## 下一步（三选一）

* 来评测模型（手里有训好的模型要交上来，才需细看）：去 [partner/01-serve-yaml.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/tutorial/partner/01-serve-yaml.md)，
 按 01→02→03 顺序读完（配准交付 → smoke → 全量拿分；不教训模型）。
* 开卡保链路：去 `operator/01-machines-ci.md`（待写，先看 [04-machines-network.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/tutorial/old/04-machines-network.md)）。
* 只看分数：RobotWin 四轮对照（校验种子，零 error 即有效；单榜 % 口径）。
 官方范式（论文 §4.5）本来就是**单 task 微调后测 Easy/Hard**，报的是 few-shot
 adaptation + robustness（Hard 落差）——我们的分头评测与官方范式一致，
 差的是：100→50 rollouts、只有 Easy（demo_clean）缺 Hard、头的训练数据未知。
 先对 Easy，再补 Hard。

| task | 我们 | 官称 |
|---|---|---|
| grab_roller | 92%（46/50） | 89% |
| adjust_bottle | 100%（35/35 有效，15 坏种已剔） | 99% |
| place_empty_cup | 16%（8/50） | 28% |
| place_phone_stand | 16%（8/50） | 18% |

差 10pp 以内判同档（n=50 噪声带约 ±6pp）；跨榜不比大小（多榜指标待接入后展开）。
完整排名规则与披露清单在 [03-full-and-report.md](https://github.com/link-seek/partner-vla-eval/blob/main/docs/tutorial/partner/03-full-and-report.md)，栈差异对照在 `explanation/`。

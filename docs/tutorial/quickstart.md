# Quickstart：跑通第一条双臂链路

> 目标：跑通 RobotWin smoke（grab_roller×1ep），亲眼看到双臂链路是绿的。
> 时间：操作 10 分钟 + 等卡 0.5~2 小时 ｜ 前置：无（不用懂镜像，不用装依赖）
> 你将得到：`smoke_exit=0` + `results/` 落盘 + 一次 spec 对齐确认。

## 为什么从 RobotWin 开始

我们的主业是双臂伙伴模型，RobotWin 是唯一双臂基线考场。全量也是按 task 逐个跑
（grab_roller → adjust_bottle → …），smoke 跑的正是全量的第一个 task、同样的 serve
口径：smoke 绿了，全量只是把 `test_num` 从 1 调到 50。LIBERO 只在"分不清是链路问题
还是模型问题"时拿来做便宜对照，见 `partner/02-smoke.md`。

```text
serve（DB-CogACT 双臂，GPU） ←WebSocket/msgpack→ benchmark（RobotWin grab_roller，Docker）
  serve-robotwin-cogact.yaml（chunk 16，三相机）   run-robotwin-smoke.yaml（demo_clean，seed 0）
```

## 步骤（只做一件事：在 GitHub 点 dispatch）

V100 是离线卡，Runner 零 checkout（代码经 `vla-payload` 镜像从 SWR 取，不走 GitHub）。
你不需要 SSH、不需要装包。

1. 进本仓 Actions → `RobotWin Smoke (DB-CogACT)` → `Run workflow`。无参数，直接点绿钮。
2. 等：hw21 自动开机 → V100 跑 `scripts/ci_robotwin.sh`（5 步）→ 跑完自动关机。单卡串行，前有队列就排队。

等卡时可读一步：`configs/serve-robotwin-cogact.yaml`（16 行）。知道三件事即可：
`chunk_size: 16` + 三相机 `head/left/right` + 权重按 task 分头（smoke 用 grab_roller 头）。
注意 `from_pretrained` 不认 `repo/subdir` 三段式，CI 会 snapshot 后生成
本地路径版 `serve-robotwin-local.yaml` 再起 serve——照抄这个做法，不要手拼路径。

## 期望输出（对照打勾）

跑完在 workflow 的 Artifacts（`robotwin-smoke`，即 `results/`）里看到：

```text
[2/5] bench + serve 镜像 (SWR 内网拉取)
[3/5] verify 镜像
[4/5] 预热 DB-CogACT 权重 (grab_roller 头, mirror, 带重试)
[4b/5] 启动 DB-CogACT serve (GPU0, 后台) ... serve UP
[5/5] 跑 RobotWin smoke (grab_roller 1ep, 用 robotwin 镜像当 client)
smoke_exit=0
```

* `results/robotwin-smoke.log`：尾部 1/1（只验链路，不计分；录像常开，`RW_VIDEO=1`）。
* `results/cogact-serve.log`：serve 端完整日志。
* 出 0 分时亲眼看录像，不要只看数字。

## 检查点（出错先看这里，不过再烧卡）

- [ ] `serve UP` 在 120 轮探测内出现？脚本自带 3 次重试，3 次都起不来先看 serve 尾日志
  （已自动存 `results/serve-debug-attempt*.log`），不要先怀疑 benchmark。
- [ ] 日志头 20 行无 `Spec mismatch`？有 → **停手**。口径错配必 0 分
  （14 关节 vs 16 EE、相机名、chunk 任一错都一样）。对照 `06-model-onboarding.md`
  口径映射表（将迁入 `reference/config-fields.md`），不要烧卡硬跑。
- [ ] `smoke_exit=0` 且 1/1？`error ≠ fail`：`fail` 是模型没做出来；`error` 是
  infra/坏种子抛异常，单列不怪模型。

## 常见卡点（只记一个，其余进 reference）

> 权重预热 `Xet 401`？权重走 Xet，mirror 直连要 token：预热传 token +
> `HF_HUB_DISABLE_XET=1`（脚本里已有）。修不好的完整 15 条表在
> `08-troubleshooting.md`（将迁入 `reference/error-codes.md`）。

## 下一步

* 伙伴交模型：去 `partner/01-serve-yaml.md` —— 交权重地址 + 一个 serve yaml
 （照 `partner-onboarding.md` 表单填，不知道的空着；按 task 分头的逐个列出）。
* 运维保链路：去 `operator/01-machines-ci.md` —— 开关机、串行队列、runner 掉了怎么修。
* 想先看分数长什么样：RobotWin 四轮对照（校验种子，零 error 即有效；单榜 % 口径）：

| task | 我们 | 官称 |
|---|---|---|
| grab_roller | 92%（46/50） | 89% |
| adjust_bottle | 100%（35/35 有效，15 坏种已剔） | 99% |
| place_empty_cup | 16%（8/50） | 28% |
| place_phone_stand | 16%（8/50） | 18% |

差 10pp 以内判同档（n=50 噪声带约 ±6pp）；CALVIN 另看平均链长，跨榜不比大小。
完整排名规则与披露清单在 `partner/03-full-and-report.md`，栈差异 A-D 在 `explanation/`。

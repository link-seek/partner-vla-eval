# Quickstart：30 分钟跑通第一条链路

> 目标：跑通 LIBERO smoke（1 task×1ep），亲眼看到链路是绿的。
> 时间：操作 10 分钟 + 等卡 0.5~2 小时 ｜ 前置：无（不用懂镜像，不用装依赖）
> 你将得到：`smoke_exit=0` + `results/` 落盘 + 一次 spec 对齐确认。

## 为什么从 LIBERO 开始

LIBERO 是最便宜的考场：单臂短程、CPU 环境镜像最小、失败跑不满 400 步。
链路分两段，责任分清：serve 不通是模型侧问题，benchmark 不通是环境侧问题。
先证明链路本身健康，后面谈分数才有意义。

```text
serve（π0.5，GPU） ←WebSocket/msgpack→ benchmark（LIBERO spatial，Docker）
  serve-pi05-libero.yaml              run-libero-smoke.yaml（suite spatial，seed 7）
```

## 步骤（只做一件事：在 GitHub 点 dispatch）

V100 是离线卡， Runner 零 checkout（代码经 `vla-payload` 镜像从 SWR 取，不走 GitHub）。
你不需要 SSH、不需要装包。

1. 进本仓 Actions → `LIBERO Smoke (pi05)` → `Run workflow`。
2. 参数保持默认（共 4 个，含义如下），点绿钮：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `serve_yaml` | `serve-pi05-libero.yaml` | π0.5 LIBERO 口径：`chunk 10`，`agentview/wrist` 双相机 |
| `run_yaml` | `run-libero-smoke.yaml` | spatial 1 task×1ep，seed 7 |
| `serve_image` | `vla-serve-pi05:0.8.0` | 依赖全烘+预热，V100 离线跑 |
| `bench_image` | `vla-eval-libero:0.8.0` | 以 workflow 输入为准（yaml 内旧 tag 忽略） |

3. 等：hw21 自动开机 → V100 跑 `scripts/ci_libero.sh`（4 步）→ 跑完自动关机。单卡串行，前有队列就排队。

等卡时可读一步：`configs/serve-pi05-libero.yaml`（15 行）。知道 `checkpoint: lerobot/pi05_libero_finetuned` + `chunk_size: 10` 即可，其余先不用懂。

## 期望输出（对照打勾）

跑完在 workflow 的 Artifacts（`libero-smoke`，即 `results/`）里看到：

```text
[1/4] 拉镜像（SWR 内网）
[2/4] 预热 pi05 权重（缓存命中则秒过）
[3/4] 启动 pi05 serve ... serve UP
[4/4] 跑 LIBERO smoke (spatial 1 task x 1ep)
smoke_exit=0
```

* `results/libero-smoke.log`：尾部 `1/1 SUCCESS`（只验链路，不计分）。
* `results/pi05-serve.log`：serve 端完整日志。
* 落盘 aggregate JSON + 录像：出 0 分时亲眼看录像，不要只看数字。

## 检查点（ emulation 出错先看这里，不过再烧卡）

- [ ] `serve UP` 在 120 轮探测内出现？没出现 → serve 镜像/权重问题，看 serve log 尾 15 行（脚本已打印），不要先怀疑 benchmark。
- [ ] 日志头 20 行无 `Spec mismatch`？有 → **停手**。口径错配必 0 分（关节/末端、相机名、chunk 任一错都一样）。对照 `06-model-onboarding.md` 口径映射表（将迁入 `reference/config-fields.md`），不要烧卡硬跑。
- [ ] `smoke_exit=0` 且 `1/1`？`error ≠ fail`：`fail` 是模型没做出来；`error` 是 infra/坏种子抛异常，单列不怪模型。

## 常见卡点（只记一个，其余进 reference）

> `docker -v` 把宿主目录建成 root 导致 `.cache Permission denied`？
> 脚本里已预建目录+改属主（`workspace_fix`），重跑即好。修不好的完整 15 条表在 `08-troubleshooting.md`（将迁入 `reference/error-codes.md`）。

## 下一步

* 伙伴交模型：去 `partner/01-serve-yaml.md` —— 交权重地址 + 一个 serve yaml（照 `partner-onboarding.md` 表单填，不知道的空着）。
* 运维保链路：去 `operator/01-machines-ci.md` —— 开关机、串行队列、runner 掉了怎么修。
* 想先看分数长什么样：RobotWin 四轮对照（校验种子，零 error 即有效）：

| task | 我们 | 官称 |
|---|---|---|
| grab_roller | 92%（46/50） | 89% |
| adjust_bottle | 100%（35/35 有效，15 坏种已剔） | 99% |
| place_empty_cup | 16%（8/50） | 28% |
| place_phone_stand | 16%（8/50） | 18% |

差 10pp 以内判同档（n=50 噪声带约 ±6pp），跨榜不比大小。完整排名规则与披露清单在 `partner/03-full-and-report.md`，栈差异 A-D 在 `explanation/`。

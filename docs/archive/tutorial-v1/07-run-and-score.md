---
nav_exclude: true
---

# 07 开跑与判分

> 版本：v1.2（2026-11-03，栈差异对照 A-D 收官；v1.0 见 2026-10-14）。
> 口径源：`docs/proposal-stack-effects.md` 对照表（V100 实测，10-14~16）+
> `docs/blog-precision-cliff.md`（B 精度断崖）+ `docs/reports/`。

## smoke（必经）

1 task×1ep（CALVIN 用 5 sequences），验证：镜像/权重/serve-up/口径/落盘。
先 smoke 后全量，省卡钱。录像常开（1ep 体积小，出 0 分时亲眼看）。

## 全量（分块战役）

- RobotWin：1 task×50ep/轮（CogACT 一头一 task），`test_num` 官方口径。
- 分片：默认 8（workflow 默认；EE 默认 4，见脚本注释——fast_init=false 全量 planner + SAPIEN 抢显存，8 分片 OOM）。
  实测：2 稳、4 慢、8 在单卡多 SAPIEN 上下文会 hang（C，watchdog 全杀）。生产切法：serve 独占卡0、分片放卡1。
- 超时：chunk 设 10080（7 天；easy50 完整对照约 2~3 天。旧 1440/24h 帽已退役，见 10-31 commit）。
- 耗时参考：单 ep 2~10 分钟，一轮（1 task×50ep，2 分片）3~7 小时；easy50 按 task 数线性累加、串行。

## 栈差异对照表（有结论才进榜，E 待定不进）

| # | 变量 | 水平 | 结果 | 结论 |
|---|---|---|---|---|
| A | benchmark 镜像 | 0.7.0 vs 0.8.0（同种子 grab_roller×50） | 43/50=86% vs 46/50=92% | 差 6pp，2σ 内，不搬分 |
| A2 | 资产内置 vs 外置挂载 | 同种子×50 | 46/50 vs 45/50 | 差 1ep，等价（Phase 2 关闭） |
| A3 | 烘焙 vs 原生 | stock vs slim×20 | 18/20 vs 18/20 | 差 0，自证清白 |
| B | 模型精度 | X-VLA fp32 vs fp16（LIBERO spatial/object/goal×10 同种子，6 轮） | 29/30 vs 0/30 | fp16 首推理即崩（`float vs Half bias`），跨 task 一致；详见 08 |
| B2 | 精度 | CogACT fp32 vs fp16（V100） | fp32 首个 forward 即 OOM（31GB） | 单侧不可行本身即证据 |
| C | 分片 | 2 / 4 / 8 | 2 稳、4 慢、8 hang | 只动速度/稳定性，不动分 |
| D | 种子 | 盲种子 vs 校验种子 | 35/35 有效+15 坏种 vs 零 error；同集重跑 41 vs 46 | 种子集动 error 率；同集轮间差 ≈1.7σ（噪声） |

E（V100 fp16 vs 官方 H100 bf16，place_empty_cup 16~20% vs 28%）待定档：只写进披露，不硬判，见 99。
披露清单（跑分必报，缺一个别比）：GPU / dtype / benchmark 镜像 tag（含 slim/补丁说明）/ serve 镜像 /
种子（bundled 还是盲）/ 分片 / 资产挂载。方法论副产品：阴性对照（/tmp 盖资产秒崩）验证挂载生效；
挂载=改镜像，版本化+差值单列。

## 最终报告模板（缺一项不算完整报告）

```json
{
  "model": "<模型名+权重地址>",
  "task": "<考场-任务>",
  "mean_success": 0.0,
  "n": 50,
  "errors": 0,
  "versions": {"harness": "v0.8.0", "benchmark_image": "<镜像:tag>"},
  "machine": "<GPU型号>",
  "seeds": "bundled/盲种子说明",
  "date": "YYYY-MM-DD",
  "artifacts": "<OBS/artifact 链接>"
}
```

## 伙伴之间怎么比（排名规则）

1. **同考场同种子同版本**：镜像 tag、test_num/种子集、harness 版本全 locked 才可比。
   我们的链路天然保证（配置钉版，见 05）。
2. **分榜排名，不合总分**：每个 task 一个榜；跨 task 看画像（各 task 分数并列），
   不造加权总分（权重一拍脑袋就失去公信）。
3. **差 10pp 以内判同档**：n=50 时噪声带约 ±6pp（p=0.2），2σ≈11pp。
   10pp 以内并列；10~15pp 标“待定”（加样本再判）；15pp 以上分档（S/A/B）。
   例：place_empty_cup 我们 16% vs 官称 28%（差 12pp）→ 待定，不硬判高下。
4. **error 口径一致**：坏种 error 剔除后再比有效成功率；剔除数也要公示。
5. **榜单四要素**：分数 + n + 版本日期 + **机器**（GPU型号+镜像tag），缺一个不上榜。
   同卡才可比：V100 的分数和 H100 的分数不上同一个榜；换卡重打基线，榜单按机器分组。

## 分数怎么读（92% 到底在说什么）

- 各榜分数各榜自己定（上游论文 Table I/II，arXiv:2603.13966）：LIBERO / RobotWin 是单 ep
  二值分（成或败，`mean_success` = 成功 ep 数 / 总 ep 数）；CALVIN 是一个 ep = 5 连子任务，
  主指标是平均链长 `completed_subtasks`（0~5，如论文 Table II 的 4.02/4.30），另有 `success`
 （5/5 全对才算）。看分先确认是哪个指标，不要把链长当成功率读。
  步数上限各榜也不同（LIBERO 按 suite 220~520，CALVIN 360×5，RobotWin 按 task 到 1700）。
- 和官称差多少算正常：±5pp 以内算对上（噪声+种子集差异）；
  差 10pp 以上先查口径（08 第 1 条），不要先怀疑模型。
- `error` ≠ `fail`：`fail` 是模型没做出来；`error` 是 infra/坏种子抛异常，
  不怪模型，单列。看分先看 errors，再看 mean。B 的反直觉点：0/30 全是 ERROR 不是 FAIL，
  vla-eval exit code 照样 0，看分不看日志会误判（见 `docs/blog-precision-cliff.md`）。
- 跨榜不比大小：LIBERO 99% 和 RobotWin 16% 没有可比性，各榜难度和判分标尺不同，
  只并列展示（我们在总表里就是这么列的）。

## 判分记分

- harness 不发明分数：各榜原生规则 + `mean_success` 透传，跨榜只并列不加权。
- error 分类记法：模型失败（判 0 分）/ 坏种子 `UnStableError`（单列，不怪模型）/ infra 异常（重跑）。
- 归档：aggregate JSON + SQLite 进 artifact 与 OBS（`eval/<榜>-*/`），Discussion 记结论。

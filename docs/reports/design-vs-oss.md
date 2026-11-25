# 设计对比：本仓 vs 开源评测框架

> 日期：2026-11-25 ｜ 目的：拿同类框架的成熟做法校准我们的设计，挑出真正值得改的点
> 对照对象：[lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)（评测框架标杆）、
> [allenai/vla-evaluation-harness](https://github.com/allenai/vla-evaluation-harness)（我们在用的上游）、
> RoboTwin 官方协议（已在 `eval-engineering-review.md` 对过）
> 方法：读代码/文档确认能力，不凭印象

---

## 一、结论先行

**我们缺的不是功能，是"失败后的退路"。**

三个框架里最成熟的一条做法是**增量与续跑**（lm-eval 的逐样本缓存、vla-eval 的 sqlite + 增量 export），
而我们每轮开跑前会 `results_fresh` 把 `results/` 连 sqlite 一起清空 —— 于是：

- 20 小时的评测如果在第 19 小时崩了，**前面 19 小时的数据全丢**，只能重跑；
- 已经完成 10 集的 task，在汇总时也拿不到（必须等整 task 跑完）。

这一条的成本最低、收益最大，应排第一。

---

## 二、能力对照（都有代码证据）

| 能力 | lm-evaluation-harness | 上游 vla-eval | 本仓现状 |
|---|---|---|---|
| **逐样本缓存 / 续跑** | ✅ `lm_eval/caching/cache.py`：按请求哈希落盘，重跑直接命中 | ✅ `RecordingStore.claim/finish/completed_results` 队列语义；`vla-eval export` 明确支持"Rerun to include subsequently recorded episodes" | ❌ `scripts/ci/lib/common.sh` 的 `results_fresh` 每轮清空 `results/`（含 sqlite） |
| **中途导出** | ✅ `--output_path` 随时可读 | ✅ `vla-eval export <sqlite>` 增量 | ❌ 只在整 task 结束后由 runner 调一次 |
| **统计口径** | ✅ `bootstrap_stderr` / `mean_stderr`（重采样） | ❌ 只有均值 | 🟡 Wilson CI，但只在榜单脚本层算，报告里没有 |
| **结果结构** | ✅ `results.json`（含 `config`、`versions`、`n-samples`） | 🟡 aggregate + sqlite | ✅ 我们更强：JSON Schema + 与 docs/data 对账 |
| **任务注册** | ✅ YAML task 注册表 | ✅ benchmark 类 | 🟡 硬编码在 shell + registry 两处 |
| **分组聚合** | ✅ `groups` 带权重 | ❌ | ❌ 无（我们明确"不给跨模型总分"，反而合理） |
| **榜单数据** | ✅ 外部榜单另建 | ✅ `leaderboard/data` + schema + `validate.py` | ✅ 已对齐（schema + 对账 + CI） |
| **配置校验** | ✅ `lm-eval validate` | ⚠️ 无 | ✅ `check_versions/registry/paths/reports/coverage` 五道门 |
| **回归测试（分数是否漂）** | ✅ `tests/` 44 项 | ✅ 大量测试 | ❌ 门禁只查结构，不查"同一配置重跑分数是否一致" |

> 一句话：**结构与校验我们已追平甚至更严；增量/续跑与统计口径是明显短板。**

---

## 三、值得改的 7 条（按投入产出排）

### 1. 别再把 sqlite 清掉，并支持"部分导出"（最高优先）

**现状**：`common.sh:27` `rm -rf results/*` + `results_root_wipe` 硬删。跑挂即全丢。

**改法**：
- 新增 `RW_RESUME=1`：跳过 `results_fresh`，保留 `results/recording-<eval_id>.sqlite`
- 跑完（或崩后）用 `vla-eval export <sqlite> -o <out>` 增量导出，已有集数照常出表
- 报告里标明 `n=<已完成>/<目标>`，不达 50 就写"部分结果"

**收益**：一次 20h 的 run 不再"全有或全无"。**这条能直接救今天这轮如果崩了的情况。**

**成本**：改 shell 约 20 行 + 一条 runbook。

---

### 2. 中途检查点：每完成一个 task 就 export 一次

**现状**：matrix 脚本在 `cp -r results/robotwin-*` 后才收集，sqlite 里的中间结果没人看。

**改法**：`ci_model_matrix.sh` 在每个 task 结束、以及每 N 分钟（可选）调 `vla-eval export`，
把 partial aggregate 落到 `matrix/<model>/<task>/partial/`。

**收益**：即使后续 task 全挂，前面 task 的数已经在手。

---

### 3. 统计口径补 bootstrap stderr

**现状**：我们有 Wilson CI（榜单脚本里算），但报告本身不带误差。

**改法**：报告生成时对每格算 bootstrap stderr（n=50 时与 Wilson 接近，但更通用，
且能直接扩展到"步数/耗时"等非二值指标），写进 `stderr` 字段；榜单并排展示。

**收益**：跨模型比较时有统一误差口径，不被"单点估计"带节奏。

**成本**：一个纯函数 + 单测，30 分钟。

---

### 4. 任务注册数据化（消灭两处硬编码）

**现状**：task 列表出现在 `ci_robotwin_full.sh`（默认值）、`collect_matrix.sh`（写死 5 个）、
`model-matrix.yml`（默认值）三处。加 task 要改三处，容易漏。

**改法**：`configs/benchmarks/robotwin.yaml` 定义 task 清单与难度枚举，脚本从它读。

**收益**：与 lm-eval 的 task registry 同构；换考场（LIBERO/CALVIN）时不用改 shell。

---

### 5. 结果 schema 版本化

**现状**：报告有 `report_version: "v1 (docs/tutorial/leaderboard.md)"` 但只是字符串，没人校验。

**改法**：加 `schema_version: 2`，`check_reports.py` 按版本分支校验；旧报告不强制迁移。

**收益**：以后改字段不会让历史报告变成"格式不明"。

---

### 6. 回归测试：同一配置重跑，分数必须落在噪声带内

**现状**：`lint` 只查结构；`explanation/01` 那张栈差异表靠人工记录。

**改法**：定时（每周）跑 1 task × 50ep 的基准配置，比对历史值，
超出 ±7pp 就开 issue 提醒"尺子可能漂了"。

**收益**：这是"可信"的最终保障——lm-eval 用 44 项测试守，我们目前只有结构门。

**成本**：一个 cron workflow + 一次 1 task 的成本（约 ¥60/周）。

---

### 7. 分组聚合规则显式化（暂不做，先记录）

lm-eval 有 `groups` 加权；我们明确"不给跨模型总分"。**保持现状是对的**——
但应该把"为什么不做总分"从文档散文升级成 registry 里的一个字段说明（已有 `exam.ranking_rule`），
避免以后有人误加。

---

## 四、我们做得比开源更好的三处（别退回去）

1. **榜单数据与报告对账**：lm-eval 的榜单是外部项目，没有"报告↔榜单"一致性校验；我们有。
2. **训练口径隔离**（`weight_type: shared|finetuned` + 门禁）：上游 leaderboard 有字段但无强制；我们对混排直接报错。
3. **覆盖矩阵前置**（`check_coverage.py` + dispatch 前拒跑）：三个框架都没有这个概念，是我们踩了 CogACT 只发 4 个头的坑之后补的。

---

## 五、建议的落地顺序

| 顺序 | 项 | 为什么这个顺序 |
|---|---|---|
| 1 | 增量/续跑（第 1、2 条） | 直接降低每次 20h 跑的"全损"风险，且能救正在跑的这一轮 |
| 2 | bootstrap stderr（第 3 条） | 报告质量，一次做完长期受益 |
| 3 | 任务注册数据化（第 4 条） | 为 5b（R01）加 task 做准备 |
| 4 | 回归测试（第 6 条） | 等 5b 定型后再建，否则基准会变 |
| 5 | schema 版本化（第 5 条） | 与第 3 条一起做 |

**不做**：分组加权总分（与我们的定位冲突）。

---

## 六、需要讨论的三个问题

1. **续跑保留多久**：sqlite 会占盘（当前一个 task 的 recording 约几 MB）。保留最近 N 轮还是全留？
2. **partial 结果能不能进榜**：n<50 的格子是标"部分"进榜，还是只进附录？我倾向只进附录，避免被当正式数。
3. **回归测试频率**：每周一次 1 task（¥60）够不够，还是要覆盖 2 个 task 交叉验证？

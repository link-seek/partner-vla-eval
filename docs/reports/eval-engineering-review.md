# 评测工程化检视：对照开源社区，我们该改什么

> 日期：2026-11-24 ｜ 范围：本仓（partner-vla-eval）全部 147 个文件
> 方法：逐项读本仓实现 → 对照上游 [allenai/vla-evaluation-harness](https://github.com/allenai/vla-evaluation-harness) 与 RoboTwin 官方协议 → 给出可验收的改法
> 结论先行：**我们的"跑得起来"是工程级的，"可被采信"还停在文档级**——社区把可信度做成了 CI 门禁，我们还是靠人盯。

---

## 一、对照总表

| 维度 | 开源社区（证据） | 本仓现状（证据） | 差距性质 |
|---|---|---|---|
| 自动化测试 | 上游 `tests/` **44 个** `test_*.py` + `leaderboard/tests/` 3 个；CI 跑 `uv run pytest` | `find -name 'test_*.py'` → **0** | 无回归防线 |
| 静态检查 | `ty check`（类型）+ `ruff check` + `ruff format --check` | `lint.yml` 只有 `bash -n` + `py_compile` + YAML 解析 | 无类型/风格门 |
| 榜单数据 | `leaderboard/data/leaderboard.json` + **5 个 JSON Schema**（leaderboard/benchmarks/candidates/extraction/coverage），PR 触发 `validate.py` | `docs/tutorial/leaderboard.md` —— **Markdown 散文表格** | 数字不可机器校验 |
| 训练口径编码 | schema 字段 `weight_type: shared \| finetuned`；`overall_score` 仅"标准协议全过"才填，否则留 null | 无字段；靠备注里写"不自己重训" | **5b 轴无法结构化表达** |
| 官方榜 vs 自测分离 | `official_leaderboard` + `external_only`：结果只在官方榜的 benchmark，本地必须 **0 行** | 无此概念，历史数与本次实测靠脚注区分 | 易混引 |
| 聚合规则 | `aggregation` 字段按 benchmark 声明（canonical） | 写在文档散文里 | 不可校验 |
| 分数范围 | `metric.range` + `validate_score_ranges()` | 无 | 手误无从发现 |
| 种子 provenance | `_extract_seed()` 把 seed 提升到 task 顶层，"promote seed to top level for reproducibility" | run yaml 里有 `seed: 0`，但没有校验/展示链 | 弱 |
| 权重版本 | —（上游按 benchmark 登记） | `"ckpt": "Dexmal/robotwin-db-cogact/<task>"` —— **只有 repo 名，无 revision/commit** | 复现必翻车 |
| 镜像版本 | — | tag 无 digest；`docs/reproducibility.md:33` 自己把 digest 列为**未完成项** | 同上 |
| 产物自证 | — | `aggregate.json` 里 `harness_version: "0.0.0"`（本轮实测），但我们的报告写 `"harness": "0.8.0"` | **产物流氓** |
| 上传可靠性 | — | `obsutil cp ... \|\| true` | 静默丢产物 |

> 一句话：上游把"这个分数凭什么信"做成了**可执行的检查**；我们把它写成了**可阅读的说明**。

---

## 二、皮肤之下的真实事故（本次会话亲历，可作为立项依据）

| 事故 | 现在靠什么拦住 | 应该靠什么 |
|---|---|---|
| CogACT 只发 4 个头，我们按 5 task 排期，跑到第 3 个才发现 | 事后查 HF 文件清单 | registry 必填 `covered_tasks` + schema 校验 + 准入检查 |
| `place_phone_stand` 两轮 16% vs 12%，报告里两个数并存 | 人工核对发现 | 每格带 run id + 重复轮方差，机器判"同档/跨档" |
| 报告写 `harness 0.8.0`，aggregate 实际 `0.0.0` | 无人发现 | 报告生成时从 aggregate 取，禁止手写 |
| deck 里 `97.0%` 与榜单 `93.2%` 短暂不一致 | 人工 diff | 数字一致性测试：docs/pptx 里的数必须能在 reports JSON 找到 |
| `r01-prep` 两次失败（`/root` 无权限、子目录 root 属主） | 看日志猜 | 预检 fail-fast + 权限自愈（已修，见 `r01-prep.yml`） |
| OBS 上传 `\|\| true` | 这次恰好成功（403/0） | 上传后回读校验，失败即红 |

**这些全部是"文档能说、机器不能验"的典型**——正好是上游用 schema + pytest 堵住的那一类。

---

## 三、优化设计（按优先级，每条给验收）

### P0-1　给数字加一道机器门：榜单数据结构化

**社区做法**：`leaderboard/data/leaderboard.json` 受 `leaderboard.schema.json` 约束；PR 改 `leaderboard/data/**.json` 即触发 `.github/workflows/leaderboard-validate.yml` 跑 `validate.py`（jsonschema + 分数范围 + 聚合规则 + 引用覆盖）。

**我们的改法**：
- 新增 `leaderboard/leaderboard.json`，一行一个 `(model × task)`：
  ```json
  {"model":"x-vla-robotwin2","task":"handover_block","bench":"robotwin",
   "protocol":"easy","weight_type":"shared","n":50,"success":39,"errors":0,
   "run":"45266034430","date":"2026-11-24",
   "bench_image":"...:0.8.0-ee-slim@sha256:...","serve_image":"...:0.8.0-ee16@sha256:...",
   "ckpt_repo":"2toINF/X-VLA-RoboTwin2","ckpt_revision":"<40-hex>"}
  ```
- `leaderboard/leaderboard.schema.json`：`required` 含 `protocol / weight_type / n / success / run / ckpt_revision`。
- `leaderboard/scripts/check_leaderboard.py`：schema 校验 + `success<=n` + `n` 与 `protocol` 白名单一致 + 同 `(model,task,protocol)` 不得重复。
- `lint.yml` 加一步跑它。

**验收**：把 `success` 改成 `60`（n=50）→ lint 红；删 `ckpt_revision` → lint 红。
**产出**：`leaderboard.md` 由脚本从这个 JSON **生成**，不再手写（彻底消除 97.0/93.2 那类漂移）。

---

### P0-2　把"训练口径"变成字段，而不是备注

**社区做法**：`weight_type: "shared" | "finetuned"`——shared = 全 benchmark 同一个 ckpt；finetuned = 在本 benchmark 数据上训过。`overall_score` **只有走标准协议才允许非 null**，否则只能进 `task_scores.reported_avg` 不参与排名。

**我们的改法**：这正是 5b 需要的骨架。
- `weight_type: shared` → X-VLA / DB-CogACT 现况
- `weight_type: finetuned` → R01 的 ACT/DP（A/B 两口径）
- 加 `regime` 字段：`clean50` / `clean50+rand500`
- **排名只在同 `(weight_type, protocol)` 内允许**，脚本强制；跨口径只并列。

**验收**：混排 shared 与 finetuned 进同一排名 → lint 红。

---

### P0-3　版本钉死：ckpt revision + 镜像 digest

**现状证据**：`configs/registry/model-registry.json:39` 只有 `"ckpt": "2toINF/X-VLA-RoboTwin2"`；`docs/reproducibility.md:33` 把 digest 列为未完成；而 `leaderboard.md:30` 的披露规则要求"checkpoint 精确版本"——**自己违反自己**。

**改法**：
- registry 增加 `ckpt_revision`（40-hex）与 `serve_image_digest`，`check_versions.py` 风格加校验：有 `status=verified` 就必须有 revision。
- 预热脚本加 `--revision`（现在 `hf-download download ... "${INC[@]}"` 无 revision，永远拉 main）。
- 报告生成时把 revision/digest 写进 JSON。

**验收**：`status=verified` 但缺 `ckpt_revision` → lint 红；同一 model 两次跑的报告 revision 必须相同。

---

### P0-4　产物自证：harness 版本不许手写

**现状证据**：本轮 aggregate `harness_version: "0.0.0"`，而 `docs/reports/xvla_robotwin-*-x50.json` 写 `"harness": "0.8.0"`。

**改法**：
- 报告生成脚本从 aggregate 读 `harness_version`，读不到就写 `null` + 标 `unknown`，禁止硬编码。
- 镜像构建时把版本注入 `vla_eval.__version__`（或 aggregate 增加 `image_digest`）。

**验收**：手写版本号 → 测试比对 aggregate 不一致即红。

---

### P1-1　重复轮与方差：n=50 的单点不可当结论

**社区做法**：RoboTwin 论文 §4.5 —— 50 demos 训练、**100 rollouts**、Easy/Hard 双条件；我们跑 50。上游把 seed 提到顶层便于整轮复跑。

**改法**：
- 每个 `(model,task)` 至少 2 轮（不同 seed 集或同集重跑），报告给 `mean ± 轮间极差`。
- 判定规则机器化：`|Δ| < 7pp` → 同档（这条现在只写在文档里）。

**验收**：只跑 1 轮的条目在 JSON 里 `replicate_count: 1`，生成榜单时自动加"单轮，勿作结论"标记。

---

### P1-2　覆盖矩阵前置，而不是事后发现

**现状**：CogACT 3/5 是跑到第 3 个 task 才发现的（`click_bell` 预热失败 → 查 HF 才发现无此头）。

**改法**：准入检查脚本在 dispatch 前跑：按 registry 的 `covered_tasks` 与考场 task 集求交，差集在 workflow 里直接打印并**拒绝把缺格写进排名**。

**验收**：dispatch 一个 5 task 但只有 3 头的模型 → 日志出现 `COVERAGE 3/5, missing=click_bell,handover_block`，且 JSON 里那两格是 `null` 而非 0。

---

### P2-1　队列：一次只允许 1 个 pending 是平台限制，不该靠人

**现状**：`concurrency: gpu-ecs-0002-smoke` 的 pending 只有一位，第三个 dispatch 会顶掉第二个（本次会话已踩两次）。

**改法**：训练轴与评测轴拆两个 concurrency group；或用一个 `r01.yml` 把 `prep→train→eval` 串成 job 依赖链，一次 dispatch 跑完（社区 CI 的常见做法：job needs 而非外部排队）。

---

### P2-2　上传与关机的兜底

- `obsutil cp ... || true` → 改成上传后 `obsutil stat` 回读校验，失败 exit 1。
- run 被 cancelled 时 `stop-ecs` 不执行 → 加 cron `idle-guard`（已有设计，未实现）。

---

## 四、分阶段落地（与 5b 对齐）

| 阶段 | 内容 | 为什么先做 |
|---|---|---|
| W1 | P0-1 schema + `check_leaderboard.py` + lint 接入；`leaderboard.md` 改为生成 | 成本最低、直接消灭本次会话出现的所有数字漂移 |
| W1 | P0-4 报告版本从 aggregate 取 | 一行改动，堵住"写 0.8.0 实为 0.0.0" |
| W2 | P0-3 revision/digest 钉死 + 预热加 `--revision` | 对外可复现的前提 |
| W2 | P1-2 覆盖检查前置 | 避免再白跑两个 task |
| W3 | P0-2 `weight_type`/`regime` 字段（与 5b 同时上） | 5b 的骨架，越早定越省返工 |
| W4 | P1-1 重复轮 + 方差口径 | 让"93.2% vs 90%"这类比较站得住 |
| 持续 | P2 队列/上传/关机兜底 | 降人力 |

---

## 五、不该照抄社区的地方

1. **不要直接聚合上游 leaderboard.json**：上游是"论文数聚合 + LLM 抽取"，明确不独立验证（我们 `index.md` 也这么定位）。我们要的是自测数，schema 可以借，数据不能借。
2. **不要引入 `external_only` 给自己开脱**：我们的价值就是"本地真跑"，结果必须落地。
3. **不要为了测试覆盖率写无意义单测**：优先测**数字一致性**（docs/pptx ↔ reports JSON ↔ aggregate），这是本仓最容易错的地方，也是本次会话实际错的地方。

---

## 六、一句话结论

**上游把可信度做成 CI，我们把可信度写成教程。** 差距不在跑得快慢，在于"错了会不会自己红"。优先补三道门：榜单 schema、版本钉死、数字一致性测试——这三道能挡住本次会话里出现过的全部事故类型。

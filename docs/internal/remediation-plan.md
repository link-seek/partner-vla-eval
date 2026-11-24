# 整改计划：把"能说"变成"能验"

> 制定：2026-11-24 ｜ 依据：`docs/reports/eval-engineering-review.md`（工程化）+ `docs/reports/layout-review.md`（目录）
> 范围：全部 15 项，分 3 条线。**不含**新算力采购、不含 5b 训练本身（只做它的骨架）。
> 排序原则：先修"不占 GPU 且影响可信度"的，再跑"占 GPU 的长活"，最后动"会改路径"的。

---

## 0. 什么算"清完"

三条线各自的完成定义（可机器验，不靠口头）：

| 线 | 完成定义 | 验收命令 |
|---|---|---|
| A 可信度 | 任取一条榜单数，能顺着 `run id → aggregate → report → leaderboard` 全部对上，且权重/镜像可钉到 revision/digest | `python3 scripts/check_leaderboard.py && python3 scripts/check_reports.py && python3 scripts/check_coverage.py` |
| B 实验 | 5 task 有 Easy+Hard 双列；每格 `replicate_count>=2` 且有区间 | `python3 scripts/check_leaderboard.py` 无"单轮"警告 |
| C 目录 | 无归档混在现货、无校验器与数据分离、README 结构块 100% 可达 | `python3 scripts/check_paths.py && test -z "$(git status --porcelain)"` |

---

## 1. 三条线与依赖

```
A 可信度（不占 GPU，先做）
 ├─ A1 权重/镜像钉死 (revision + digest)
 ├─ A2 版本真实来源（报告不许手写）
 ├─ A3 覆盖前置检查
 ├─ A4 数字一致性（榜单已做，补 report↔aggregate）
 └─ A5 重复轮 + 方差（需 GPU，排在 B1 之后）

B 实验完整性
 ├─ B1 Hard 一轮（8–12h GPU，长跑，可与 A 并行）
 ├─ B2 weight_type / regime 字段（5b 骨架）
 └─ B3 ACT/DP serve 适配器（解锁官方 §4.5 对照）

C 目录归位（会改路径，最后做）
 ├─ C1 scripts 三分 + leaderboard 自包含
 ├─ C2 docs/reports JSON → docs/data；deck → docs/decks
 ├─ C3 tutorial/old → archive/tutorial-v1；合并 archive
 ├─ C4 configs 三分 + docker-compose 入 docker/compose
 ├─ C5 workflows 拆 manual/
 ├─ C6 上传回读校验 + idle-guard 关机兜底
 └─ C7 队列拆组（或 r01 串 job 链）
```

**关键判断**：C 会动路径 → **必须排在 A/B 之后**，否则每改一次就要修一轮引用。A 和 B1 可以并行（A 是本地代码，B1 是远端 GPU）。

---

## 2. A 线：可信度（要命的那 5 个）

### A1　权重钉 revision + 镜像钉 digest

| 项 | 内容 |
|---|---|
| 问题 | `configs/model-registry.json` 只有 `"ckpt": "2toINF/X-VLA-RoboTwin2"`，无 revision；预热 `hf-download download ...` 无 `--revision` → 永远拉 main。镜像只有 tag 无 digest，而 `docs/reproducibility.md:33` 自己把 digest 列为未完成 |
| 动作 | ①registry 加 `ckpt_revision`（40-hex）+ `serve_image_digest`；②`ci_robotwin_full.sh` 预热加 `--revision "$CKPT_REV"`；③报告生成时写入；④`check_leaderboard.py` 已有 40-hex 校验，改为对 registry 也生效 |
| 影响面 | `configs/model-registry.json`、`scripts/ci_robotwin_full.sh`、`scripts/ci_model_matrix.sh`、新增 `check_registry.py` |
| 工时 | 半天 |
| 验收 | `status=verified` 的模型缺 revision → lint 红；两次跑的报告 revision 相同 |
| 回滚 | 单 PR，revert 即回 |

### A2　版本不许手写

| 项 | 内容 |
|---|---|
| 问题 | aggregate 里 `harness_version: "0.0.0"`（本轮实测），报告却写 `"harness": "0.8.0"` |
| 动作 | ①`gen_reports.py` 从 aggregate 读，读不到写 `null` + `"harness_source":"unknown"`；②镜像构建注入真实版本（`vla_eval.__version__`）或 aggregate 增加 `image_digest` |
| 影响面 | 报告生成脚本、`docker/Dockerfile.robotwin-unified` |
| 工时 | 半小时（①）+ 一次重打镜像（②） |
| 验收 | 手写版本 → `check_reports.py` 比对 aggregate 不一致即红 |

### A3　覆盖检查前置

| 项 | 内容 |
|---|---|
| 问题 | CogACT 只发 4 个头，按 5 task 排期，跑到第 3 个才发现 |
| 动作 | `scripts/check_coverage.py`：registry 的 `covered_tasks` ∩ 输入 tasks，差集打印并 `exit 1`；`model-matrix.yml` 在 `Run matrix` 前调用 |
| 影响面 | 新脚本 + `model-matrix.yml` 一步 |
| 工时 | 2 小时 |
| 验收 | dispatch `db-cogact` + 5 task → 日志 `COVERAGE 3/5 missing=click_bell,handover_block` 并以非 0 退出 |

### A4　数字一致性（补 report ↔ aggregate）

| 项 | 内容 |
|---|---|
| 现状 | `leaderboard ↔ report` 已上门禁（今天做）；`report ↔ aggregate` 还没有 |
| 动作 | `check_reports.py`：每个 report 的 `(n, success)` 必须能在对应 aggregate 找到（aggregate 归档也进仓或从 OBS 拉清单） |
| 影响面 | 新脚本 |
| 工时 | 2 小时 |
| 验收 | 改 report 里一个数 → 红 |

### A5　重复轮 + 方差（排在 B1 后）

| 项 | 内容 |
|---|---|
| 问题 | 全仓每条都是 `replicate_count: 1`；`place_phone_stand` 两轮 16%/12% 无人能判 |
| 动作 | ①每 `(model,task)` 至少 2 轮（同集重跑，`skip_expert=false` 不变）；②报告给 `mean ± 轮间极差`；③`|Δ|<7pp → 同档` 规则写进脚本，不再只写文档 |
| 影响面 | matrix workflow（加 `repeats` 输入）、报告 schema、榜单 |
| 工时 | 代码 2h + GPU 每模型 5 task 再跑一轮（约 6–8h） |
| 验收 | `check_leaderboard.py` 无"单轮"警告 |

---

## 3. B 线：实验完整性

### B1　Hard 一轮（长跑，建议最先派）

| 项 | 内容 |
|---|---|
| 目的 | 补齐官方 §4.5 的 Easy/Hard 双列，回答"鲁棒性落差" |
| 口径 | 5 task × 50 ep × 2 模型，`task_config: demo_randomized` |
| 规模 | 500 ep；按 Easy 实测速率约 **8–12h GPU** |
| 动作 | matrix workflow 加 `task_config` 输入（现在硬编码 `demo_clean`，见 `ci_robotwin_full.sh:75`） |
| 工时 | 代码 1h + 跑 8–12h |
| 验收 | 报告 `hard_success` 非 null、`gap` 有值；OBS `Succeed/Failed` 计数正常 |
| 风险 | Hard 下 CogACT 可能大量失败（官方 Easy 16% 的 task，Hard 更低），**仍是有效数据，不许丢** |

### B2　weight_type / regime（5b 骨架）

| 项 | 内容 |
|---|---|
| 动作 | registry 与榜单条目落 `weight_type`(shared/finetuned) + `regime`(clean50 / clean50+rand500)；排名按 `(weight_type, protocol)` 分组，脚本强制 |
| 依赖 | R01 出数前完成，否则 5b 数据无处安放 |
| 工时 | 2h |

### B3　ACT/DP serve 适配器

| 项 | 内容 |
|---|---|
| 目的 | 解锁官方基线（`Avada11/*` 两个 ckpt）与 R01 自训 ckpt 的接入 |
| 动作 | `scripts/model_servers/robotwin_policy.py`（`--policy act\|dp`）+ `vla-serve-robotwin-{act,dp}` 镜像 + 1 task smoke |
| 依赖 | 开发需在 0002 的 robotwin 镜像内读 `policy/ACT|DP` 源码 |
| 工时 | 1–1.5 天（含镜像构建） |

---

## 4. C 线：目录归位（最后做，每步一个 PR）

| # | 动作 | 影响面 | 工时 |
|---|---|---|---|
| C1 | `scripts/` 三分 `ci/ gates/ data/`；`leaderboard/{data,schemas,scripts,tests}` 自包含 | 6 workflow + 2 脚本 + lint 2 步 | 2h |
| C2 | `docs/reports/*.json` → `docs/data/`；`deck/` → `docs/decks/`；同步 `leaderboard.json` 的 `report` 字段 | 13 JSON + 2 文档 | 1.5h |
| C3 | `docs/tutorial/old/` → `docs/archive/tutorial-v1/`；合并 `docs/archive/` | 12 + 互引 + `tutorial/index.md:93` | 1h |
| C4 | `configs/{benchmarks,model_servers,registry}/`；`docker-compose.*` → `docker/compose/` | 3 + payload 清单 | 1.5h |
| C5 | workflows 拆 `manual/`（8 个一次性排障） | 8（移动即改引用） | 1h |
| C6 | `obsutil cp` 后回读校验；`idle-guard` cron 兜底关机 | 6 workflow + 1 新 workflow | 2h |
| C7 | 队列拆组，或 `r01.yml` 串 `prep→train→eval` job 链 | 2–3 workflow | 2h |

**每步做完必须跑**：`python3 scripts/check_paths.py`（今天新增的门禁，专门防改断链接）。

---

## 5. 排期（按"是否占 GPU"分道）

| 时间 | GPU 道 | 人/代码道 |
|---|---|---|
| 今天 | **派 B1 Hard（8–12h 长跑）** | A2（版本来源，0.5h）→ A1（revision，半天） |
| 明天 | B1 收尾、取数归档 | A3（覆盖检查）→ A4（report↔aggregate） |
| 第 3 天 | A5 第二轮（6–8h） | C1、C2 |
| 第 4 天 | B3 适配器 smoke | C3、C4 |
| 第 5 天 | — | C5、C6、C7；B2 与 5b 立项合并 |

**关键路径是 B1**：它占 8–12h GPU 且阻塞 A5 与"Hard 双列"。所以第一步就派它，代码活并行做。

---

## 6. 明确不做（控制范围）

1. 不新建算力（A30/A100 仍为决策项，不在本计划）
2. 不动 `docs/tutorial/` 的 Diátaxis 分类（已对）
3. 不重写 `docker/` 的扁平 Dockerfile（11 个文件不值得分层）
4. 不引入上游的论文聚合数据（我们只出自己跑的数）
5. 不为覆盖率写无意义单测（只测数字一致性与口径隔离）

---

## 7. 风险

| 风险 | 影响 | 应对 |
|---|---|---|
| Hard 大面积失败被误读为"模型不行" | 结论被质疑 | 报告单列 `errors`，失败也给录像；Easy/Hard 并排不合并 |
| C 线改路径断链接 | 文档全断 | `check_paths.py` 每步必跑；一步一 PR |
| A5 第二轮结果与第一轮差 >10pp | 原结论要改 | 这正是要测的；差大就如实写"单轮不可信"，不粉饰 |
| 重复跑撞队列（只 1 个 pending） | run 被顶掉 | 先做 C7 或串 job 链，再连派 |

---

## 8. 今天就能开始的两件事

1. **派 B1 Hard**（占 GPU 长跑，回收 8–12h 的关键路径）
2. **A2 + A1**（不占 GPU，把"版本/权重可钉"这两个最要命的补上）

需要你点头的只有一件：**B1 会烧 8–12h 的 0002**（约 ¥260–390 按需价），其余都是本地代码。

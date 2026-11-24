# 整改计划：把"能说"变成"能验"

> 制定：2026-11-24 ｜ 依据：`docs/reports/eval-engineering-review.md`（工程化）+ `docs/reports/layout-review.md`（目录）
> 范围：全部 15 项，分 3 条线。**不含**新算力采购、不含 5b 训练本身（只做它的骨架）。
> 排序原则：先修"不占 GPU 且影响可信度"的，再跑"占 GPU 的长活"，最后动"会改路径"的。

---

## 0. 什么算"清完"

三条线各自的完成定义（可机器验，不靠口头）：

| 线 | 完成定义 | 验收命令 |
|---|---|---|
| A 可信度 | 任取一条榜单数，能顺着 `run id → aggregate → report → leaderboard` 全部对上，且权重/镜像可钉到 revision/digest | `python3 leaderboard/scripts/check_leaderboard.py && python3 scripts/gates/check_reports.py && python3 scripts/gates/check_coverage.py` |
| B 实验 | 5 task 有 Easy+Hard 双列；每格 `replicate_count>=2` 且有区间 | `python3 leaderboard/scripts/check_leaderboard.py` 无"单轮"警告 |
| C 目录 | 无归档混在现货、无校验器与数据分离、README 结构块 100% 可达 | `python3 scripts/gates/check_paths.py && test -z "$(git status --porcelain)"` |

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
 ├─ C3 ✅ 旧教程稿 → archive/tutorial-v1；论文 → archive/papers
 ├─ C4 configs 三分 + docker-compose 入 docker/compose
 ├─ C5 ✅ workflows 分类索引（子目录不可行，已改文档）
 ├─ C6 上传回读校验 + idle-guard 关机兜底
 └─ C7 队列拆组（或 r01 串 job 链）
```

**关键判断**：C 会动路径 → **必须排在 A/B 之后**，否则每改一次就要修一轮引用。A 和 B1 可以并行（A 是本地代码，B1 是远端 GPU）。

---

## 2. A 线：可信度（要命的那 5 个）

### A1　权重钉 revision + 镜像钉 digest

| 项 | 内容 |
|---|---|
| 问题 | `configs/registry/model-registry.json` 只有 `"ckpt": "2toINF/X-VLA-RoboTwin2"`，无 revision；预热 `hf-download download ...` 无 `--revision` → 永远拉 main。镜像只有 tag 无 digest，而 `docs/reproducibility.md:33` 自己把 digest 列为未完成 |
| 动作 | ①registry 加 `ckpt_revision`（40-hex）+ `serve_image_digest`；②`ci_robotwin_full.sh` 预热加 `--revision "$CKPT_REV"`；③报告生成时写入；④`check_leaderboard.py` 已有 40-hex 校验，改为对 registry 也生效 |
| 影响面 | `configs/registry/model-registry.json`、`scripts/ci/ci_robotwin_full.sh`、`scripts/ci/ci_model_matrix.sh`、新增 `check_registry.py` |
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
| 动作 | `scripts/gates/check_coverage.py`：registry 的 `covered_tasks` ∩ 输入 tasks，差集打印并 `exit 1`；`model-matrix.yml` 在 `Run matrix` 前调用 |
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
| C3 | ✅ 已完成：旧教程稿 → `docs/archive/tutorial-v1/`，论文 → `docs/archive/papers/` | 12 + 互引已改 | 1h |
| C4 | `configs/{benchmarks,model_servers,registry}/`；`docker-compose.*` → `docker/compose/` | 3 + payload 清单 | 1.5h |
| C5 | ✅ 已完成（方案修正）：**GitHub 不支持 workflow 子目录**，改为 `.github/workflows/README.md` 分类索引 | 1 文档 | 0.5h |
| C6 | ✅ 已完成：5 workflow 回读校验 + `idle-guard.yml` + lint 回归门 | 6 workflow | 2h |
| C7 | 队列拆组，或 `r01.yml` 串 `prep→train→eval` job 链 | 2–3 workflow | 2h |

**每步做完必须跑**：`python3 scripts/gates/check_paths.py`（今天新增的门禁，专门防改断链接）。

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

---

## 9. D 线：协作面收口（PR / issue / 分支 / git 历史）

盘点结果（2026-11-24 实查）：

| 项 | 状态 | 处置 |
|---|---|---|
| 开着的 PR | **0** | 无需动作 |
| Issue #11（报告归档缺失） | 本轮 `cogact_robotwin-{adjust_bottle,place_phone_stand}-x50.json` 正好补齐 | **已关**，附数字与噪声说明 |
| Issue #14（总账） | 陈旧 | 已评论更新：出数、deck、两份检视、三道门禁、待办 |
| Issue #8（OBS 自定义前缀 + 开跑前校验） | 半解决：校验步骤已有、上传 403/0 通过 | **保留**，已记明仍缺三项（自定义前缀未测、`|| true` 吞错、路径多一层 `matrix/`），并入 C6 |
| 远程分支 `docs/tutorial-ia` | 0 ahead / 170 behind，纯落后 | **已删**（SHA `bcae8493`） |
| 远程分支 `docs/tutorial-v1-2-stack-effects` | 1 ahead，但改动只针对已不存在的旧教程结构 | **已删**（SHA `2a7df768`）；核对后差异仅为归档时加的 `nav_exclude` 头，实质已进 `docs/archive/tutorial-v1/`，A–D 栈差异表已进 `explanation/01-stack-effects.md` |

### D1　git 历史分叉（必须先处理）

**问题**：本轮所有推送走的是 GitHub API（`POST /git/commits`），远程 commit SHA 与本地 SHA **系列不同**——内容一致但历史分叉。

实测：
```
本地 HEAD tree  = f1ca234a...
远程 main tree  = 4b000e1d...
逐 blob 比对：156 vs 157 个文件，差异仅 1 个（Open Design 边车 .artifact.json）
```

**风险**：此刻在本地 `git push` 会撞非快进，或灌入 37 个重复历史。

**动作**：
1. 已删那 1 个越界文件并加 `.gitignore` → 内容对齐
2. 在**能直连 github.com 的环境**执行一次：
   ```bash
   git fetch origin && git reset --hard origin/main
   ```
   本容器 `git fetch` 不通 github.com:443，但 `gh api` 通 api.github.com —— 两条出口不同。
3. 之后恢复「本地 commit → git push」正常流程，不再用 API 造提交

**在 D1 完成前**：继续用 API 推送，且**不要**在本地 `git push`。

### D2　流程规矩（防止再分叉）

| 规矩 | 原因 |
|---|---|
| 一个改动一个 PR，不再直推 main | 本轮 37 个提交全是直推，没有 review 记录 |
| issue 关闭必须附证据（run id / 文件路径 / 数字） | #11 是"详情待补"挂了 15 天，实际早就该关 |
| 分支生命周期 ≤ 1 周，超期要么合并要么删 | 两个分支分别滞后 170/171 个提交，等于死分支 |

---

## 10. 执行进度（滚动更新）

| 项 | 状态 | 证据 |
|---|---|---|
| A1 权重钉 revision | ✅ 完成 | registry 加 `ckpt_revision`（真实 sha）；预热 `--revision`；`check_registry.py` 拦 verified 缺版本 |
| A2 版本取自 aggregate | ✅ 完成 | 5 份 X-VLA 报告改为实测 `0.0.0` + `harness_note` |
| A3 覆盖检查前置 | ✅ 完成 | `check_coverage.py`；`model-matrix.yml` 新增 Coverage check；CI 反例返回 2 |
| A4 报告自洽 | ✅ 完成 | `check_reports.py`（19 份报告，mean_success vs success/n、镜像必填） |
| A5 重复轮 | 🟡 管线就绪、待跑 | matrix 加 `replicate` 输入；产物/OBS 按轮次分目录；`make_leaderboard.py` 支持多轮合并（replicate_count + rate_min/max）；门禁强制多轮必带极差 |
| B1 Hard | 🔄 运行中（run 45503556969，X-VLA 5 task） | `task_config: demo_randomized` 已确认；按实测吞吐 250ep ≈ 15.8h ≈ ¥521 |
| B2 weight_type/regime | ✅ 完成 | registry 5 模型全标；两道门禁（缺字段/混排即红）；schema 支持 `ranked_separately` |
| B3 ACT/DP 适配器 | 🟡 代码+单测完成，**未 smoke** | 观测转换 16 项单测进 lint；镜像内实测：ACT 可导入、DP 缺 hydra/dill；registry 仍 `pending` |
| C1 scripts 三分 + leaderboard 自包含 | ✅ 完成 | `scripts/{ci,gates,data}`、`leaderboard/scripts/`；28 处引用已改 |
| C2 结果 JSON → docs/data | ✅ 完成 | 19 JSON + deck → docs/decks；registry/leaderboard/schema 同步 |
| C3 归档合并 | ✅ 完成 | tutorial-v1 12 个、papers 3 个；外链与相对路径已改 |
| C4 configs 三分 | ✅ 完成 | benchmarks 13 / model_servers 9 / registry 1；脚本与 workflow 同步 |
| C5 workflows 分类 | ✅ 完成（方案修正） | GitHub 不支持子目录 → `.github/workflows/README.md` 索引（25 个全覆盖） |
| C6 上传回读 + idle-guard | ✅ 完成 | 5 个 workflow 去掉 `\|\| true` 改回读计数；新增 `idle-guard.yml`（30min cron，三条件全满足才关）；lint 加回归门 |
| C7 队列拆组 | ✅ 完成 | `r01-prep` 独立到 `data-ecs-0002`（不占 GPU pending 位）；GPU 组加语义注释 |
| D 收口 | ✅ 部分 | #11 关、#14/#8 更新、2 分支删；D1 git 分叉待外部环境 fetch |

**CI 证据（C 线后半段）**：run `45438238470` 七道门全绿（C1 落地后）。
**CI 证据（A 线）**：run `45432762112` —— SYNTAX / VERSIONS / LEADERBOARD / PATHS / REPORTS / REGISTRY / COVERAGE 七道全绿。

---

## 11. 估算修正（2026-11-24）

早先给 B1 报「8–12h / ¥260–390」是按主观节奏估的，**与实测吞吐不符**，此处更正：

| 依据 | 数值 |
|---|---|
| 实测 run 45266034430（Easy，5 task × 50ep = 250 ep） | 15.8h |
| 吞吐 | **15.78 ep/h**（4 分片） |
| Hard 单模型 5 task（250 ep） | ≈ 15.8h ≈ **¥521** |
| Hard 双模型 5 task（500 ep） | ≈ 31.7h ≈ **¥1042** |
| A5 重复轮单模型（250 ep） | ≈ 15.8h ≈ **¥521** |

所以 B1 实际按 **单模型（X-VLA）先跑**，成本约 ¥520，而不是原估的 ¥260–390；CogACT 的 Hard 待 X-VLA 跑完再决定。

### C1 回归（已修）

`scripts/` 下沉到 `scripts/ci/` 后，`cd "$(dirname "$0")/.."` 只到 `scripts/`，
导致 `configs/registry/model-registry.json` 找不到、跑批立即失败（run 45502286025）。
已全部改成 `/../..`，并在 lint 加 `cd-depth` 守卫（bash -n 抓不到这类运行期路径错误）。

---

## 12. 收 Hard 数的固定管线（2026-11-24 补齐）

之前这段只在 `/tmp`，机器一关就没了。现已进仓：

```bash
# 1) 汇总 aggregate（easy 或 hard）
bash scripts/data/collect_matrix.sh x-vla-robotwin2 hard > /tmp/hard.json

# 2) 生成报告：easy 新建；hard 在既有 easy 报告上回填 hard_success / gap
python3 scripts/data/gen_reports.py /tmp/hard.json hard

# 3) 建榜单（easy/hard 各一份，值全部从 collected+registry 取，不许手写）
python3 scripts/data/make_leaderboard.py /tmp/hard.json hard --run <run_id>

# 4) 门禁（含"报告有 hard_success 但榜单缺行"的交叉校验）
python3 scripts/gates/check_reports.py && python3 leaderboard/scripts/check_leaderboard.py
```

`hard` 模式实测（mock）：easy 0.96 / hard 0.40 → `gap: 0.56`，写进同一份报告，不覆盖 Easy 数。

---

## 13. B3 交付（2026-11-24，未验证）

| 产物 | 说明 |
|---|---|
| `scripts/model_servers/robotwin_policy.py` | 一个文件切 `act\|dp`；绕开官方 `eval()` 直接用 `get_model()`+`get_action()`；策略自带时序状态，故 harness 层 `chunk_size=None` 防双重缓冲 |
| `configs/model_servers/serve-robotwin-act.yaml` / `-dp.yaml` | 按官方 `deploy_policy.yml` 默认值填；ACT 用 `ckpt_dir`，DP 用 `task_name+ckpt_setting+expert_data_num+seed` |
| `docs/internal/act-dp-adapter-runbook.md` | 首次 smoke 手册：起服 → 1ep → 三条通过标准 → 常见失败表 |
| registry | `act-baseline` / `dp-baseline` 从 `dropped` 改 `pending`（有适配器但未验证；`verified` 必须等 smoke 过） |

**为什么现在不能标 verified**：verified 的含义是"本仓已跑出数"。适配器只是能加载，
动作维度/相机通道/归一化这三处都可能错，必须 1ep smoke 才能定。

---

## 14. B3 依赖体检（2026-11-24 实测，非推测）

在 `vla-eval-robotwin:0.8.0-ee-slim` 的 robotwin 环境里真跑了一遍导入：

```
ACT import ok: True True True          # get_model / encode_obs / reset_model
DP  import FAIL: ModuleNotFoundError No module named 'hydra'
dep ok: IPython / torch / cv2 / h5py
dep MISSING: detr（顶层，但 ACT 走相对导入可用）
diffusion_policy: vendored 在 policy/DP/diffusion_policy，dp_model.py 自己 append sys.path
```

结论：
- **ACT 可直接用现成 robotwin 镜像起 serve**（依赖齐）
- **DP 需要另烘镜像**（hydra + dill），不是改代码能解决的
- 适配器已加 fail-fast：DP 导入失败时直接报"缺 hydra/dill，需另烘镜像"，不再抛裸异常

---

## 15. B3 ACT 前向体检通过（2026-11-24，CPU 打桩）

```
constructed in 4.0s, 31.35M params
call1 (1,14) 1.6s finite   → 首次推理
call2/3 (1,14) 0.0s finite → chunk 复用生效
reset_model → 仍 14 维
```

修掉两个会直接导致 smoke 失败的问题：缺 `dropout`（改用官方 parser 默认值打底）、
`camera_names` 为空（显式设三相机名）。

**真实 ckpt 也验过了**（`Avada11/RoboTwin-Model-AgileX-ACT`，click_bell seed100）：
`dec_layers=7 → missing=0 unexpected=0`，78.51M 参数，前向 14 维有限值。

**四个配置坑**：dropout=0.1、camera_names=3、hidden_dim=512/dim_feedforward=3200、dec_layers=7；
**一个文件名坑**：官方 ckpt 不叫 `policy_last.ckpt`，内置加载会静默用随机权重。

**官方 ACT 只覆盖本考场 2/5**（adjust_bottle、click_bell），grab_roller/place_phone_stand/handover_block 无 ckpt。
→ 榜上三家覆盖面各不相同：X-VLA 5/5、CogACT 3/5、ACT 2/5。

**B3 剩余**：跑满一整集（需 GPU 空闲）。仍在 `pending`。

---

## 16. B1 实测速率与 ETA 再修正（2026-11-24 23:45Z）

用运行中的日志算（22:54:48 首个 episode → 23:44:54 第 10 个）：

| 项 | 值 |
|---|---|
| 已跑 episode | 10（grab_roller） |
| 耗时 | 50 分钟 |
| 速率 | **5.0 分钟/episode**（Hard 比 Easy 慢，Easy 是 3.8） |
| 250 ep 预计 | **约 21 小时**（不是我上一轮说的 15.8h） |
| 成本 | 约 ¥690（21h × ¥32.87） |

**首个 Hard 信号**：`grab_roller` 已出 10 集，6 成功 / 4 失败 = **60%**，
对比 Easy 的 49/50 = 98%。这正是 Hard 该体现的落差，且失败都是 `steps=400` 跑满（不是 ERROR）。

**结论**：B1 完成约在 2026-11-25 19:30Z。A5 第二轮再需约 16h，两者串行总成本约 ¥1200。

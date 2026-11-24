# 目录划分检视：现状、问题、目标布局

> 日期：2026-11-24 ｜ 对象：本仓 147 个文件的目录划分
> 方法：实测目录树 + 引用可达性扫描 → 对照上游仓库布局与 Diátaxis 文档分类 → 给目标树与迁移表
> 结论先行：**内容分类（Diátaxis）是对的，物理归位是乱的**——同一类东西散在两三处，归档混在现货里，README 描述已过期。

---

## 一、现状（实测）

```
partner-vla-eval/
├── README.md                        ← 结构块已过期（见 P6）
├── docker-compose.split.yml         ← 根目录，但 Dockerfile 都在 docker/
├── docker-compose.verify.yml        ← 同上
├── configs/         23 个           ← run-*/serve-* 与 model-registry.json 混放
├── docker/          11 个           ← Dockerfile.* + versions.yaml + entrypoint + patch
├── scripts/         10 个 + lib/    ← CI 编排 / 门禁 / 数据准备 三类混放
├── leaderboard/      2 个           ← 今天新增：data + schema（校验脚本却在 scripts/）
├── docs/            47 个 md + 2 tex + 2 pptx
│   ├── _config.yml, _sass/          ← 站点配置与内容混在 docs 根
│   ├── （根）9 个 md                ← 对外文档 + 内部规划混放
│   ├── tutorial/                    ← Diátaxis 四类（本仓最健康的部分）
│   │   ├── old/      12 个          ← 旧教程归档，嵌在现货树里
│   │   ├── explanation/ operator/ partner/ reference/
│   ├── reports/     21 个           ← 结果 JSON + 叙事 md + deck（含 3MB pptx）混放
│   ├── archive/      4 个           ← 第二个归档目录（含论文 .tex）
│   └── upstream/     1 个           ← **未被 git 跟踪（?? docs/upstream/）**
└── .github/workflows/ 24 个         ← 生产类与一次性排障类平级混放
```

---

## 二、七个具体问题（每条带证据）

### P1　两个归档目录，且归档混在现货里

- 原 `docs/archive/`：论文 3 份 + README → **已收拢到 `docs/archive/papers/`（C3）**
- 原 tutorial 旧稿目录：12 个旧教程稿（曾占 `docs/*.md` 的 **26%**）→ **已迁至 `docs/archive/tutorial-v1/`（C3）**

**问题**：找"当前有效的文档"时要先排除 12 个归档文件；两个 archive 目录语义不同却同级（一个放论文，一个放旧教程），没有统一入口。

### P2　upstream 草稿目录曾是孤儿（S1 已修）

```
$ git status --short
?? docs/upstream/
$ git ls-files docs/upstream
（空）
```
一个文件 `serve-yaml-onboarding.md` 从未提交。它要么该进 git 并归位，要么该删——当时两头不靠。

**已处理（S1）**：移入 `docs/internal/serve-yaml-onboarding.md` 并纳入 git；空目录删除。
该文件自述"DRAFT for upstream discussion (not yet submitted)"，属内部过程稿，符合 `docs/internal/` 定位。

### P3　docs 根混了三类东西

| 类别 | 现居 `docs/` 根的文件 | 应该在哪 |
|---|---|---|
| 站点配置 | `_config.yml`、`_sass/` | 保持（Pages 要求 `/docs` 为源，可接受） |
| 对外文档 | `index.md`、`blog-precision-cliff.md` | `docs/` 根（合理） |
| **内部过程文档** | `submission-plan.md`、`onboarding-tasks.md`、`two-day-patrol.md`、`proposal-stack-effects.md`、`partner-onboarding.md`、`reproducibility.md` | **`docs/internal/`** |

证据：这 6 个文件全部带 `nav_exclude: true`——它们本来就不该出现在站点导航里，但仍和对外文档同层，读者无法区分"这是给外人看的还是给自己看的"。

### P4　`docs/reports/` 混三类资产

- 结果数据：12+ 个 `*.json`
- 叙事报告：`R01-training-data-axis.md`、`eval-engineering-review.md`
- 交付件：`deck/`（含 `capability-deck.pptx` 2.5MB + 可编辑版 512KB）

**问题**：`reports/` 既是对外数据归档，又塞了 3MB 二进制；`docs/` 从 3.4MB 里大头是 pptx。

### P5　`configs/` 与 `scripts/` 各自混类

**configs（23 个）**：
- 配置：`serve-*.yaml`(8) + `run-*.yaml`(13)
- **数据真源**：`model-registry.json` —— 不是"配置"，是榜单/矩阵的输入数据，却被当成 yaml 邻居
- 命名不一致：`run-libero-goal10.yaml`（bench+task+集数）vs `run-robotwin-xvla-easy50.yaml`（bench+model+protocol+集数）

**scripts（10 个）**：
- CI 编排：`ci_*.sh`(6) + `lib/common.sh`
- **门禁**：`check_versions.py`、`check_leaderboard.py`（CI 校验，不参与跑批）
- 数据准备：`prepare_robotwin_data.sh`

而今天新增的 `check_leaderboard.py` 在 `scripts/`，它校验的 schema 在 `leaderboard/`——**校验器与被校验物分离**。上游是自洽的：`leaderboard/{data,scripts,tests}` 放一起。

### P6　README 的"仓库结构"已过期（实证）

```
$ ls scripts/upstream
ls: cannot access 'scripts/upstream': No such file or directory
```

README:30 写着 `scripts/upstream/run_sharded.sh  上游分片脚本（v0.7.0 vendor）` —— **文件不存在**；
README:43 写 `vla-eval: v0.7.0` —— 实际 `docker/versions.yaml` 已是 **0.8.0**；
README:31 写 "smoke/full/sync/repair 四类 workflow" —— 实际 **24 个**。

### P7　workflows 24 个无分组

按前缀粗分：`probe`(3) `pi0`(3) `build`(3) `repair`(2) `power`(2) `pi`(2) + 9 个单件。

其中 **8 个是一次性排障/自检**（`probe-jev`、`probe-jev-hw21`、`probe-guard`、`audit-v100`、`inspect-v100`、`power-selftest`、`ts-join-v100`、`repair-v100-0001`），与 6 个生产 workflow 平级。任何人扫 Actions 列表都要先分辨"哪个能点"。

---

## 三、社区对照

**上游 `allenai/vla-evaluation-harness`**（实读目录）：
```
src/                     代码（含 model_servers/ benchmarks/ results/）
tests/                   44 个 test_*.py
configs/{benchmarks,model_servers}/   配置按用途分目录
docker/
docs/{architecture,design-philosophy,rfcs,reproductions,proposal}/
leaderboard/{benchmarks,data,experiments,scripts,site,tests}/   ← 数据+校验+测试同处
experiments/
examples/
```

**可借鉴的三条**：
1. **配置按用途分目录**（`configs/benchmarks/` vs `configs/model_servers/`）——我们的 `run-*`/`serve-*` 正好对应。
2. **`leaderboard/` 自包含**：`data + scripts + tests` 一处；校验器跟着数据走。
3. **代码与测试平级**：`src/` 与 `tests/` 分开，我们目前没有 `tests/`（已在 `eval-engineering-review.md` P0-1 立项）。

**Diátaxis**：本仓 `docs/tutorial/{tutorial,operator,partner,reference,explanation}` 已经是 Diátaxis 变体，**这部分不用动**——问题不在分类法，在归档与散落。

---

## 四、目标布局

```
partner-vla-eval/
├── README.md                       ← 重写"仓库结构"，并加路径存在性检查
├── configs/
│   ├── benchmarks/     run-*.yaml          （13）
│   ├── model_servers/  serve-*.yaml        （8）
│   └── registry/       model-registry.json + model-registry.schema.json
├── docker/
│   ├── Dockerfile.*  versions.yaml  entrypoint-*.sh  *.patch
│   └── compose/        docker-compose.split.yml, docker-compose.verify.yml
├── scripts/
│   ├── ci/             ci_*.sh + lib/common.sh
│   ├── gates/          check_versions.py, check_leaderboard.py, check_paths.py
│   └── data/           prepare_robotwin_data.sh
├── leaderboard/                    ← 自包含（对齐上游）
│   ├── data/           leaderboard.json
│   ├── schemas/        leaderboard.schema.json
│   ├── scripts/        check_leaderboard.py
│   └── README.md       准入规则（从 tutorial/leaderboard.md 指向）
├── docs/
│   ├── index.md  blog-*.md  _config.yml  _sass/
│   ├── tutorial/                   ← 不动（Diátaxis 已对）
│   ├── reports/                    ← 只留叙事 md
│   │   ├── R01-training-data-axis.md
│   │   └── eval-engineering-review.md
│   ├── data/                       ← 结果 JSON（12+）
│   ├── decks/                      ← capability-deck.html + exports/
│   ├── internal/                   ← 6 个 nav_exclude 的内部过程文档
│   └── archive/
│       ├── tutorial-v1/            ← 旧教程稿（12，已迁入）
│       └── papers/                 ← 2 tex + paper-stack-effects.md
└── .github/workflows/
    ├── （生产 6 个留在顶层）
    └── manual/                     ← 8 个一次性排障/自检
```

**关键取舍**：
- `docs/data/` 与 `docs/reports/` 分开：**JSON 是机器读的，md 是人读的**，混放导致每次改文档都要在 12 个 JSON 里找。
- `docs/archive/` 统一两个来源，保留 `tutorial-v1/README.md` 的迁移映射。
- `scripts/gates/` 独立：门禁不参与跑批，混在 `ci/` 里会被误认为"要跑的东西"。

---

## 五、迁移表（影响面已实测）

| 动作 | 引用它的文件数 | 必须同步改 |
|---|---|---|
| `configs/*.yaml` → `configs/{benchmarks,model_servers}/` | 3 | `ci_robotwin_full.sh`（`$WORK/configs/$SERVE_YAML`）、`ci_model_matrix.sh`、README |
| `configs/registry/model-registry.json` → `configs/registry/` | 3 | `ci_model_matrix.sh:15`、`model-matrix.yml:91`、`build-payload` 清单 |
| `scripts/ci_*.sh` → `scripts/ci/` | 3 | 6 个 workflow 的 `bash scripts/...`、payload build 清单 |
| `scripts/check_*.py` → `scripts/gates/` | 0（CI 里用路径调用） | `lint.yml` 两步 |
| `docs/reports/*.json` → `docs/data/` | 1（deck/README 引用） | `REPORT-PLAN.md`、`leaderboard.json` 的 `report` 字段、`eval-engineering-review.md` |
| ✅ 旧教程稿 → `docs/archive/tutorial-v1/` | 已完成（3 处外链 + 12 条相对路径已改） | — |
| `docker-compose.*.yml` → `docker/compose/` | 0 | 无（仅 README 提及） |

**风险点**：`docs/reports/*.json` 挪位置会断 `leaderboard.json` 里的 `report` 字段——而这正是今天刚加的对账门禁。迁移必须与新路径同步，否则 lint 会红（这其实是好事：门禁会替我们验）。

---

## 六、分期建议（范围可控，先小后大）

| 阶段 | 动作 | 影响面 | 可独立回滚 |
|---|---|---|---|
| **S1（已完成）** | 重写 README"仓库结构"（修正 3 处过期）；孤儿目录收编进 `docs/internal/`；`scripts/gates/check_paths.py` 进 lint | 4 文件 | 是 |
| **S2** | `docs/reports/*.json` → `docs/data/`；`leaderboard.json` 的 `report` 字段同步 | 1 JSON + 2 文档 | 是 |
| **S3（已完成）** | 旧教程稿 → `docs/archive/tutorial-v1/`；论文 → `docs/archive/papers/` | 12 + 链接 | 是 |
| **S4** | `scripts/` 三分（ci/gates/data）；`leaderboard/` 自包含 | 6 workflow + 2 脚本 | 是 |
| **S5** | `configs/` 三分；`docker-compose` 入 `docker/compose/` | 3 + payload 清单 | 是 |
| **S6** | workflows 拆 `manual/` | 8 个（移动即需重命名引用） | 是 |

**建议先只做 S1**：零风险，且 `check_paths.py` 会成为后续每一步的安全网——它能在每次 `git mv` 后立刻告诉你哪些引用断了。

---

## 七、不该改的地方

1. **`docs/tutorial/` 的 Diátaxis 分类**：已经对了，别动。改它只会破坏已有链接与读者心智。
2. **`docs/` 根放 Pages 配置**：GitHub Pages 要求 `/docs` 为源，`_config.yml`/`_sass` 只能在这。可接受。
3. **`docker/` 里 Dockerfile 扁平**：11 个文件规模，分 `serve/`、`bench/` 反而增加跳转成本。
4. **不要为了"整齐"把 `configs/` 拆成每文件一目录**：23 个配置不值得。

---

## 八、一句话结论

**分类法是对的，归位是乱的**：归档混在现货里（12/47）、两个归档目录、校验器与被校验物分离、README 描述已与事实脱节 3 处。不需要重构分类，需要一次**分六步的物理归位 + 一个路径存在性门禁**——后者先做，它保证前面每一步不把链接改断。

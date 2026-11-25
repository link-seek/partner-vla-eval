# 贡献规则（治理的唯一入口）

> 本文件定义"什么东西放哪、怎么改、什么会被门禁拦"。**改动前先读这一节**。
> 分类原则来自社区通行做法：产物 / 基础设施 / 文档 / 流程 四类分开治理，
> 凭证与地址不进仓。

---

## 一、四类归属（放错位置会被门禁拦）

| 类 | 是什么 | 住在哪 | 谁写 |
|---|---|---|---|
| **1 烧卡产物** | 评测结果、榜单、逐集记录 | 大件 → OBS；索引/汇总 → `docs/data/`、`leaderboard/` | **只有流水线**（`post-run-collect`） |
| **2 基础设施** | 镜像、workflows、脚本、配置、registry | 仓 + SWR/GHCR | 只有 PR |
| **3 文档教程** | 教程、原理、参考；过程记录；决策 | 站点（`docs/`）/ Discussion / `docs/adr/` | PR 或评论 |
| **4 仓库流程** | 本文件、PR 模板、CODEOWNERS | 仓根 / `.github/` | owner |

**判断口诀**：机器产生 → 1；改了影响"跑不跑得通" → 2；给人读 → 3；约束人怎么协作 → 4。
**密码、密钥、机器地址**：都不进仓（见第五节）。

### 真源唯一

`configs/registry/model-registry.json` 是模型/考场/镜像的**唯一真源**。
第 1 类和第 3 类**只读**它，不得手写分数或参数。

---

## 二、分支与合并（硬规则）

```
main 上只允许常驻能力。任何只做一次的东西活在分支，用完删分支，不合并不留痕。
```

- 开分支 → 做事 → **不合并**（一次性动作）或 提 PR（常驻改动）→ 删分支
- 一次性诊断/探针/迁移**不许**以 workflow 形式进 main
- 分支上跑 workflow：`gh workflow run <file> --ref <branch>`（UI 下拉只列默认分支）
- 一次性动作的**结论**要留：写进 issue 评论或 `docs/howto/`，别跟分支一起删掉

---

## 三、workflow / 配置的登记制

新增或改动 `workflow` / `configs` 前，先在 `scripts/gates/infra-inventory.json` 登记：

| kind | 含义 | 允许进 main |
|---|---|---|
| `routine` | 每次都要跑（评测、收数、门禁、构建） | ✅ |
| `rare` | 出事才用（装机、重建 tailnet、审计） | ✅（必须写 owner + when） |
| `option` | 靠参数引用（`run_yaml` / `serve_yaml` / build-arg） | ✅（登记在 configs 段） |
| `one-off` | 一次性 | ❌ **禁止**（活在分支） |

门禁 `scripts/gates/check_infra_inventory.py` 会检查：
1. 每个 workflow 必须登记，且 `kind` 只能是 `routine`/`rare`
2. 清单里不许有实际不存在的文件（防止清单腐化）
3. 出现 `one-off` 即红

---

## 四、PR 必须满足

1. 用 `.github/pull_request_template.md`（写清"改了哪一类""怎么验的"）
2. 状态检查 `lint` 与 `actionlint` 通过（`secret-hygiene` 也会跑）
3. 涉及第 1 类数字：PR 里必须给出 run id 或 aggregate 路径
4. 涉及第 2 类镜像：必须更新 `registry` 的 digest（不许手抄，用 `buildx imagetools inspect`）

---

## 五、凭证与地址（铁律）

- 真值只在 **GitHub Secrets** 与目标机 `.env`（600）
- 仓里只能有 `.env.example`（键名，无值）
- 机器地址走 **repo variables**（`vars.V100_0002_HOST` 等），不写字面 IP
- 提交前本地可跑：`gitleaks dir . --redact -c .gitleaks.toml`
- CI：`secret-hygiene.yml`，命中即红

---

## 六、文档（第 3 类）

| 内容 | 去哪 | 门禁 |
|---|---|---|
| 教程/原理/参考 | `docs/`，必须有 `title` + `parent` | 进站、构建通过、链接可达 |
| 过程/进度/待办 | **Discussion 或 Issue** | 不写 md |
| 决策（为什么这么定） | `docs/adr/ADR-NNNN-*.md`，**接受后冻结** | 不进站（`nav_exclude`） |
| 运维手册 | `docker/AGENTS.md`、`scripts/AGENTS.md`（就近） | 不进站 |

站点只发布公开面；内部稿一律 `nav_exclude: true`。目录规则见 `docs/AGENTS.md`。
产物保留策略（OBS 桶生命周期）见 `docs/adr/ADR-0002` 与 `docs/howto/obs-lifecycle.md`。

门禁分两层：

- **构建**：CI 跑 `bundle exec jekyll build --strict_front_matter`（`docs/Gemfile`）——字段对了但站点构建不出来，同样红
- **字段/归属**：`scripts/gates/check_docs.py` 判定四件事：
1. 每篇都有 front-matter；
2. 进站页面必须有 `title`；
3. 每篇归属明确：`parent` / `nav_exclude` / `has_children` / 站点首页 四选一；
4. `archive|adr|howto|internal|reports|decks` 下的页面必须 `nav_exclude`，
   且 `docs/` 根下的站外文档必须**被至少一篇其他文档引用**（防孤儿稿）。

注意：`docs/` 根下的站外文档**不等于过时**。`partner-onboarding`（对接表单）、
`proposal-stack-effects`（对外口径）、`reproducibility`（digest 记法）都被站内教程实质引用——
按日期归档会打断这些链接。判断依据是"有没有人引用"，不是"多久没改"。

---

## 七、发布与版本

- 版本号唯一真源：`registry.exam.protocol_version`（bump 条件写在 `protocol_version_rules`）
- 报告与榜单（含每条 entry）必须带该字段；`check_protocol.py` 判定，删字段即红
- 非 robotwin 考场的临时 smoke 标 `adhoc`（如实标注，不冒充版本化协议）
- 旧结果冻结，不覆盖；`git tag v<protocol_version>` 即发布

**物理目录分版（`docs/data/v<ver>/`）推迟到第一次真正发布时做**：现在 0 tag、0 release，
提前分目录只会让 19 份报告的所有引用重排一遍，收益为零。触发条件就是我们打第一个 tag。

# scripts/ 目录规则（就近文档，不进公开站点）

## 四类脚本，按**执行位置**分

| 目录 | 在哪跑 | 干什么 | 谁调 |
|---|---|---|---|
| `scripts/ci/` | V100 机器 | 派单编排：起容器、分片、出 aggregate | workflow |
| `scripts/data/` | GitHub runner | 产物加工：采集→报告→榜单→统计 | workflow / 手动 |
| `scripts/gates/` | CI | 门禁（yml/契约/registry/版本/报告/基础设施） | `run_all.py` |
| `scripts/model_servers/` | serve 镜像内 | ACT/DP 适配器 + 观测转换 | 镜像 |

## 门禁只有一个人口

```bash
python3 scripts/gates/run_all.py          # 全跑，输出一张表
python3 scripts/gates/run_all.py --only infra,contracts
python3 scripts/gates/run_all.py --list
```

新增门禁 → 加进 `run_all.py` 的 `GATES` 列表，不要另起 CI 步骤（步骤数会和门禁数脱钩）。

## 写脚本的三条约定

1. **路径映射只有一处**：宿主机↔容器的映射写在一个变量里，不要在两处各写一遍
   （2026-11-25 的 `output_dir` 双写事故就是这么来的）
2. **长跑必须留档**：`tee` 到文件 + 分阶段 `timeout`；禁止把整段长跑接 `| tail`
3. **断言读被测系统自己的字段**：例如"有没有报错"要读 aggregate 的 `num_errors`/`failure_reason`，
   不是自己以为的 `error` 键（曾因此把报错的一集判成 PASS）

## 推送纪律：重命名后取变更清单必须 `--no-renames`

```bash
git show --name-only --no-renames HEAD        # ✅ 重命名会同时列出旧路径与新增路径
git show --name-only HEAD                     # ❌ 重命名只输出新路径 → 旧路径的删除被漏掉
```

**真实事故（2026-11-25，PR #23 → #24）**：`git mv docs/internal/x.md docs/howto/x.md` 后，
用 `git show --name-only` 生成推送清单，结果只推送了新增的 `docs/howto/x.md`，
旧路径的删除没进 commit —— main 上同时存在新旧两份，`docs/internal/` 404 不掉，
只能再开一个 PR 补删。

**判据**：任何"按文件清单推送"的自动化（API 建 tree、批量 scp、rsync），
都必须用 `--no-renames`，或在推送后核对"旧路径是否真的消失"。

## 配置的唯一真源

- 考场/task/协议/镜像 digest → `configs/registry/model-registry.json`（经 `scripts/data/bench_config.py` 读）
- 版本号 → `registry.exam.protocol_version`
- 禁止在 shell / workflow 里硬编码 task 清单（门禁 `check_contracts.py` 会拦）

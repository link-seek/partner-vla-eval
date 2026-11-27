---
title: ADR-0004 双考场评测运行时与 episode 级增量归档
status: Proposed
date: 2026-11-27
nav_exclude: true
---

## 背景

当前评测编排把模型、考场、资源与归档策略绑在具体脚本中：

- `ci_model_matrix.sh` 直接调用 `ci_robotwin_full.sh`；
- LIBERO 另有 `ci_libero.sh`，serve、端口、GPU、结果目录各自硬编码；
- `model-matrix.yml` 在整个 matrix 跑完后才上传 GitHub artifact 与 OBS；
- `post-run-collect.yml` 再把这些产物拉回来生成报告。

这带来两个已经确认的问题：

1. **扩展性**：RoboTwin 与 LIBERO 都需要接入，继续复制 workflow / shell 会放大维护面。
2. **数据安全**：task 中途失败时，已完成的 episode 只在本机 `results/`，可能随机器故障丢失；`resume=1` 依赖本机文件，不是持久断点。

目标不是重写 VLA Evaluation Harness，而是在其评测内核之上建立统一的：

- BenchmarkAdapter（RoboTwin / LIBERO / 后续考场）
- RuntimeProfile（Docker / ECS / K8s，SAPIEN / MuJoCo 运行要求）
- CheckpointCoordinator + ArtifactSink（episode 级增量归档）
- RunManifest（完成定义、断点恢复、partial 判定）

---

## 开源社区做法（查证结论）

### 1. VLA Evaluation Harness：已经有 episode 级原子记录与恢复语义

上游 `src/vla_eval/recording.py`：

- 每个 evaluation 一个 SQLite：`recording-<eval_id>.sqlite`；
- `PRAGMA journal_mode=DELETE`、`synchronous=EXTRA`；
- `EpisodeRecorder.close()` 在一个事务里同时 upsert step rows 与 episode result；
- episode status 为 `success / fail / error / skipped`；
- work queue 支持 shard claim、unfinished item 恢复；
- export 从一致快照生成 episode JSONL 与 aggregate；
- 同一 task/episode 取最后一次 committed attempt；
- shard completion 保留 partial-run 状态；
- episode 级失败隔离，单集崩溃不中止整个评测。

**缺口**：记录与导出是本地的，没有远程 `ArtifactSink`。我们的工作应该是补持久化边界，不是再写一套 recorder。

证据：

- https://github.com/allenai/vla-evaluation-harness/blob/main/src/vla_eval/recording.py
- https://github.com/allenai/vla-evaluation-harness/blob/main/src/vla_eval/results/export.py
- https://github.com/allenai/vla-evaluation-harness/blob/main/docs/architecture.md#result-collection

### 2. LeRobot：按 episode 批量上传，支持恢复

`lerobot-rollout` 的 Sentry strategy：

- `--strategy.upload_every_n_episodes=5`：每 N 个 episode 推送到 Hub；
- 提供 `--resume` 恢复已有 recording session；
- Episodic strategy 以 episode 为记录单元；
- strategy 通过 config registry + subclass 扩展，核心 rollout 引擎不认识具体 strategy。

这证明两件事：**episode 是天然的 checkpoint 边界；策略插件化是 robotics 开源社区的成熟做法。**

证据：

- https://github.com/huggingface/lerobot/blob/main/docs/source/inference.mdx
- https://huggingface.co/docs/lerobot/en/api/datasets

### 3. ManiSkill：episode / 时间片 flush

`RecordEpisode`：

- 单环境在 episode reset 时保存轨迹与视频；
- 向量环境按 `max_steps_per_video` flush，避免无限缓冲；
- 轨迹 HDF5 + JSON metadata。

证据：

- https://maniskill.readthedocs.io/en/latest/user_guide/wrappers/record.html

### 4. Ray Train：本地 staging → 持久化 → committed / validated → 恢复

Ray Train 的 checkpoint 生命周期：

1. 先写本地临时目录；
2. `train.report(metrics, checkpoint=...)` 上传到持久存储；
3. 提供 `COMMITTED` / `VALIDATED` 一致性模式；
4. worker / node 失败后读取最新已报告 checkpoint 恢复；
5. 支持同步或异步上传，异步必须等上传完成才能删除本地目录。

这是本 ADR 最直接参考的持久化语义：**未 committed 的本地数据不算完成；恢复只认持久化 checkpoint。**

证据：

- https://docs.ray.io/en/latest/train/user-guides/checkpoints.html
- https://docs.ray.io/en/latest/train/user-guides/persistent-storage.html
- https://docs.ray.io/en/latest/train/user-guides/fault-tolerance.html

### 5. Metaflow：step 边界 + 长任务 in-task checkpoint

Metaflow：

- task 完成时把 artifacts 写入 datastore，resume 可跳过已完成 step；
- 对长任务明确建议在 task 执行期间周期性 checkpoint，否则失败会丢数小时工作；
- `@checkpoint` 自动按 task / branch 管理 checkpoint 目录与最新引用。

证据：

- https://docs.metaflow.org/scaling/checkpoint/introduction

### 6. Argo Workflows / Dagster：artifact 是一等公民

- Argo：step input/output artifacts 写入 artifact repository，可按 workflow / artifact 设 GC；
- Dagster：asset materialization + IO manager + retry policy，数据在 op 之间通过 IO manager 持久化。

共同点：**工作流引擎负责调度，持久化层负责“完成”的证据，报告只是派生视图。**

证据：

- https://argo-workflows.readthedocs.io/en/latest/walk-through/artifacts/
- https://docs.dagster.io/concepts/assets/software-defined-assets
- https://docs.dagster.io/guides/build/ops/op-retries

### 7. MLflow / W&B：run-scoped artifact 与版本化

- MLflow：artifact 绑定 run，`log_artifact(s)` 在 run 执行期间持续写入 artifact store；
- W&B：checkpoint 可作为 artifact version，内容 checksum，多个 checkpoint 形成历史与 `latest` 别名。

证据：

- https://mlflow.org/docs/latest/self-hosting/architecture/artifact-store
- https://docs.wandb.ai/guides/artifacts/model-versioning

---

## 选项

| 方案 | 优点 | 代价 | 结论 |
|---|---|---|---|
| A. 继续各 workflow 跑完后上传 | 改动最少 | 中途失败丢数据；LIBERO 再复制一套 | 拒绝 |
| B. 给现有 RoboTwin 单独加 watchdog 上传 | 能先救 RoboTwin | LIBERO 再写一个；归档逻辑仍分散 | 拒绝 |
| C. 统一 CheckpointCoordinator + BenchmarkAdapter | 两个考场共用；恢复语义一致；可扩资源 | 需要抽接口与迁移现有脚本 | **采用** |
| D. 直接引入 Argo / Metaflow / Ray 作为编排内核 | 生态成熟 | 对当前 GitHub Actions + 单机双卡过重；迁移风险大 | 暂不采用，借用其设计语义 |

---

## 决定

采用 C：**保留 VLA Evaluation Harness 作为评测内核，在其上增加统一运行时；归档属于评测完成定义，Post-run Collect 降级为派生层。**

### 1. 统一分层

```text
EvalJobSpec（模型 / 考场 / 协议 / 资源 / sink）
        ↓
GenericEvaluator
        ↓
BenchmarkAdapter
  ├── RoboTwinAdapter
  └── LiberoAdapter
        ↓
Harness EpisodeRunner + RecordingStore（上游）
        ↓
CheckpointCoordinator
        ↓
ArtifactSink（OBS / S3 / 本地持久盘 / GitHub artifact 镜像）
        ↓
RunManifest
        ↓
ReportProjector（aggregate / 报告 / 榜单）
```

### 2. BenchmarkAdapter 契约

```python
class BenchmarkAdapter(Protocol):
    name: str

    def tasks(self, suite: str) -> list[TaskSpec]: ...
    def resource_profile(self) -> ResourceRequest: ...
    def model_profile(self, model: ModelSpec) -> ModelProfile: ...
    def run(self, ctx: EvalContext) -> Iterator[EpisodeRecord]: ...
    def finalize(self) -> RunFinalization: ...
```

RoboTwin 与 LIBERO 只负责“怎么跑、怎么判”，不负责“怎么归档”。

### 3. 统一 EpisodeRecord

```json
{
  "run_id": "...",
  "benchmark": "robotwin",
  "protocol_version": "robotwin-2.0.1",
  "model": {"key": "...", "weight_revision": "...", "serve_image_digest": "..."},
  "task": "...",
  "task_idx": 0,
  "episode_id": 0,
  "attempt": 1,
  "status": "success",
  "metrics": {},
  "steps": 0,
  "elapsed_sec": 0.0,
  "failure_reason": null,
  "raw_ref": "checkpoints/shard-0/seq-000001/episode.jsonl",
  "raw_sha256": "...",
  "video_ref": null
}
```

### 4. CheckpointCoordinator 语义

- **输入**：harness 已 committed 的 episode（SQLite transaction 完成后）。
- **本地 spool**：优先直接消费上游 SQLite / JSONL，不重复实现 recorder。
- **上传**：episode 元数据逐集上传；视频异步上传并单独跟踪状态。
- **快照**：每个 task 结束或每 N 集做一次 SQLite 一致性快照。
- **一致性**：对象写入后 read-back / checksum 校验，才算 `COMMITTED`。
- **并发**：每个 shard 写独立不可变 journal；单个 projector 合并成 run manifest，避免多写者争抢。
- **重试**：at-least-once + 幂等键；重复上传同 checksum 视为成功。
- **恢复**：从持久化 journals 重建“已完成 episode 集合”，不依赖本机 `results/`。

幂等键：

```text
(run_id, benchmark, task_idx, episode_id, attempt)
```

同一 episode 重跑生成新 attempt；manifest 按“最后一次 committed attempt 生效”，与上游 export 语义一致。

### 5. RunManifest 状态

```text
PENDING
  → RUNNING
      → COMPLETED       全部目标 episode committed，final aggregate 已验证
      → INCOMPLETE      部分 episode committed，但目标未完成 / 进程中断
      → FAILED          启动或基础设施失败，可能没有 episode
```

规则：

- `INCOMPLETE` 允许生成 partial 报告，但按 ADR-0002 只进附录，不进正式榜；
- `COMPLETED` 必须有 final manifest 与 aggregate；
- GitHub artifact 只是镜像，不是唯一真源；
- OBS / 对象存储是主真源，manifest 与原始 episode 永久保留。

### 6. 目录布局

```text
<artifact_root>/<run_id>/
  job.json
  journals/
    shard-000.jsonl
    shard-001.jsonl
  checkpoints/
    shard-000/
      seq-000001/
        episode-000000.jsonl
        episode-000000.meta.json
        recording.snapshot.sqlite      # task 级或周期快照
  final/
    manifest.json
    aggregate.json
    recording.sqlite
    COMPLETED
```

所有 checkpoint 对象不可变；不在同一 key 上覆盖。

### 7. Post-run Collect 的新职责

只允许：

```text
manifest + committed episodes
  → aggregate
  → partial / final 报告
  → 榜单投影
```

不允许：

- 从 OBS “抢救”未归档数据；
- 补写 episode 完成状态；
- 把本机 `results/` 当恢复真源；
- 在 manifest 不完整时生成正式榜。

---

## 迁移步骤

### 阶段 0：冻结行为

- 固定 RoboTwin smoke 与 50ep 用例；
- 记录 aggregate、episode 顺序、error 分类；
- 作为后续重构的 golden tests。

### 阶段 1：抽 BenchmarkAdapter

- 现有 `ci_robotwin_full.sh` 原样包装为 RoboTwinAdapter；
- 现有 `ci_libero.sh` 包装为 LiberoAdapter；
- 两者只暴露统一 `run() -> EpisodeRecord`。

### 阶段 2：抽 GenericEvaluator

- 负责模型 serve、benchmark 选择、episode 循环、结果收集；
- 不再直接调用 `ci_robotwin_full.sh`；
- 不包含 OBS、ECS、端口 8000 等具体实现。

### 阶段 3：接 CheckpointCoordinator

- 优先使用上游 SQLite committed rows + `export_db` 一致快照；
- 若上游增加 `on_episode_committed` hook，则改为直接事件消费；
- 先实现 OBS sink，GitHub artifact 作为镜像。

### 阶段 4：拆配置真源

```text
models.json       ModelSpec + weight / image / benchmark profiles
benchmarks.json   BenchSpec + protocol / suite / backend
runtimes.json     RuntimeProfile + runner / GPU / port / mounts
sinks.json        ArtifactSink 配置
```

现有 `model-registry.json` 中考场与运行时分段迁移，不一次性重写。

### 阶段 5：收口 workflow

- 6 条评测执行 workflow 收敛为 1 条 Generic Eval Workflow；
- workflow 只接收 EvalJobSpec；
- `post-run-collect` 只做 ReportProjector；
- 电源、构建、CI、治理保持独立。

---

## 验收标准

1. 在 RoboTwin 跑到第 12 集时强杀进程，前 11 集仍可从 OBS manifest 恢复。
2. 换一台机器 resume，只跑未 committed episode，不重复已完成集。
3. LIBERO 接入不需要修改 GenericEvaluator 或 CheckpointCoordinator。
4. 第二台机器只需要增加 RuntimeProfile，不需要改 BenchmarkAdapter。
5. 同一 episode 重复上传不会产生重复记录；重跑 attempt 只保留最后一次 committed。
6. Post-run Collect 在原始数据缺失时必须失败，不能生成正式榜。
7. RoboTwin 重构前后 golden aggregate 一致。
8. partial 仍遵守 ADR-0002：只进附录，不进正式榜。

---

## 后果

### 好处

- RoboTwin / LIBERO 共用一套完成、归档、恢复与报告语义；
- 中途失败不丢已提交数据；
- 新考场不再复制 workflow；
- 新模型主要是 ModelSpec + serve profile；
- 报告可重算，原始证据不可变；
- 与上游 harness 的 SQLite / export / resume 能力对齐。

### 代价

- 需要抽接口与迁移现有脚本；
- 每个 episode 增加一次小对象上传与校验；
- manifest / journal 合并需要单写者或确定性合并；
- 视频上传需要独立状态机；
- 短期 RoboTwin 流程会多一个 checkpoint 组件。

### 触发重议

- 若上游 harness 提供稳定的 episode commit hook 与远程 sink，则本仓 CheckpointCoordinator 应改为薄适配；
- 若对象存储成本显著上升，先调整视频与 SQLite 快照频率，不削弱 episode 元数据归档；
- 若引入 K8s / Argo，GenericEvaluator 与 ArtifactSink 保持不变，只替换 Executor。

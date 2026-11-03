# 03 harness 本体

> 版本：v1.1（2026-10-27）。serve/bench 全系 `v0.8.0`（10-23 对齐，HARNESS_REF 同值；
> 唯一真源见 `docker/versions.yaml`，lint 门禁漂移）。

## 三件套

- **serve**：`vla-eval serve -c <serve.yaml>`，把权重变成 WebSocket 服务。
  实现永远是 `uv run <script>`（PEP 723 header 自带依赖），离线跑必须预热 + `UV_OFFLINE=1`（见 05）。
- **benchmark**：`vla-eval run -c <run.yaml>`，在 Docker 里起环境跑 episode。
  常用覆盖：`--server-url`（换 serve 地址，不用改文件）、`--record-video`、`--shard-id/--num-shards`。
- **orchestrator**：读配置、建 benchmark + runner、管 episode、写 SQLite/JSON。
  `run_sharded.sh -n N` 起 N 分片共享一个 SQLite，跑完 `vla-eval export` 出 aggregate。

## 协议与口径机制

- 传输：WebSocket + msgpack；harness 不发明分数，只透传各榜原生规则再汇总（`mean_success`）。
- **spec 机制**：episode 起点自动比对观测/动作口径，mismatch 直接打 warning。
  看到 `Spec mismatch` 先别跑——必 0 分（X-VLA 就是这么发现的，见 08）。
- 集数口径：`episodes_per_task × test_num` 相乘！官方口径是 `test_num`
  （默认 100），我们全量用 `test_num=50 × episodes=1`。

## 版本跟随

- 全系钉 `v0.8.0`（serve/bench/CLI，10-23 对齐，无需兼容探针）。
- 上游发版先看 changelog 的 benchmark 修复项（#86/#87/#89 这类），再决定跟不跟。

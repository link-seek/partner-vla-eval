# 07 开跑与判分

> 版本：v1.0（2026-10-14）

## smoke（必经）

1 task×1ep（CALVIN 用 5 sequences），验证：镜像/权重/serve-up/口径/落盘。
先 smoke 后全量，省卡钱。录像常开（1ep 体积小，出 0 分时亲眼看）。

## 全量（分块战役）

- RobotWin：1 task×50ep/轮（CogACT 一头一 task），`test_num` 官方口径。
- 分片：2 分片（4 分片以上抢单卡会 hang，见 08），serve 独占卡0、分片放卡1。
- 超时：自托管上限 5 天，chunk 设 1440（别信 6 小时，那是公有 runner 的）。
- 耗时参考：单 ep 2~10 分钟，一轮 3~7 小时。

## 判分记分

- harness 不发明分数：各榜原生规则 + `mean_success` 透传，跨榜只并列不加权。
- error 分类记法：模型失败（判 0 分）/ 坏种子 `UnStableError`（单列，不怪模型）/ infra 异常（重跑）。
- 归档：aggregate JSON + SQLite 进 artifact 与 OBS（`eval/<榜>-*/`），Discussion 记结论。

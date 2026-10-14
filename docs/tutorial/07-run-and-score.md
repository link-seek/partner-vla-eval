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

## 分数怎么读（92% 到底在说什么）

- `mean_success` = 成功 ep 数 / 总 ep 数。**二值分**：一个 ep 要么整单完成（1），
  要么 0，没有“完成一半给 0.5”。400 步没做出来和第一步就崩，都记 0。
- 和官称差多少算正常：±5pp 以内算对上（噪声+种子集差异）；
  差 10pp 以上先查口径（08 第 1 条），不要先怀疑模型。
- `error` ≠ `fail`：`fail` 是模型没做出来；`error` 是 infra/坏种子抛异常，
  不怪模型，单列。看分先看 errors，再看 mean。
- 跨榜不比大小：LIBERO 99% 和 RobotWin 16% 没有可比性，各榜难度和判分标尺不同，
  只并列展示（我们在总表里就是这么列的）。

## 判分记分

- harness 不发明分数：各榜原生规则 + `mean_success` 透传，跨榜只并列不加权。
- error 分类记法：模型失败（判 0 分）/ 坏种子 `UnStableError`（单列，不怪模型）/ infra 异常（重跑）。
- 归档：aggregate JSON + SQLite 进 artifact 与 OBS（`eval/<榜>-*/`），Discussion 记结论。

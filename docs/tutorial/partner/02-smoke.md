# 伙伴 02：smoke（1 天内，通/不通）

> 目标：拿到 spec 对齐报告，确认链路绿。
> 时间：0.5~2 小时（含排队） ｜ 前置：`01` 对接帖通过 ｜ 你将得到：通/不通 + spec 对齐报告。
> 读法：本篇你是等结果的人，操作只有"看懂报告"；原理讲报告里每行是什么意思。

## 操作：我们跑，你看报告

我们按你的表单起 serve，跑 1 个 task×1ep：RobotWin 跑 grab_roller，
LIBERO 跑 spatial（只在分不清链路/模型问题时加跑，便宜对照），
CALVIN 跑 5 sequences。录像常开（1ep 体积小，出 0 分时亲眼看）。

输出就两样：**通/不通 + spec 对齐报告**。名字会骗人，实测不会——
口径不对这里打回，不烧大钱，通过后才进全量排期。

## 操作：报告三行怎么读

1. `serve UP` + `smoke_exit=0`：serve 起来了，链路通了。
2. 日志头 20 行无 `Spec mismatch`：口径对上了。可以烧卡。
3. 有 `Spec mismatch`：看它是 advisory 还是真拦路（下）。

> **原理·warning 分级**：`action [ee_pose]: benchmark expects it but server
> doesn't declare it` 只是 advisory——动作实测照通（X-VLA EE 已验证），400 步
> 可照常；真拦路的是 unknown kwarg 类错误（旧镜像，已退役）和维度/相机/
> chunk 错配。分级依据是上游合入的 #168 实测矩阵（6ep 全跑满 400 步零 ERROR），
> 不是猜的。详见 09 社区协作。
> **原理·为什么 smoke 能省钱**：smoke 与全量是同一套配置，只有 `test_num`
> 不同（1 vs 50）+ smoke 跳专家校验。smoke 绿 = 口径、权重、serve、落盘四个
> 变量一次对齐；全量只是加集数，不引入新变量。反过来，跳过 smoke 直接全量，
> 口径错了就是 50ep 的卡钱打水漂（单 ep 2~10 分钟，一轮 3~7 小时）。

## 检查点：不通的三种死法

| 现象 | 根因 | 下一步 |
|---|---|---|
| serve 起不来（`HFValidationError` / 401） | 路径三段式 / 权重无权限 | 回 01 补确切 commit + 开授权 |
| 全 0 分但零异常 | 口径错（EE 当关节喂等） | 按 06 口径映射表改 serve yaml，重跑 smoke |
| 0/30 全 ERROR 但 exit 0 | error 当数据（B 的教训） | 先看 errors 列，infra/坏种子问题单列重跑 |

完整 15 条见 `08-troubleshooting.md`（将迁入 `reference/error-codes.md`）。

## 下一步

通过 → 进 V100 队列等全量（`03-full-and-report.md`，按 task 数排期，串行）。

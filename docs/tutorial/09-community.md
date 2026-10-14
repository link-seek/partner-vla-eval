# 09 社区协作

> 版本：v1.0（2026-10-14）

## 已提 issue

- [#166](https://github.com/allenai/vla-evaluation-harness/issues/166)：
  RobotWin 写死 qpos，EE 模型必 0 分。含 spec 实测 + 0% vs 70% + `action_type` 参数化方案。
  PR 等战役收尾、GPU 空出再做（需 smoke 验证）。

## 上游跟随纪律

1. 发版先看 changelog 的 benchmark 修复项（如 #86 种子随包、#87 warp 钉版、#89 渲染优化）。
2. 小步探针：2ep 验证协议兼容，再切默认（0.7.0→0.8.0 就是这么切的）。
3. 缺的口径先记债（X-VLA EE、46 个缺头 task），不堵主战役。

## 回馈

第一个验证人的数据（RobotWin 全量）整理好可 PR 回上游，榜单留名。

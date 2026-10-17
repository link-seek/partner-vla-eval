# 两天战役巡检（无人值守触发器）

## 为什么有这个文件

opencode 会话结束 = 后台 watcher 全死，无人能叫醒 agent。
本文件让**任意新会话 / 宿主机 cron** 零上下文接管：状态全在 #1/#3 帖，
本文件只给检查清单和推进规则。

## 宿主机 cron（示例，每 30 分钟）

```
*/30 * * * * cd /workspace && opencode run --prompt-file work/partner-vla-eval/docs/two-day-patrol.md >> /var/log/vla-patrol.log 2>&1
```

## 巡检清单（按序，每轮必做）

1. `gh run list --repo link-seek/partner-vla-eval --limit 8`：记下所有
   in_progress / pending / completed（结论 success/failure/cancelled）。
2. 对每个刚 completed 的 GPU run：`gh run view <id> --log-failed` 定位；
   验收类（pi0-robotwin-full）去 artifact/OBS 取分数，对基线（grab_roller 46/50，
   ±8pp 即过）。
3. 对 failure：修（能修的当场修：改脚本/workflow → 推 main → 记 #1 帖）；
   修不了：记 #1 帖说明 + 发邮件（`send-mail "" "VLA战役受阻" "<现象+日志链接>"`）。
4. 推进队列（严格串行，同 `gpu-ecs-pi0-smoke` 组，一次只 dispatch 一个，
   等 completed 再发下一个——pending 会被新 dispatch 挤掉，已验证 3 次）：
   验收 grab_roller×50 → libero smoke 0.8.0 → calvin smoke 0.8.0 →
   切 tag 收尾（ci_smoke/ci_calvin/compose libero+calvin→0.8.0）→
   20ep 烘焙对照（`pi0-robotwin-full` tasks=grab_roller episodes=20 shards=2
   + assets_mount 外置）→ 还债实装（serve-smolvla 镜像好后 spatial 1×1）→
   gap 深查（换种子块 place_empty_cup×50）→ 瘦身等价验（slim 镜像好后 ×50）→
   PR 验证（X-VLA EE smoke，转正 #168）。
5. 免费机线（与 GPU 并行，不占卡）：slim 构建、serve 镜像构建挂了就修
   workflow 重发（参考 38730733038 上下文教训）。
6. 每轮结束：`#1` 帖记一条过程（现象+根因+修法/分数），教程直接可用。

## 当前基线（2026-10-15 12:00 UTC）

- main 已含：钉死 0.8.0（99b90be）、libero/calvin 参数化（30f4802）、
  slim Dockerfile+构建流、serve-smolvla。
- 上游 draft PR：allenai/vla-evaluation-harness#168。
- 决策总账：Discussion #3（含第 2 件作废）。

## 铁律：一切验证必须流水线可复现

- GPU/构建实验：只许 workflow_dispatch，不许手跑；结论必须带 run id。
- 只读查询（HF/arXiv/上游文件）：贴完整命令，他人同命令可复现。
- 例外零容忍：没有 run id 或命令的结论不记帖。

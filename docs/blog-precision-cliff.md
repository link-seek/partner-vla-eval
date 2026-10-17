# 一个 fp16 把 97% 的分数干到 0%：VLA 评测里的精度断崖

*X-VLA × LIBERO × V100：29/30（fp32）vs 0/30（fp16）。不是判负，是首个推理就在算子层炸掉。*

## 起因

给 VLA 榜单做栈差异对照：同一套代码，只换精度。预期是差几个点，实际 fp16 一分不得。

## 报错

```
RuntimeError: Input type (float) and bias type (c10::Half) should be the same
```

每个 episode 死在第一个 action。去噪头的 LayerNorm/大激活值在 fp16（5 位指数）下直接溢出——X-VLA 官方训练命令是 `accelerate --mixed_precision bf16`，fp16 推理属于数值越界，不是性能降级。

## 三个反直觉的点

1. **0/30 全是 ERROR 不是 FAIL**：vla-eval 把 error 当数据，exit code 照样 0。看分不看日志会误判。
2. **同卡 fp32 29/30，pi0 fp32 照跑**：坏的是 X-VLA 的 fp16 路径，不是卡不是 benchmark。
3. **CogACT fp32 在 V100 上连加载都过不了**（28GB 权重）：精度故事的另一面是显存墙，双卡分片能加载，但 custom forward 的裸 cat 让推理过不去——另文再表。

## 教训

- 跑分先报栈：GPU / dtype / 镜像 digest / 种子 / 分片，缺一个都别比。
- fp16 不是 fp32 的廉价版：指数位少 3 位，范围差 4 个数量级，训的时候没见过的数值，推理时一个都躲不掉。
- 完整对照表、镜像（公开可拉）、讨论过程见本仓 docs/ 与 Discussion #1。

*（原 workshop 短文计划取消，内容并入可复现评测系统一文；本篇为技术记录。）*

---
title: 伙伴 01：配准交付
parent: 评测教程
nav_order: 3
---

# 伙伴 01：认模型，对号入座，配准交付

> 目标：把你训好的模型配准成可上榜形态（不教训模型，只教交模型），
> 产出一份 harness 能直接吃掉的 serve yaml。
> 时间：30 分钟 ｜ 前置：读完 `quickstart`。
> 你将得到：路线归位 + serve yaml + 提交包（权重版本 + ★项 + 表单）。

harness 把官方原生要写的（约 200 行适配器 + 两个 env + 十几个参数）收拢成两个 yaml。
**省的是实现，不省的是口径**：`ckpt_setting`（训的哪份数据）vs `task_config`
（测的什么环境）在官方命令行里本来就是两个独立参数。
下文六节与上游 [CONTRIBUTING（Adding a Model Server）](https://github.com/allenai/vla-evaluation-harness/blob/main/CONTRIBUTING.md#adding-a-model-server) 1:1 对照：节号即上游节号，缺的是代码实现，留的是填表动作。卡住时拿着节号去上游问。

先把模板和表单源文件拿下来（后面照着改、对着填）：

```bash
git clone https://github.com/link-seek/partner-vla-eval.git
cd partner-vla-eval
```

### §1 定范围：按模型类型找你的路线，定完再往下读。


### §2 备权重：权重按"Hub ID 或本地路径 + 精确版本"交，OBS 地址另算我方补充。


### §3 对口径：照你的路线表填★项（官方字段全集的子集），其余抄默认。


### §4 状态并发：缺省，有特殊走 `policy_kwargs` 写表单备注。

### §5 校验交接：有 GPU 先 `test -c`，然后联系 xieyucheng 交三样。


---
title: 伙伴接入 · 真人计时测试包（30 分钟）
nav_exclude: true
status: living
---

# 伙伴接入 · 真人计时测试包

> 给**没接触过本仓**的同事/伙伴使用。目标不是“做对”，而是**如实记录哪里卡住、花了多久**。
> 预计 30 分钟；做得慢、做错、问问题都算有效数据，不要美化。

---

## 0. 前提（请先确认）

- [ ] 我从没看过 `link-seek/partner-vla-eval` 这个仓库
- [ ] 我不会去问写文档的人，除非完全无法继续（问了几次也要记下来）
- [ ] 我接受被计时

## 1. 你要做的事

只读下面三份公开文档 + 上游一份 yaml，产出两样东西：

1. 一个改好的 X-VLA / RoboTwin serve yaml（照文档改★）
2. 一份填好的对接表单

文档（只读这些，不要浏览本地仓库）：

- https://raw.githubusercontent.com/link-seek/partner-vla-eval/main/docs/tutorial/partner/01-serve-yaml.md
- https://raw.githubusercontent.com/link-seek/partner-vla-eval/main/docs/partner-onboarding.md
- https://raw.githubusercontent.com/link-seek/partner-vla-eval/main/docs/tutorial/partner/02-full-and-report.md
- 上游参考 yaml：
  https://raw.githubusercontent.com/allenai/vla-evaluation-harness/main/configs/model_servers/xvla/robotwin.yaml

## 2. 怎么计时（照抄即可）

每个阶段开始/结束各跑一次：

```bash
date -u +%s
```

把秒数填进下表；总时长 = 最后结束 − 最开始开始。

| 阶段 | 开始秒 | 结束秒 | 分钟 |
|---|---|---|---|
| 读 01-serve-yaml | | | |
| 读对接表单 | | | |
| 读 02-full-and-report | | | |
| 看上游 yaml + 对照 | | | |
| 改 serve yaml | | | |
| 填表单 | | | |
| 提交前自检 | | | |
| **总计** | | | |

## 3. 必须记录的四个数

1. **总时长**（打开文档 → 交出 yaml）
2. **最久的一节**（上表里分钟数最大的）
3. **卡住次数**：每次写一句“卡在哪、文档原文怎么说、你怎么解决（猜的标‘猜’）”
4. **提问次数**：问了谁、问了什么

## 4. 交付物

- `xvla-robotwin.yaml`（改好的）
- 填好的表单（不知道的空着）
- 上面两张表 + 卡点/提问清单

交回给：xieyucheng（直接发文件/粘贴均可）。

## 5. 不需要做的事

- 不需要跑评测、不需要 GPU
- 不需要克隆仓库
- 不需要把 yaml 放对位置（交给我们放）
- 不需要 `_base.yaml`

## 6. 组织者用（测试者不用看）

收到结果后，把四项指标填进 `docs/howto/partner-onboarding-timing.md` 第六节，并把“文档声称/AI 走查”替换为真人实测数字。

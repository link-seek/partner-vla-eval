# 08 排障手册

> 版本：v1.0（2026-10-14）。一句话现象 + 一行解法，详见 Discussion #1 评论。

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| 1 | 全 0 分但零异常 | 口径错（EE 当关节喂） | 看 spec warning，按 06 对表；X-VLA 见 issue #166 |
| 2 | `HFValidationError: repo/subdir` | `from_pretrained` 不认三段式 | snapshot 后用本地子目录绝对路径 |
| 3 | Xet 401 | 权重走 Xet，mirror 直连要 token | 预热传 token + `HF_HUB_DISABLE_XET=1` |
| 4 | bf16 vs Half 混 | V100 无 bf16，tower 是 fp16 | 全链 fp16（V100 限定） |
| 5 | SWR 登录失败 | 密码是 HMAC-SHA256(AK)，不是 SK 明文 | 照 so101 的登法抄 |
| 6 | runner 不上线 | 离线超期被回收注册 | `repair-v100.yml`（token 现开用完删） |
| 7 | `.cache` Permission denied | docker -v 把宿主目录建成 root | 预建目录+改属主（脚本里已有） |
| 8 | 分片 watchdog 全杀 | 多 SAPIEN 上下文抢单卡 | 降 2 分片，serve 独占卡0、分片放卡1 |
| 9 | hub CLI 改名 | v1 只有 `hf`，0.x 无 `--version` | 镜像里钉别名 `hf-download`，脚本只认它 |
| 10 | checkout 超时 | 已根治：V100 job 无 checkout（payload 镜像 SWR 拉） | 失败先看 payload tag 是否过期 |
| 11 | 集数翻倍 | `episodes_per_task × test_num` 相乘 | 集数走 `test_num`，前者固定 1 |
| 12 | 6h 被杀 | 自设 360 帽，实际自托管 5 天 | chunk 提到 1440 |
| 13 | 坏种子 error | 场景物理不稳定 | 0.8.0 开校验走自带种子；0.7.0 单列 error |
| 14 | 镜像 28GB 传不动 | 免费机磁盘/跨洋慢 | skopeo 直拷（不落盘）+ SWR 内网拉 |
| 15 | 行内 python 必崩 | 引号三层绣花 | CLI 能办的不写代码；逻辑进独立文件 |

## 原则

bash 只编排，逻辑进文件；先 smoke 后全量；先看 warning 再烧卡。

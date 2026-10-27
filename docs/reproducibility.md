# 可复现清单（镜像）

## 现状：对内一条 pull 即可，对外还不行

所有镜像进 `swr.cn-north-4.myhuaweicloud.com/link-seek`（**私仓**，需 AK/SK 派生登录），
Dockerfile + 构建 workflow 全在 git（`docker/` + `.github/workflows/build-*.yml`），
tag 钉死、可重打。读论文的人匿名可拉：`ghcr.io/link-seek/<上表名>:\<tag>`（SWR→GHCR mirror 全量 success，包 visibility=public 已验）。

## 镜像表

| 用途 | SWR tag | 来源/Dockerfile | 备注 |
|---|---|---|---|
| benchmark LIBERO | vla-eval-libero:0.8.0 | skopeo 直拷上游 ghcr（bit-identical） | sync-images.yml |
| benchmark CALVIN | vla-eval-calvin:0.8.0 | 同上 | 同上 |
| benchmark RobotWin（回滚位） | vla-eval-robotwin:0.8.0 | skopeo 直拷上游 ghcr（bit-identical） | 不跑生产，只回滚 |
| benchmark RobotWin（统一生产） | vla-eval-robotwin:0.8.0-ee-slim | docker/Dockerfile.robotwin-unified（slim 三刀 + EE 烘进 + P2 烘进，arch=7.0） | 4→1 收官；qpos 默认，ee 走 action_type |
| serve CogACT | vla-serve-cogact:0.7.0 | docker/Dockerfile.serve-cogact（torch2.6.0cu126，tf 4.46.3） | 双臂关节口径 |
| serve pi05 | vla-serve-pi05:0.7.0 | docker/Dockerfile.serve-pi05 | LIBERO 单臂 |
| serve X-VLA fp32/fp16 | vla-serve-xvla[:]0.7.0 / vla-serve-xvla-fp16:0.7.0 | docker/Dockerfile.serve-xvla（DTYPE 构建参） | 精度对照组 |
| serve SmolVLA | vla-serve-smolvla:0.8.0 | docker/Dockerfile.serve-smolvla（lerobot 0.6.1 + tf v5） | 还债 |
| serve pi0 | vla-serve-pi0:0.8.0 | docker/Dockerfile.serve-pi0（lerobot 0.6.1） | 还债 |
| 通用底座 | vla-verify:0.1 | docker/Dockerfile.verify | 预热/下载工具 |

权重不在镜像里：OBS 标准桶（V100 内网拖）+ HF mirror 直下，serve 启动时挂载。

## 对外可复现还缺

1. ~~公开镜像~~ ✅ 已公开（mirror-swr-ghcr.yml 全量 success，11 包 public）。
2. digest 锁定：上表补每 tag 的 sha256（SWR 控制台抄），论文里贴 digest 不贴 tag。
3. 第三方权重：Dexmal/*、2toINF/*、lerobot/* 全是公开 Hub 仓，可直接引用； gated 权重没有。

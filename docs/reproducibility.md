# 可复现清单（镜像）

## 现状：对内一条 pull 即可，对外还不行

所有镜像进 `swr.cn-north-4.myhuaweicloud.com/link-seek`（**私仓**，需 AK/SK 派生登录），
Dockerfile + 构建 workflow 全在 git（`docker/` + `.github/workflows/build-*.yml`），
tag 钉死、可重打。读论文的人**有权限**可直接拉；**没权限**拉不到——公开发布待决策。

## 镜像表

| 用途 | SWR tag | 来源/Dockerfile | 备注 |
|---|---|---|---|
| benchmark LIBERO | vla-eval-libero:0.8.0 | skopeo 直拷上游 ghcr（bit-identical） | sync-images.yml |
| benchmark CALVIN | vla-eval-calvin:0.8.0 | 同上 | 同上 |
| benchmark RobotWin | vla-eval-robotwin:0.8.0 | 同上（ROBOTWIN_REF=c3ddfa8，CUROBO v0.7.8，nvcc 12.6） | 同上 |
| benchmark RobotWin slim | vla-eval-robotwin:slim-0.8.0 | docker/Dockerfile.robotwin-slim（去资产/nvcc/清源码，arch=7.0） | 11.3GB；50ep 等价 46/50 |
| benchmark RobotWin EE | vla-eval-robotwin:ee-0.8.0 | slim? 不——stock 0.8.0 + robotwin-ee.patch | PR#168 验证用 |
| serve CogACT | vla-serve-cogact:0.7.0 | docker/Dockerfile.serve-cogact（torch2.6.0cu126，tf 4.46.3） | 双臂关节口径 |
| serve pi05 | vla-serve-pi05:0.7.0 | docker/Dockerfile.serve-pi05 | LIBERO 单臂 |
| serve X-VLA fp32/fp16 | vla-serve-xvla[:]0.7.0 / vla-serve-xvla-fp16:0.7.0 | docker/Dockerfile.serve-xvla（DTYPE 构建参） | 精度对照组 |
| serve SmolVLA | vla-serve-smolvla:0.8.0 | docker/Dockerfile.serve-smolvla（lerobot 0.6.1 + tf v5） | 还债 |
| serve pi0 | vla-serve-pi0:0.8.0 | docker/Dockerfile.serve-pi0（lerobot 0.6.1） | 还债 |
| 通用底座 | vla-verify:0.1 | docker/Dockerfile.verify | 预热/下载工具 |

权重不在镜像里：OBS 标准桶（V100 内网拖）+ HF mirror 直下，serve 启动时挂载。

## 对外可复现还缺（待决策）

1. 公开镜像：私仓 → ghcr.io 公开（或 worv-ai 同款匿名 fallback）。镜像内无密钥，可公开；费的是公网推流时间。
2. digest 锁定：上表补每 tag 的 sha256（SWR 控制台抄），论文里贴 digest 不贴 tag。
3. 第三方权重：Dexmal/*、2toINF/*、lerobot/* 全是公开 Hub 仓，可直接引用； gated 权重没有。

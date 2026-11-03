# 04 机器与网络

> 版本：v1.0（2026-10-14）

## 铁律

只有 GitHub 免费 runner 有完整外网，其余都是内网。**下载只能发生在有外网处。**
（组织新规：境外源优先走 url2hc 中转；但中转镜像 7 天老化，不适用于常驻镜像，见下。）

## 三机分工

| 机器 | 网络 | 只干 |
|---|---|---|
| GitHub 免费机 | 外网 | 打镜像→SWR；小文件/一次性下载 |
| hw21 常驻机 | 几乎内网 | V100 开关机（hcloud API 内网可达） |
| V100（`jushenzhineng-0002`，北京四，双32G） | 几乎内网 | 离线跑：SWR 内网拉镜像、mirror 拖权重、`UV_OFFLINE=1` |

## 铁律例外（实测结论）

- SWR 同步**不迁** url2hc：`img-to-swr` 给目标仓挂 7 天老化，战役镜像要常驻数周——属“中转不适用”，继续 skopeo 直拷。
- 权重不同步 OBS：15GB 以跨洋上传太慢（实测），走 mirror+token 直下 V100（国内源，已验证）。
- OBS 只收小结果（artifact 备份）。

## runner 生存

- V100 自托管 runner 离线超期会被 GitHub 回收注册，开机也连不回来。
  症状：开机后 runner 不上线。修法：安全组给跳板加 22/32 → 跳板 SSH → `svc uninstall` →
  runner 身份 `config remove` → 新 token 重配 → 重装 service。仓里 `repair-v100.yml` 即此流程。
- 开关机走 hw21 常驻机（V100 关着时也能叫醒），GPU job 串行（`concurrency: gpu-ecs-pi0-smoke`）。

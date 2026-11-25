#!/usr/bin/env python3
"""策略 profile：把「哪个策略、从哪导入、要哪些参数、怎么吐动作」变成数据。

为什么要有（2026-11-25）：
  适配器里 ACT / DP 的差异原本散在 `_load()` 和 `predict()` 的 if/else 里：
  导入路径、缺依赖时的提示、必需参数、是否合并官方默认值、动作是单步还是整块。
  新增第三个官方策略时要改 4 处代码，容易漏。

  抽成表之后：**已有动作模式（single / queue）的新策略 = 加一条 profile**，
  不需要改服务器逻辑；只有全新动作模式（比如批量并行）才需要加分支。

注意：这里只放"决策数据"，不放模型代码；导入保持惰性（镜像里才有的官方包）。
"""
from __future__ import annotations

from dataclasses import dataclass

ACT_IMPORT_HINT = (
    "ACT 导入失败：缺 {missing}。robotwin 镜像（0.8.0-ee-slim）实测可导入 ACT；"
    "若换镜像，需把 detr 等依赖烘进去（V100 禁止现场 pip）。"
)
DP_IMPORT_HINT = (
    "DP 导入失败：缺 {missing}。实测 0.8.0-ee-slim 的 robotwin 环境缺 hydra/dill"
    "（diffusion_policy 本身是 vendored，不用另装）；需另烘一个 DP serve 镜像，再切 serve_image。"
)


@dataclass(frozen=True)
class PolicyProfile:
    name: str
    import_path: str                 # 官方 deploy_policy 的模块路径（惰性导入）
    import_hint: str
    required_args: tuple[str, ...] = ()
    merge_official_defaults: bool = False   # ACT 的 parser 默认值必须先铺底
    action_mode: str = "single"      # single = 每步一个；queue = 整块排空再推理
    ckpt_guard: str | None = None    # "policy_last" = 官方只认该文件名，缺了会随机权重


PROFILES: dict[str, PolicyProfile] = {
    "act": PolicyProfile(
        name="act",
        import_path="policy.ACT.deploy_policy",
        import_hint=ACT_IMPORT_HINT,
        merge_official_defaults=True,
        action_mode="single",
        ckpt_guard="policy_last",
    ),
    "dp": PolicyProfile(
        name="dp",
        import_path="policy.DP.deploy_policy",
        import_hint=DP_IMPORT_HINT,
        required_args=("task_name", "expert_data_num"),
        action_mode="queue",
    ),
}

ACTION_MODES = {"single", "queue"}


def get_profile(name: str) -> PolicyProfile:
    key = (name or "").lower()
    if key not in PROFILES:
        raise ValueError(f"policy 只允许 {sorted(PROFILES)}（实际 {name!r}）")
    return PROFILES[key]

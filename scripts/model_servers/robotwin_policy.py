#!/usr/bin/env python3
"""RoboTwin 官方 ACT / DP 的 serve 适配器（一个文件，`--policy act|dp` 切换）。

背景
----
RoboTwin 官方 `policy/ACT`、`policy/DP` 自带训练与部署代码，但部署入口是
`deploy_policy.py` 里的 `eval(TASK_ENV, model, observation)`——它自己驱动环境。
harness 的模型侧只需要"给观测、返回动作"，所以要绕开 `eval()`，直接用：

    model = get_model(usr_args)      # ACT(usr_args, Namespace(**usr_args)) / DP(ckpt, ...)
    actions = model.get_action(obs)  # 内部自带 chunk / 动作队列复用

`obs` 的键由官方 `encode_obs()` 决定：
    ACT: {head_cam, left_cam, right_cam} (CHW, 640x480, 0..1) + qpos(14)
    DP : {head_cam, left_cam, right_cam} (CHW, 0..1)            + agent_pos(14)

状态性
------
两个策略都**自带时序状态**（ACT 的 `query_frequency` / `temporal_agg`，DP 的
`n_action_steps` 动作队列）。所以这里绝不能设 chunk_size（否则双重缓冲，动作错位），
每步只调一次 `get_action`，并在 episode 开始时 `reset_model`。

⚠️ 状态：**未验证**（2026-11-24 写就，机器被 Hard 评测占用，未做 smoke）。
首次使用前必须按 `docs/internal/act-dp-adapter-runbook.md` 跑 1 task×1ep smoke。

用法（serve yaml 里）：
    script: "scripts/model_servers/robotwin_policy.py"
    args:
      policy: act
      ckpt_dir: /root/robotwin-train/ckpt/grab_roller-clean50-seed0
      task_name: grab_roller
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

# 纯函数放在同目录的 robotwin_obs.py（零依赖、可单测）；serve 按路径加载本文件时
# 目录不一定在 sys.path 里，所以显式加一次。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from robotwin_obs import build_policy_obs  # noqa: E402

from vla_eval.model_servers.base import SessionContext
from vla_eval.model_servers.predict import PredictModelServer
from vla_eval.specs import IMAGE_RGB, RAW
from vla_eval.types import Action, Observation

# 官方 deploy_policy.yml 的默认值（ACT / DP 两份合并；未用到的键会被忽略）
_ROBOTWIN_DEFAULTS: dict[str, Any] = {
    # 通用
    "task_name": None,
    "task_config": None,
    "ckpt_setting": None,
    "seed": 0,
    "instruction_type": "unseen",
    "action_dim": 14,
    "state_dim": 14,                     # detr parser 必填
    # 官方 act_policy 里硬编码这三个名字（detr_vae 按列表长度索引摄像机位）
    "camera_names": ["head_cam", "left_cam", "right_cam"],
    # ACT
    "kl_weight": 10.0,
    "chunk_size": 50,
    "hidden_dim": 512,
    "dim_feedforward": 3200,
    "temporal_agg": False,
    "ckpt_dir": None,
    "policy_class": "ACT",
    "num_epochs": 2000,
    "position_embedding": "sine",
    "lr_backbone": 1e-5,
    "weight_decay": 1e-4,
    "lr": 1e-5,
    "masks": False,
    "dilation": False,
    "backbone": "resnet18",
    # DP
    "expert_data_num": None,
    "checkpoint_num": 600,
    "head_camera_type": "D435",
    "left_arm_dim": 6,
    "right_arm_dim": 6,
}

_CAMERAS = ("head_camera", "left_camera", "right_camera")


class RoboTwinPolicyServer(PredictModelServer):
    """官方 ACT/DP 的薄适配层（不做任何模型侧改动）。"""

    def __init__(
        self,
        policy: str = "act",
        ckpt_dir: str | None = None,
        device: str = "cuda:0",
        robotwin_root: str = "/app/RoboTwin",
        **overrides: Any,
    ) -> None:
        policy = policy.lower()
        if policy not in ("act", "dp"):
            raise ValueError(f"policy 只允许 act|dp（实际 {policy!r}）")
        # 策略自带时序缓冲，harness 层不得再切 chunk
        super().__init__(chunk_size=None, action_ensemble="newest")
        self.policy_kind = policy
        self.ckpt_dir = ckpt_dir
        self.device = device
        self.robotwin_root = robotwin_root

        self._usr_args = dict(_ROBOTWIN_DEFAULTS)
        self._usr_args.update({k: v for k, v in overrides.items() if v is not None})
        if ckpt_dir:
            self._usr_args["ckpt_dir"] = ckpt_dir
        self._usr_args["device"] = device

        self._module = None
        self._model = None
        self._parser_defaults: dict[str, Any] | None = None

    # ---------------------------------------------------------------- specs
    def get_action_spec(self) -> dict[str, Any]:
        return {"actions": RAW}

    def get_observation_spec(self) -> dict[str, Any]:
        return {"image": IMAGE_RGB, "left_camera": IMAGE_RGB, "right_camera": IMAGE_RGB}

    # -------------------------------------------------------------- loading
    def _official_defaults(self, dp_module: Any) -> dict[str, Any]:
        """用官方 detr parser 的默认值打底。

        实测教训（2026-11-24）：只按 `deploy_policy.yml` 填会缺 `dropout`
        （`build_transformer` 直接读 args.dropout），且 `camera_names` 为空会让
        `detr_vae.forward` 拿不到任何相机特征（`torch.cat([])` 报错）。
        所以默认值必须来自官方 parser，而不是我们手抄的 yml。
        """
        if self._parser_defaults is not None:
            return self._parser_defaults
        from policy.ACT.detr.main import get_args_parser  # type: ignore

        required = [
            "--ckpt_dir", self._usr_args.get("ckpt_dir") or "/tmp/ckpt",
            "--policy_class", "ACT",
            "--task_name", str(self._usr_args.get("task_name") or "grab_roller"),
            "--seed", str(self._usr_args.get("seed") or 0),
            "--num_epochs", str(self._usr_args.get("num_epochs") or 2000),
            "--state_dim", str(self._usr_args.get("state_dim") or 14),
        ]
        self._parser_defaults = vars(get_args_parser().parse_args(required))
        return self._parser_defaults

    def _load(self) -> None:
        if self._model is not None:
            return
        # 官方代码是 package 形式（`from .act_policy import ACT`），
        # 所以把 RoboTwin 根目录加进 sys.path，按 package 导入。
        if self.robotwin_root not in sys.path:
            sys.path.insert(0, self.robotwin_root)

        if self.policy_kind == "act":
            try:
                from policy.ACT import deploy_policy as dp  # type: ignore
            except ModuleNotFoundError as e:
                raise RuntimeError(
                    f"ACT 导入失败：缺 {e.name}。robotwin 镜像（0.8.0-ee-slim）实测可导入 ACT；"
                    "若换镜像，需把 detr 等依赖烘进去（V100 禁止现场 pip）。"
                ) from e
        else:
            try:
                from policy.DP import deploy_policy as dp  # type: ignore
            except ModuleNotFoundError as e:
                raise RuntimeError(
                    f"DP 导入失败：缺 {e.name}。实测 0.8.0-ee-slim 的 robotwin 环境缺 hydra/dill"
                    "（diffusion_policy 本身是 vendored，不用另装）；"
                    "需另烘一个 DP serve 镜像，再切 serve_image。"
                ) from e

        if self.policy_kind == "dp":
            # DP 的 get_model 从 ckpt_dir 约定拼路径，需要 task_name/expert_data_num 等
            missing = [k for k in ("task_name", "expert_data_num") if not self._usr_args.get(k)]
            if missing:
                raise ValueError(
                    f"DP 需要 usr_args 里的 {missing}（官方按 <task>-<setting>-<num>-<seed> 拼 ckpt 路径）；"
                    f"当前只有 {sorted(k for k, v in self._usr_args.items() if v is not None)}"
                )

        if self.policy_kind == "act":
            merged = dict(self._official_defaults(dp))
            merged.update({k: v for k, v in self._usr_args.items() if v is not None})
        else:
            merged = dict(self._usr_args)
        self._dp = dp
        self._model = dp.get_model(merged)
        self._module = dp

    def _reset(self) -> None:
        if self._model is not None and self._module is not None:
            self._module.reset_model(self._model)

    # ------------------------------------------------------------ inference
    def _to_robotwin_obs(self, obs: Observation) -> dict[str, Any]:
        """harness Observation → 官方 encode_obs 的产物（转换逻辑见 robotwin_obs.py）。"""
        images = obs.get("images") or {}
        if not isinstance(images, dict):
            images = {"head_camera": images}
        js = obs.get("joint_state")
        if js is None:
            raise KeyError("观测缺 joint_state（ACT 要 qpos / DP 要 agent_pos，都是 14 维）")
        return build_policy_obs(
            images,
            js,
            self.policy_kind,
            int(self._usr_args.get("action_dim", 14)),
        )

    def predict(self, obs: Observation, ctx: SessionContext) -> Action:
        self._load()
        rw_obs = self._to_robotwin_obs(obs)
        act = self._model.get_action(rw_obs)
        arr = np.asarray(act, dtype=np.float32).reshape(-1)
        dim = int(self._usr_args.get("action_dim", 14))
        if arr.size != dim:
            raise ValueError(f"策略返回 {arr.size} 维动作，与 action_dim={dim} 不符")
        return {"actions": arr.reshape(1, dim)}

    async def on_episode_start(self, config: dict[str, Any], ctx: SessionContext) -> None:
        # 每个 episode 清一次时序状态（ACT 的 all_time_actions / DP 的动作队列）
        if self.ckpt_dir is None and not self._usr_args.get("task_name"):
            raise ValueError(
                "serve yaml 必须给 ckpt_dir（ACT）或 task_name+expert_data_num（DP），"
                f"当前只有 {sorted(k for k, v in self._usr_args.items() if v is not None)}"
            )
        self._reset()
        await super().on_episode_start(config, ctx)


if __name__ == "__main__":
    from vla_eval.model_servers.serve import run_server

    run_server(RoboTwinPolicyServer)

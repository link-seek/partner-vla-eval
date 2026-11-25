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

✅ 状态：**已验通路**（2026-11-25）：ACT click_bell 1/1 success、num_errors=0；
50 集校准跑进行中。2026-11-25 另修一处静默错误——官方只认 `policy_last.ckpt`，
发布权重是 `policy_epoch_*_seed_*.ckpt`，不显式给 `ckpt_file` 会用随机权重跑满 400 步且不报错。

用法（serve yaml 里）：
    script: "scripts/model_servers/robotwin_policy.py"
    args:
      policy: act
      ckpt_dir: /root/robotwin-train/ckpt/grab_roller-clean50-seed0
      task_name: grab_roller
"""
from __future__ import annotations

import glob
import importlib
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

# 纯函数放在同目录的 robotwin_obs.py（零依赖、可单测）；serve 按路径加载本文件时
# 目录不一定在 sys.path 里，所以显式加一次。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from action_queue import ActionQueue  # noqa: E402
from act_ckpt import resolve_act_ckpt  # noqa: E402
from policy_profiles import get_profile  # noqa: E402
from robotwin_obs import build_policy_obs, split_action_chunk  # noqa: E402

from vla_eval.model_servers.base import SessionContext
from vla_eval.model_servers.predict import PredictModelServer
from vla_eval.specs import IMAGE_RGB, LANGUAGE, STATE_JOINT, DimSpec
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
    # 实测：官方 ACT ckpt 的 decoder 有 7 层（parser 默认 6），差一层会 missing=0/unexpected=18，
    # 模型少跑一层、动作悄悄偏掉。见 runbook §0.1。
    "dec_layers": 7,
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
        ckpt_file: str | None = None,
        device: str = "cuda:0",
        robotwin_root: str = "/app/RoboTwin",
        # 以下必须显式声明：harness 的 serve CLI 会内省 __init__ 签名来生成 --args.*，
        # 藏在 **kwargs 里的参数它认不出来（实测会被 CLI 拒绝）。
        action_dim: int = 14,
        state_dim: int = 14,
        hidden_dim: int = 512,
        dim_feedforward: int = 3200,
        dec_layers: int = 7,
        enc_layers: int = 4,
        camera_names: list[str] | None = None,
        chunk_size: int = 50,
        temporal_agg: bool = False,
        kl_weight: float = 10.0,
        task_name: str | None = None,
        ckpt_setting: str | None = None,
        expert_data_num: int | None = None,
        seed: int = 0,
        checkpoint_num: int = 600,
        # 官方 DP 的 get_model 要这两个来算 action_dim = left + right + 2 个夹爪。
        # 必须显式声明：jsonargparse 按类签名生成 --args.*，缺了就直接
        # "unrecognized arguments: --args.left_arm_dim=6"（2026-11-25 实测）。
        left_arm_dim: int = 6,
        right_arm_dim: int = 6,
        # 服务端口：harness 的 serve 读的是 args.port（默认 8000），
        # 写成 yaml 顶层 server.port 会被静默忽略（2026-11-25 实测：去绑了 8000）。
        port: int = 8000,
        **overrides: Any,
    ) -> None:
        # 差异全部来自 profile 表（policy_profiles.py）：加策略 = 加一条数据
        self.profile = get_profile(policy)
        policy = self.profile.name
        # 策略自带时序缓冲，harness 层不得再切 chunk
        super().__init__(chunk_size=None, action_ensemble="newest")
        self.policy_kind = policy
        self.ckpt_dir = ckpt_dir
        self.ckpt_file = ckpt_file
        self.device = device
        self.robotwin_root = robotwin_root

        self._usr_args = dict(_ROBOTWIN_DEFAULTS)
        self._usr_args.update({
            k: v for k, v in {
                "action_dim": action_dim, "state_dim": state_dim,
                "hidden_dim": hidden_dim, "dim_feedforward": dim_feedforward,
                "dec_layers": dec_layers, "enc_layers": enc_layers,
                "camera_names": camera_names, "chunk_size": chunk_size,
                "temporal_agg": temporal_agg, "kl_weight": kl_weight,
                "task_name": task_name, "ckpt_setting": ckpt_setting,
                "expert_data_num": expert_data_num, "seed": seed,
                "checkpoint_num": checkpoint_num,
                "left_arm_dim": left_arm_dim, "right_arm_dim": right_arm_dim,
            }.items() if v is not None
        })
        self._usr_args.update({k: v for k, v in overrides.items() if v is not None})
        # 分块策略（DP）的动作队列：队列空才推理、每步吐一个。
        # 逻辑抽在 action_queue.py（纯函数，配单测），接第三个策略时可复用。
        self._queue = ActionQueue(int(self._usr_args.get("action_dim", 14)))
        if ckpt_dir:
            self._usr_args["ckpt_dir"] = ckpt_dir
        self._usr_args["device"] = device

        self._module = None
        self._model = None
        self._parser_defaults: dict[str, Any] | None = None

    # ---------------------------------------------------------------- specs
    def get_action_spec(self) -> dict[str, Any]:
        # 与 RobotWin benchmark 的声明逐字对齐（2026-11-25 从 benchmark 源码取）：
        #   "joints": DimSpec("joints", 14, "joint_positions")
        return {"joints": DimSpec("joints", int(self._usr_args.get("action_dim", 14)), "joint_positions")}

    def get_observation_spec(self) -> dict[str, Any]:
        # 与 RobotWin benchmark 的声明逐字对齐（2026-11-25 从 benchmark 源码取）：
        #   head_camera / left_camera / right_camera / state(STATE_JOINT) / language
        # 注：send_state 时 benchmark 还会加 ee_state，我们不需要，故不声明。
        return {
            "head_camera": IMAGE_RGB,
            "left_camera": IMAGE_RGB,
            "right_camera": IMAGE_RGB,
            "state": STATE_JOINT,
            "language": LANGUAGE,
        }

    def get_observation_params(self) -> dict[str, Any]:
        """告诉考场"要送关节状态"。

        没有这一条，考场不会带 `joint_state`，predict 里必然 KeyError
        （2026-11-24 `vla-eval test -c` 实测就是栽在这里）。
        官方 CogACT/pi0/lerobot 等 server 都是这么声明的。
        """
        return {"send_state": True}

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

    def _act_ckpt_or_fail(self) -> None:
        """官方 ACT 只认 `<ckpt_dir>/policy_last.ckpt`，缺了会**静默**留随机权重。

        判断逻辑抽在 `act_ckpt.py`（纯函数 + 单测）：显式 ckpt_file 优先；
        目录里没有 policy_last 就报错，不猜。
        """
        resolve_act_ckpt(self._usr_args.get("ckpt_dir"), self.ckpt_file)

    def _load(self) -> None:
        if self._model is not None:
            return
        # 官方代码是 package 形式（`from .act_policy import ACT`），
        # 所以把 RoboTwin 根目录加进 sys.path，按 package 导入。
        if self.robotwin_root not in sys.path:
            sys.path.insert(0, self.robotwin_root)

        p = self.profile
        try:
            dp = importlib.import_module(p.import_path)
        except ModuleNotFoundError as e:
            raise RuntimeError(p.import_hint.format(missing=e.name)) from e

        missing = [k for k in p.required_args if not self._usr_args.get(k)]
        if missing:
            raise ValueError(
                f"{p.name} 需要 usr_args 里的 {missing}（官方按约定拼 ckpt 路径）；"
                f"当前只有 {sorted(k for k, v in self._usr_args.items() if v is not None)}"
            )

        if p.ckpt_guard == "policy_last":
            self._act_ckpt_or_fail()
        if p.merge_official_defaults:
            merged = dict(self._official_defaults(dp))
            merged.update({k: v for k, v in self._usr_args.items() if v is not None})
        else:
            merged = dict(self._usr_args)
        self._dp = dp
        self._model = dp.get_model(merged)

        if self.ckpt_file:
            # 官方 ckpt 文件名是 policy_epoch_<N>_seed_<S>.ckpt，而 deploy_policy 只认
            # policy_last.ckpt —— 内置加载会告警跳过并留随机权重（静默错误）。
            # 所以显式给了 ckpt_file 就自己 load，并对 missing 严格断言。
            import torch

            sd = torch.load(self.ckpt_file, map_location=self.device)
            if isinstance(sd, dict) and "model" in sd:
                sd = sd["model"]
            missing_keys, unexpected = self._model.policy.load_state_dict(sd, strict=False)
            if missing_keys:
                raise RuntimeError(
                    f"ckpt 缺 {len(missing_keys)} 个键（前 3：{missing_keys[:3]}）。"
                    "多半是 hidden_dim / dim_feedforward / dec_layers 与训练时不一致。"
                )
            if unexpected:
                raise RuntimeError(
                    f"ckpt 多 {len(unexpected)} 个键（前 3：{unexpected[:3]}）。"
                    "多半是 dec_layers 少于训练值（官方 ckpt 实测需 7 层）。"
                )
        self._module = dp

    def _reset(self) -> None:
        self._queue.clear()
        if self._model is not None and self._module is not None:
            self._module.reset_model(self._model)

    # ------------------------------------------------------------ inference
    def _to_robotwin_obs(self, obs: Observation) -> dict[str, Any]:
        """harness Observation → 官方 encode_obs 的产物（转换逻辑见 robotwin_obs.py）。"""
        # 注意：不能用 `or` 兜底——numpy 数组的真值会抛 ValueError
        # （2026-11-25 实测：js = obs.get("joint_state") or obs.get("state") 直接炸）。
        images = obs.get("images")
        if not isinstance(images, dict) or not images:
            images = {k: obs[k] for k in ("head_camera", "left_camera", "right_camera") if k in obs}
        js = obs.get("joint_state")
        if js is None:
            js = obs.get("state")
        if js is None:
            raise KeyError("观测缺 joint_state（ACT 要 qpos / DP 要 agent_pos，都是 14 维）")
        # 一次性诊断（RW_DEBUG_OBS=1）：打印实际键名/维度/原图尺寸，别再靠猜
        if os.environ.get("RW_DEBUG_OBS") == "1" and not getattr(self, "_dbg_done", False):
            self._dbg_done = True
            arr = np.asarray(js).reshape(-1)
            print("[dbg] obs keys:", sorted(obs.keys()), flush=True)
            print(f"[dbg] state dim={arr.size} dtype={arr.dtype} head={arr[:4]}", flush=True)
            print(f"[dbg] image shapes={ {k: getattr(v, 'shape', None) for k, v in images.items()} }", flush=True)
        return build_policy_obs(
            images,
            js,
            self.policy_kind,
            int(self._usr_args.get("action_dim", 14)),
        )

    def predict(self, obs: Observation, ctx: SessionContext) -> Action:
        self._load()
        dim = int(self._usr_args.get("action_dim", 14))

        if self.profile.action_mode == "queue":
            # 队列空才推理（= 官方的"整块开环执行"），否则继续吐上一块的剩余步。
            if self._queue.pending == 0:
                self._queue.push(self._model.get_action(self._to_robotwin_obs(obs)))
            return {"actions": self._queue.pop().reshape(1, dim)}

        act = self._model.get_action(self._to_robotwin_obs(obs))
        actions = split_action_chunk(act, dim)
        if len(actions) != 1:
            raise ValueError(
                f"ACT 应返回单步动作，实际 {len(actions)} 步（{np.asarray(act).size} 维）；"
                "若换成分块策略请走 dp 分支")
        return {"actions": actions[0].reshape(1, dim)}

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

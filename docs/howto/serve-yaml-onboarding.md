---
nav_exclude: true
---

# Onboarding a Model: Writing a Harness-Compatible Serve Config

> Status: DRAFT for upstream discussion (not yet submitted).
> Rule: confirm with maintainers before polishing into a PR (#169 lesson).
> Scope: generic vla-eval only. No org-specific infra (registries, runners, queues).

## Goal

Turn a trained VLA checkpoint into a serve config (`serve-*.yaml`) that
`vla-eval serve` accepts and any benchmark can drive. You need no GPU farm:
validate locally, then run one smoke episode.

## Step 1: Pick your route (you know your model)

| Model type | Route |
|---|---|
| Any 🤗 LeRobot `PreTrainedPolicy` checkpoint (π0.5, GR00T, SmolVLA, MolmoAct2, …) | LeRobot bridge, one config, swap `checkpoint` |
| Model with an existing server in `configs/model_servers/` | Copy its config, change 6 fields below |
| Anything else | Write a server (~50 lines `predict()`, see CONTRIBUTING "Adding a Model Server"), or open an issue with your checkpoint |

## Step 2: Fill the 6 universal fields

Copy the closest example, change only these (everything else stays):

| # | Field | What to check |
|---|---|---|
| 1 | action dim + meaning | Joint qpos or end-effector? For EE note rot6d/quat and gripper inclusion |
| 2 | `image_keys` | Camera names exactly as the benchmark publishes them |
| 3 | `state_key` | Joint angles / EE pose / none |
| 4 | `chunk_size` | Match the benchmark cadence |
| 5 | dtype | fp32 vs fp16 is not interchangeable (X-VLA fp16 crashes at first inference; CogACT fp32 OOMs single-GPU) |
| 6 | weights | Exact Hub commit (never branch name); per-task heads listed one by one |

```yaml
# LeRobot bridge (single arm), closest generic example
script: "src/vla_eval/model_servers/lerobot.py"
args:
  policy_type: pi05
  checkpoint: lerobot/pi05_libero_finetuned
  image_keys: {agentview: image, wrist: image2}
  state_key: observation.state
  chunk_size: 10
```

## Step 3: Validate before burning GPU

1. `vla-eval test -c <your-serve.yaml>` (needs uv + weights + GPU; upstream smoke test).
2. Read the first 20 log lines of a real run: any `Spec mismatch` is a stop sign.
 Root-cause by the table above, not by re-running. Advisory-level warnings
 (e.g. undeclared but working EE pose) are documented exceptions, not blockers.

## Why this exists

Upstream ships per-model READMEs (parameter tables) and a developer guide for
writing servers, but no user-facing "write your first compatible config" path.
This note fills that gap. Field semantics verified against the
`configs/model_servers/*` READMEs and the vla-eval paper (arXiv:2603.13966).

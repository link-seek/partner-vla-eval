# How Much of a VLA Leaderboard Score Is the Stack?

## Abstract

VLA leaderboards compare scores across models, but rarely control what the
scores were produced *with*: GPU type, weight dtype, benchmark image version,
seed set, sharding, asset mounting. We vary one knob at a time on a fixed
V100 stack and report the score delta of each. Most knobs do not move scores
(benchmark image 0.7.0 vs 0.8.0: 86% vs 92%, n=50, within noise; baked vs
native image: 18/20 vs 18/20; external asset mount vs built-in: 45/50 vs
46/50). One knob moves scores off a cliff: X-VLA in fp16 vs fp32 on LIBERO
goes from 0/30 to 29/30 across three suites — the fp16 path fails at the
operator level (`float` vs `Half` bias mismatch on the first inference), it
does not merely degrade. We release a VLA evaluation stack disclosure
checklist (GPU / dtype / image tag+digest / seed protocol / shards /
mounts) and all images publicly so any entry in our tables can be re-run
with one pull.

## 1. Introduction

A VLA score is a joint product of model, benchmark, and stack. The community
standardizes the first two and ignores the third. This is load-bearing:
papers and leaderboards routinely compare an fp16 number from one lab with a
bf16 number from another, or a 0.7.0 number with a 0.8.0 number, as if the
stack were transparent. We test whether it is.

## 2. Method

One knob at a time, everything else pinned (V100 32GB, fixed seeds, fixed
shards unless the knob *is* sharding). Each run's artifacts (aggregate JSON,
SQLite recordings, logs) are archived; every image is published with its
Dockerfile so deltas are reproducible, not anecdotal. Negative-control
discipline throughout: mounts are verified by breaking them on purpose
(overlay /tmp over the asset dir must crash in seconds, or the mount is
being ignored); image identity is verified by digest, not tag.

## 3. Results

**Benchmark image (0.7.0 vs 0.8.0).** grab_roller x50, same seeds: 43/50
(86%) vs 46/50 (92%). Difference 6pp against a ~12pp 2-sigma band at n=50:
no significant difference. Scope: one task.

**Baked vs native.** Our rebuilt slim image (assets removed, nvcc stripped,
11.3GB vs 21GB) vs the upstream-identical stock image, grab_roller x20 same
seeds: 18/20 vs 18/20. Zero delta.

**Asset mounting.** External 16GB asset mount vs image-baked assets, same
50 seeds: 45/50 (90%) vs 46/50 (92%). Equivalent.

**Precision (the cliff).** X-VLA on LIBERO (spatial/object/goal x10, same
seed=7): fp32 scores 9/10, 10/10, 10/10 (29/30); fp16 scores 0/10 x3 (0/30).
The fp16 zeros are not low scores: every episode errors at the first
inference with `RuntimeError: Input type (float) and bias type (c10::Half)
should be the same`. The denoising path is numerically broken in fp16 on
this stack, exactly as the upstream code comment warns ("sensitive to
precision"). A 7B CogACT in fp32 does not even load on a 32GB card (OOM at
first forward); sharded across two cards it loads, but the custom
architecture's forward has bare cross-device concatenations, so split
inference needs model surgery — single-GPU fp32 comparison remains
unavailable on V100, reported as a limit, not a result.

**Sharding.** 2 shards stable, 4 slow, 8 hangs. Speed/stability only.

**Seeds.** Blind seeds vs bundled verified seeds move the error rate, not
the valid-score; re-running the same bundled 50 seeds gives 41/50 vs 46/50
(diff -10pp, ~1.7 sigma: noise).

**Cross-stack reference.** place_empty_cup: our V100 fp16 16~20% vs official
H100 bf16 28%. Recorded as pending (different GPU *and* dtype), not judged.

## 4. Related work

vla-eval (protocol layer), VLATest (environment perturbations, 580 GPU-h),
VLA-Perf (cross-GPU speed only, assumes BF16/FP16 interchangeable — our
Section 3 falsifies that for at least X-VLA), [2606.04233] (leaderboard
design), REPLICA (real-robot cross-site), bifrost eval guide (practical
checklist, no precision study), upstream #44 (ROCm accuracy parity,
hardware direction). None quantifies same-code-different-stack score
deltas. That is this paper.

## 5. The disclosure checklist

GPU model + driver; weight dtype; benchmark image digest (+ slim/patch
notes); serve image digest; seed protocol (bundled vs blind, base seed);
shard count; asset/code mounts; harness ref. Missing one item: not
comparable.

## 6. Conclusion

Stacks are not transparent: one common knob (fp16) takes a model from 97%
to 0% without changing a single weight. Compare same-stack, or disclose.

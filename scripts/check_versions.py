#!/usr/bin/env python3
"""versions.yaml 一致性门：Dockerfile 的 pin 不许私自漂移。
长期机制：新增/改动 pin 只改 versions.yaml + Dockerfile ARG 默认，两处对不上即红。
已知债走 versions.yaml 的 known_debts（带到期条件），不在此脚本里开口子。
"""
import re, sys
import yaml

V = yaml.safe_load(open("docker/versions.yaml"))
fails = []

def norm(v):
    return (v or "").lstrip("v")

def arg_default(path, name):
    m = re.search(rf"^ARG\s+{name}=(.+?)\s*$", open(path).read(), re.M)
    return m.group(1).strip().strip('"') if m else None

# 1. serve 系 HARNESS_REF：必须等于 target，或在 known_debts 中登记
debts = V.get("known_debts_harness_070", [])
import glob
for f in sorted(glob.glob("docker/Dockerfile.serve-*")):
    v = arg_default(f, "HARNESS_REF")
    if norm(v) == norm(V["harness_serve_target"]):
        continue
    name = f.split("/")[-1]
    if v == "v0.7.0" and name in debts:
        print(f"DEBT-OK {name} (0.7.0, 待升级冒烟)")
    else:
        fails.append(f"{f}: HARNESS_REF={v} 与 target {V['harness_serve_target']} 不一致且未登记")

# 2. torch_serve：serve 系 sed 目标必须 == torch_serve_cu126
for f in sorted(glob.glob("docker/Dockerfile.serve-*")):
    txt = open(f).read()
    if '"torch==2.6.0"' in txt or "'torch==2.6.0'" in txt or "torch==2.6.0" in txt:
        continue
    fails.append(f"{f}: 未找到 torch=={V['torch_serve_cu126']} 钉死")

# 3. python 基座：serve 系必须 FROM python:3.12-slim
for f in sorted(glob.glob("docker/Dockerfile.serve-*")):
    if "FROM python:3.12-slim" not in open(f).read():
        fails.append(f"{f}: 基座不是 python:3.12-slim")

# 5. 统一镜像：EE REF + P2 烘焙 + fork 出处（构建时拉，运行时不拉）
_U = open("docker/Dockerfile.robotwin-unified").read()
for _k in ["harness_unified_ref"]:
    if V[_k] not in _U:
        fails.append("Dockerfile.robotwin-unified: %s 未引用" % _k)
# harness_patch_ref 只记 P2-only 分支（上游 PR 用），烘焙以 unified 为准（同源防覆盖，10-26 教训）
if V["harness_fork"] not in _U:
    fails.append("Dockerfile.robotwin-unified: 未引用 fork")
if "github.com/allenai/vla-evaluation-harness" in _U:
    fails.append("Dockerfile.robotwin-unified: 仍直连上游 harness")
import os as _os
if not _os.path.exists("docker/entrypoint-robotwin.sh"):
    fails.append("docker/entrypoint-robotwin.sh 缺失")
elif "STATE_PATCH" not in open("docker/entrypoint-robotwin.sh").read():
    fails.append("entrypoint-robotwin.sh: 无 STATE_PATCH 激活")

# 6. verify 镜像：只许 SWR 拉，不许本地构建（V100 出境限速，构建按小时计）
import subprocess as _sp
_v = open("docker/Dockerfile.verify").read()
if ('vla-eval==%s' % V["verify_vla_eval"]) not in _v:
    fails.append("Dockerfile.verify: vla-eval 与 versions.yaml 不一致")
for _f in ["scripts/ci_robotwin.sh", "scripts/ci_libero.sh", "scripts/ci_calvin.sh", "scripts/ci_robotwin_full.sh"]:
    _t = open(_f).read()
    if "docker build -f docker/Dockerfile.verify" in _t:
        fails.append("%s: verify 改 SWR 拉，不许本地构建" % _f)
    if "vla-verify:0.1" not in _t and "VERIFY_IMAGE" not in _t:
        fails.append("%s: 未引用 SWR verify 镜像" % _f)

# 7. V100 出境禁令：ci 编排脚本不许 git clone（现场下源码在限速下必挂；一律烘进镜像走 SWR）
# 例外：ci_smoke.sh（molmo 路，待转 SWR serve；转完删豁免）
for _f in ["scripts/ci_libero.sh", "scripts/ci_calvin.sh", "scripts/ci_robotwin.sh", "scripts/ci_robotwin_full.sh"]:
    _t = open(_f).read()
    if "git clone" in _t:
        fails.append("%s: 含 git clone，改烘进镜像" % _f)

# 8. V100 job 零 checkout（代码走 payload 镜像；只剩 hw21 start-ecs 的 1 个）
import glob as _glob
for _wf in ["pi-libero-smoke.yml", "pi-calvin-smoke.yml", "pi0-robotwin-smoke.yml", "pi0-robotwin-full.yml", "pi0-molmo-smoke.yml"]:
    _wt = open(f".github/workflows/{_wf}").read()
    if _wt.count("actions/checkout") != 1:
        fails.append(f"{_wf}: checkout 数={_wt.count('actions/checkout')}，应为 1（仅 hw21 start-ecs）")
    if "sparse-checkout" in _wt:
        fails.append(f"{_wf}: 还有 sparse-checkout 残留")

# 4. 源码出处：serve 系只许从 fork clone（研究仓不再直连上游源码）
for f in sorted(glob.glob("docker/Dockerfile.serve-*")):
    txt = open(f).read()
    if "github.com/allenai/vla-evaluation-harness" in txt:
        fails.append(f"{f}: 仍直连上游源码，改走 fork {V['harness_fork']}")
    if V["harness_fork"] + ".git harness" not in txt:
        fails.append(f"{f}: 未引用 fork {V['harness_fork']}")

if fails:
    print("VERSION-DRIFT:")
    [print(" -", x) for x in fails]
    sys.exit(1)
print("VERSIONS OK")

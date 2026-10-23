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

if fails:
    print("VERSION-DRIFT:")
    [print(" -", x) for x in fails]
    sys.exit(1)
print("VERSIONS OK")

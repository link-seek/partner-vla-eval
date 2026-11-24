#!/usr/bin/env python3
"""collect_matrix.sh 的输出里若一个 task 都没出数，就删掉该文件（供 workflow 过滤用）。"""
import json, os, sys
p = sys.argv[1]
try:
    d = json.load(open(p))
except Exception:
    sys.exit(0)
if all(v.get("status") == "missing" for v in d.get("tasks", {}).values()):
    os.remove(p)
    print(f"drop empty: {p}")

#!/usr/bin/env python3
"""policy_profiles 单测：新增策略只需加一条数据，这些约束必须成立。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from policy_profiles import ACTION_MODES, PROFILES, get_profile  # noqa: E402

fails: list[str] = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name} {detail if not cond else ''}")
    if not cond:
        fails.append(name)


print("[必需的两个 profile]")
check("act/dp 都在", set(PROFILES) >= {"act", "dp"}, sorted(PROFILES))
check("act 单步", get_profile("act").action_mode == "single")
check("dp 整块队列", get_profile("dp").action_mode == "queue")
check("act 合并官方默认值", get_profile("act").merge_official_defaults is True)
check("dp 合并官方默认值", get_profile("dp").merge_official_defaults is False)
check("act 有 policy_last 守卫", get_profile("act").ckpt_guard == "policy_last")
check("dp 无 ckpt 守卫", get_profile("dp").ckpt_guard is None)
check("dp 需要 task_name/expert_data_num",
      get_profile("dp").required_args == ("task_name", "expert_data_num"))

print("[表本身的一致性]")
for name, p in PROFILES.items():
    check(f"{name}: 名字一致", p.name == name)
    check(f"{name}: 动作模式合法", p.action_mode in ACTION_MODES, p.action_mode)
    check(f"{name}: import 路径以 policy. 开头", p.import_path.startswith("policy."), p.import_path)
    check(f"{name}: 提示含插槽", "{missing}" in p.import_hint)
check("大小写不敏感", get_profile("ACT").name == "act")
try:
    get_profile("smolvla")
    check("未知策略报错", False, "没抛")
except ValueError as e:
    check("未知策略报错", "只允许" in str(e), str(e))

if fails:
    print(f"\nFAILED: {len(fails)} -> {fails}")
    sys.exit(1)
print("\nALL OK")

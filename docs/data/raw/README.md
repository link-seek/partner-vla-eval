---
title: 原始 aggregate（逐集证据）
nav_exclude: true
status: living
---

# 原始 aggregate

这里放评测器直接导出的 aggregate（逐集 seed / steps / metrics），用于复核摘要 JSON 里的 n、success、errors。

## act-baseline_click_bell-x50.aggregate.json

| 项 | 值 |
|---|---|
| 来源 | 0002 `/root/r01/act50v3/results/act/click_bell_aggregate.json` |
| 运行 | 2026-11-25，ACT 官方 ckpt（100-demo），Easy/demo_clean |
| 规模 | 50 集，`episodes_per_task=1` + `test_num=50` |
| eval_id | `c4cfd5fb-4447-4834-bacb-10c66f11f392-click_bell` |

复核（不需要信任摘要）：

```bash
python3 - <<'PY'
import json
d = json.load(open('docs/data/raw/act-baseline_click_bell-x50.aggregate.json'))
t = d['tasks'][0]; eps = t['episodes']
print('n =', len(eps))
print('success =', sum(1 for e in eps if e['metrics']['success']))
print('distinct seeds =', len({e['seed'] for e in eps}))
print('errors =', sum(1 for e in eps if e.get('failure_reason')))
PY
```

预期：`n=50`、`success=46`、`distinct seeds=50`、`errors=0`。

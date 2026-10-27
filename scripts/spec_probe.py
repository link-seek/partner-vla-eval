#!/usr/bin/env python3
"""伙伴模型元信息自发现（v1）：输入一个 HF id，输出能读到的全部事实 + 仍需人答的问题。

只读元数据，不下权重：
- HF API：commits（取 main 最新 3 个）、config.json、*.safetensors.index.json、model card tags
- 推断：dtype（index.json）、候选动作维（各 family 的 action head 形状 heuristic）、家族归属（card tags/架构名）
- 读不到的（相机名/状态需求/chunk 语义）：明确标出，转 smoke 实测或问本人

用法：python3 scripts/spec_probe.py <hf-id> [--rev <commit>] [--token $HF_TOKEN]
"""
import json, sys, urllib.request, urllib.error

API = "https://huggingface.co/api/models/"

def _get(url, token=None):
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code}
    except Exception as e:
        return {"_error": str(e)[:120]}

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); return 1
    repo = sys.argv[1]
    token = None
    if "--token" in sys.argv:
        token = sys.argv[sys.argv.index("--token") + 1]
    rev = None
    if "--rev" in sys.argv:
        rev = sys.argv[sys.argv.index("--rev") + 1]

    print(f"## spec_probe: {repo}")
    meta = _get(API + repo, token)
    if "_http_error" in meta or "_error" in meta:
        print(f"- 仓库不可读：{meta}（私仓？先开权限）")
        return 2
    print(f"- card tags: {meta.get('tags', [])[:12]}")
    print(f"- gated: {meta.get('gated')}  private: {meta.get('private')}")
    sha = (meta.get("sha") or "")[:12]
    print(f"- main HEAD: {sha}")

    # commits（最新 3 个，供选 commit 用）
    commits = _get(API + repo + "/commits?limit=3", token)
    if isinstance(commits, list):
        print("- 最近 commits:")
        for c in commits[:3]:
            print(f"  {c.get('id','')[:12]} {c.get('date','')[:10]} {(c.get('title') or '')[:60]}")

    # config.json（架构、chunk 等各 family 自定义键，原样 dumping 关键段）
    cfg = _get(f"https://huggingface.co/{repo}/resolve/{rev or 'main'}/config.json", token)
    if isinstance(cfg, dict) and "_error" not in cfg and "_http_error" not in cfg:
        keep = {k: cfg[k] for k in cfg if any(s in k.lower() for s in ("architect", "chunk", "action", "horizon", "model_type", "dim", "policy"))}
        print(f"- config 架构键: {json.dumps(keep)[:300]}")
    else:
        print(f"- config.json: 读不到 {cfg}")

    # safetensors index（只读形状，不下权重）
    sibs = meta.get("siblings", []) or []
    idx = [s["rfilename"] for s in sibs if s.get("rfilename", "").endswith(".safetensors.index.json")]
    print(f"- index 文件: {idx[:3] or '无（单文件 safetensors 或其它格式，需整包看头）'}")
    for name in idx[:1]:
        j = _get(f"https://huggingface.co/{repo}/resolve/{rev or 'main'}/{name}", token)
        if isinstance(j, dict) and "weight_map" in j:
            wm = j["weight_map"]
            total = j.get("metadata", {}).get("total_size", "?")
            dtypes = {}
            act_keys = []
            for k in wm:
                # 粗扫：含 action/head/out 关键字的层
                kl = k.lower()
                if any(s in kl for s in ("action", "head", "out_proj", "policy_head")):
                    act_keys.append(k)
            print(f"  - 总大小: {total}；疑似动作相关层 {len(act_keys)} 个")
            for k in act_keys[:8]:
                print(f"    {k}")
        else:
            print(f"  - index 读失败：{str(j)[:100]}")

    print()
    print("## 仍需人答 / smoke 实测（机器读不到）")
    print("- 相机名、状态字段需求、chunk 语义、特殊依赖（requirements/model card 无则试）")
    print("- 最终口径以 smoke 实测为准（config.json 会撒谎，见 SmolVLA 6-D/7-D）")
    return 0

if __name__ == "__main__":
    sys.exit(main())

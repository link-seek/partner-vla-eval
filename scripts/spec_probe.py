#!/usr/bin/env python3
"""伙伴模型元信息自发现（v2）：输入 HF id 或本地目录，输出能读到的全部事实 + 仍需人答的问题。

只读元数据，不加载权重：
- HF id：HF API（commits 取 main 最新 3 个）、config.json、*.safetensors.index.json、model card tags
- 本地目录：config.json + 各 *.safetensors 文件头（形状/dtype，不读权重体）+ 子目录（分头情况）
- 推断：dtype、候选动作维（各 family 的 action head 形状 heuristic）、家族归属
- 读不到的（相机名/状态需求/chunk 语义）：明确标出，转 smoke 实测或问本人

用法：
  python3 scripts/spec_probe.py <hf-id> [--rev <commit>] [--token $HF_TOKEN]
  python3 scripts/spec_probe.py <本地目录>   # 伙伴给模型文件时用
"""
import json, os, struct, sys, urllib.request, urllib.error

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

def _act_keys(names):
    return [k for k in names if any(s in k.lower() for s in ("action", "head", "out_proj", "policy_head"))]


def _probe_local(path):
    print(f"## spec_probe(local): {path}")
    # config.json（有则读）
    cfg_path = os.path.join(path, "config.json")
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
        keep = {k: cfg[k] for k in cfg if any(s in k.lower() for s in ("architect", "chunk", "action", "horizon", "model_type", "dim", "policy"))}
        print(f"- config 架构键: {json.dumps(keep)[:300]}")
    except FileNotFoundError:
        print("- config.json: 无（按人答走）")
    except Exception as e:
        print(f"- config.json: 读失败 {str(e)[:100]}")
    # 分头：含权重文件的子目录
    subdirs = []
    for entry in sorted(os.listdir(path)):
        full = os.path.join(path, entry)
        if os.path.isdir(full) and not entry.startswith("."):
            try:
                files = os.listdir(full)
            except OSError:
                continue
            if any(fn.endswith(".safetensors") or fn == "config.json" for fn in files):
                subdirs.append(entry)
    if subdirs:
        print(f"- 子目录（疑似按 task 分头）: {subdirs}")
    else:
        print("- 子目录: 无（单仓通用权重）")
    # 各 safetensors 文件头（只读形状/dtype，不读权重体）
    sfs = sorted(fn for fn in os.listdir(path) if fn.endswith(".safetensors"))
    if not sfs:
        print("- safetensors: 顶层无（看子目录或其它格式：bin/pth 需整包看头）")
    total = 0
    seen_dtypes = {}
    for fn in sfs:
        full = os.path.join(path, fn)
        try:
            total += os.path.getsize(full)
            with open(full, "rb") as f:
                (n,) = struct.unpack("<Q", f.read(8))
                header = json.loads(f.read(n).decode())
        except Exception as e:
            print(f"  - {fn}: 头读失败 {str(e)[:100]}")
            continue
        header.pop("__metadata__", None)
        dtypes = {}
        for k, v in header.items():
            dtypes[v.get("dtype", "?")] = dtypes.get(v.get("dtype", "?"), 0) + 1
        for k in dtypes:
            seen_dtypes[k] = seen_dtypes.get(k, 0) + dtypes[k]
        keys = _act_keys(header.keys())
        print(f"  - {fn}: 张量 {len(header)} 个，dtype {dtypes}，疑似动作相关层 {len(keys)} 个")
        for k in keys[:8]:
            print(f"    {k} shape={header[k].get('shape')}")
    if sfs:
        print(f"- 合计大小: {total / 1e9:.1f}GB；dtype 分布 {seen_dtypes}")
    print()
    print("## 仍需人答 / smoke 实测（文件读不到）")
    print("- 版本：本地目录无 commits，精确版本靠交付时注明（文件夹哈希/时间/自述三选一）")
    print("- 相机名、状态字段需求、chunk 语义、特殊依赖")
    print("- 最终口径以 smoke 实测为准（文件头会撒谎，见 SmolVLA 6-D/7-D）")
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); return 1
    repo = sys.argv[1]
    if os.path.isdir(repo):
        return _probe_local(repo)
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

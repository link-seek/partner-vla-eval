# docker/ 目录规则（就近文档，不进公开站点）

## 现状：10 个 Dockerfile → 15 个 tag

同一 Dockerfile 靠 `build-arg` / `POLICY` 出多个 tag，这是常态：

| Dockerfile | 出几个 | tag |
|---|---|---|
| `Dockerfile.robotwin-slim` | 1 | `vla-eval-robotwin:0.8.0-ee-slim`（考场基座，11.3G） |
| `Dockerfile.robotwin-unified` | 1 | `vla-eval-robotwin:0.8.0`（全量，28.7G） |
| `Dockerfile.serve-xvla` | 2 | `-ee16` / `-fp16` |
| `Dockerfile.serve-cogact` | 3 | 基础 / `-fp32` / `-fp32-2gpu` |
| `Dockerfile.serve-robotwin` | 2 | `POLICY=act` / `POLICY=dp`（自建适配器） |
| `Dockerfile.serve-pi0` / `serve-pi05` / `serve-smolvla` | 各 1 | — |
| `Dockerfile.verify` | 1 | `vla-verify:0.1` |
| `Dockerfile.payload` | 2 | `vla-payload:<sha>` + `:latest` |

**唯一清单**：`configs/registry/image-registry.json`（15 条，含 digest / kind / status / 来源 Dockerfile）。
准确数量以 SWR 为准，不以 Dockerfile 为准——历史 tag 不会自动消失。
门禁：`scripts/gates/check_images.py`（静态一致性）；加 `--remote` 可逐个向 SWR 解析 digest 比对。
查法：`docker buildx imagetools inspect <ref> --format '{{.Manifest.Digest}}'`。

## 三条硬规则

1. **tag 不可变**：同 tag 不许指向不同 digest（`build-serve.yml` 有守卫，默认红；`force_retag=true` 才放行）
2. **digest 只从 `buildx imagetools inspect` 取**，不许用 `docker manifest inspect` 里的 `config.digest`
   （后者是配置层 blob，拿去做 `FROM image@digest` 会报 `unexpected media type`）
3. **V100 上禁止构建/装包**：镜像只在有外网的机器/runner 上构建，V100 只从 SWR 内网拉

## registry 与镜像的关系

`configs/registry/model-registry.json` 记录**被引用的** serve 镜像（`serve_image` + `serve_image_digest`）。
未登记的 tag（变体、工具）不是"不存在"，只是"当前没被评测引用"——
要让 registry 成为唯一清单，需要把全部 15 个 tag 补登记（见治理待办）。

## 构建在哪跑

- **常规**：GitHub runner（`build-serve.yml`，免费机）
- **robotwin 基座**：基座 11.3G，跨境拉取慢；实测在 0002 本机构建（镜像已在本地）只需 6~11 秒
- 无论在哪构建，**只有 digest 是身份**，tag 只是别名

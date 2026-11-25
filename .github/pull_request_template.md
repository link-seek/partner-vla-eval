## 这个 PR 属于哪一类

- [ ] 1 烧卡产物（报告/榜单/逐集记录）
- [ ] 2 基础设施（镜像/脚本/workflow/配置）
- [ ] 3 文档教程（教程/ADR/参考）
- [ ] 4 仓库流程（本模板/CONTRIBUTING/CODEOWNERS）

## 改了什么

<!-- 一两句话。改了基础设施要写"为什么不能不做" -->

## 怎么验的（必填，证据优先于描述）

- [ ] 本地：`python3 scripts/gates/run_all.py` 通过
- [ ] CI：`lint` / `actionlint` / `secret-hygiene` 绿

## 分类相关的额外要求

- [ ] **第 1 类**：给出 run id 或 aggregate 路径；数字不是手写的
  - run id / 路径：
- [ ] **第 2 类 镜像**：`registry` 的 digest 用 `docker buildx imagetools inspect` 取，不是 `docker inspect | sed`
  - 镜像与 digest：
- [ ] **第 2 类 workflow**：已在 `scripts/gates/infra-inventory.json` 登记 `kind`
- [ ] **第 3 类**：`title` + `parent`（或 `nav_exclude: true`）；过程记录没有写成 md
- [ ] **凭证**：没有新增字面 IP / 密钥；新键只出现在 `.env.example`

## 回滚方式

<!-- 默认 revert；有特殊顺序要求的写清 -->

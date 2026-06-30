# Waydroid OTA Repo

Waydroid OTA manifest 转换器 MVP。目标是把上游 manifest 解析、校验并重写为适合本地发布目录、GitHub Pages + Releases、Nexus Raw Hosted、以及可直接作为 Nexus Raw Proxy Remote URL root 的静态仓库结构。

## 当前能力

- 解析 fixture manifest 或真实上游 Waydroid OTA manifest
- 校验每个 artifact 的 `sha256` 与 `size`
- 复用本地 cache，必要时通过 `httpx2` 流式下载
- 将 manifest 中 artifact URL 重写为本地模式、GitHub 模式、Nexus Raw Hosted URL 骨架，或 raw-proxy-root 模式
- 输出版本化 release 目录与 `latest` 指针
- 兼容更接近 Waydroid/OTA API 的 `response[]` fixture 形状
- 显式区分 system/vendor 上游源
- 提供离线单元/集成测试
- 提供 GitHub Actions lint/test 与 production-oriented publish 草案

## 快速开始

```bash
uv sync
uv run ruff check .
uv run basedpyright
uv run pytest
uv run waydroid-ota-repo tests/fixtures/upstream_manifest.json \
  --cache-dir tests/fixtures/cache \
  --dist-dir .tmp/local-dist \
  --publisher-config examples/github.publisher.json

uv run waydroid-ota-repo tests/fixtures/upstream_manifest_waydroid.json \
  --cache-dir tests/fixtures/cache \
  --dist-dir .tmp/local-dist-waydroid \
  --publisher-config examples/nexus_raw.publisher.json

uv run waydroid-ota-repo tests/fixtures/upstream_manifest_waydroid.json \
  --cache-dir tests/fixtures/cache \
  --dist-dir .tmp/local-dist-proxy-root \
  --publisher-config examples/raw_proxy_root.publisher.json

uv run waydroid-ota-repo \
  --upstream-config examples/upstream.sources.json \
  --cache-dir cache \
  --dist-dir .tmp/local-dist-upstream \
  --publisher-config examples/raw_proxy_root.publisher.json
```

## CLI

```bash
uv run waydroid-ota-repo MANIFEST_JSON \
  --cache-dir cache \
  --dist-dir dist \
  --publisher-mode local \
  --publisher-value dist
```

也可以通过 `--publisher-config` 传入 `examples/*.json`。

### 真实上游发布模式

通过 `--upstream-config` 进入真实上游发布模式：

- `--upstream-config` 传入 system/vendor 两路 manifest URL
- 保持默认测试链离线，不把真实网络依赖混进默认 `pytest`
- artifact URL 必须是绝对 HTTP(S) URL；相对 URL 会在模型校验阶段失败
- 下载落盘先写 `.part` 临时文件，校验 hash/size 后再原子替换，避免明显缓存损坏

`examples/upstream.sources.json` 展示了生产配置结构。

说明：

- 真实 Waydroid 上游的 system 与 vendor channel 语义本来就可能不同，例如 `VANILLA` 与 `MAINLINE`。
- 生产发布时可以通过 `published_channel` 统一对外暴露为 `stable` 这类发布 channel，避免把上游 system/vendor 内部差异直接透出到最终 OTA 入口。

## 输出约定

- `dist/manifest.json`: latest 指针 manifest
- `dist/latest.json`: latest release 元数据索引
- `dist/releases/index.json`: 所有已发布版本索引
- `dist/releases/<version>/manifest.json`: 版本化 manifest
- `dist/releases/<version>/artifacts/*`: 版本化 artifact
- `dist/latest/artifacts/*`: latest 指针 artifact

### Release 元数据语义

- `manifest.json` 始终表示“当前 latest 版本的 manifest 内容”
- `latest.json` 与 `releases/index.json` 提供显式元数据：
  - `latest_version`
  - `latest_manifest_url`
  - `releases[]`
- `releases[]` 中每一项至少包含：
  - `version`
  - `manifest_url`

这让静态仓库既能被直接消费 latest manifest，也能被上层脚本显式发现所有版本。

## Manifest 兼容说明

- 原始 MVP fixture 使用 `artifacts[]`
- 现在兼容 Waydroid 风格 `response[]`，并自动归一化：
  - `filename -> name`
  - `id -> sha256`
  - `response[0].version -> version`
  - `response[0].romtype -> channel`
- 未知字段会保留，并在 URL 重写后继续出现在输出 manifest 中

## Publisher 示例

- `examples/local.publisher.json`
- `examples/github.publisher.json`
- `examples/nexus_raw.publisher.json`
- `examples/raw_proxy_root.publisher.json`
- `examples/upstream.sources.json`

当前 Nexus 支持仍仅实现离线 URL 渲染骨架，不执行真实上传。

## Raw Proxy Root 输出

当 publisher 为 `raw_proxy_root` 时，除了保留现有 release/latest 元数据输出外，还会额外生成适合作为静态 HTTP 根目录的 Waydroid 兼容结构：

- `dist/system/stable.json`
- `dist/system/latest.json`
- `dist/system/versions/<version>.json`
- `dist/system/artifacts/*`
- `dist/vendor/stable.json`
- `dist/vendor/latest.json`
- `dist/vendor/versions/<version>.json`
- `dist/vendor/artifacts/*`

这些 JSON 使用 Waydroid 风格 `response[]`：

- `filename`
- `id`
- `romtype`
- `url`
- `version`
- `size`
- 以及原始 artifact 中可透传的字段

因此可以直接把生成目录挂到静态 HTTP 服务下，再作为 Nexus Raw Proxy 的 Remote URL root。

## GitHub Pages 部署

仓库内置 `.github/workflows/publish.yml`，使用 GitHub 官方 Pages 流程：

- `actions/configure-pages`
- `actions/upload-pages-artifact`
- `actions/deploy-pages`

该工作流会通过 `publish-upstream` 读取真实 upstream source 配置，生成 `raw_proxy_root` 输出并把 `dist/` 部署到 GitHub Pages。

默认 Pages 根 URL 形如：

- `https://spark-liang.github.io/Waydroid-OTA-Repo`

部署后，关键路径应为：

- `https://spark-liang.github.io/Waydroid-OTA-Repo/system/stable.json`
- `https://spark-liang.github.io/Waydroid-OTA-Repo/vendor/stable.json`
- `https://spark-liang.github.io/Waydroid-OTA-Repo/system/artifacts/system.img`
- `https://spark-liang.github.io/Waydroid-OTA-Repo/vendor/artifacts/vendor.img`

如果仓库 Pages 之前未启用，需要在 GitHub 仓库设置中允许 GitHub Actions 作为 Pages source。

## 多版本行为

- 重复对同一 `dist/` 转换不同版本时：
  - 历史 `dist/releases/<version>/` 会保留
  - `dist/manifest.json` 会指向最新一次转换的版本
  - `dist/latest.json` 与 `dist/releases/index.json` 会同步更新 latest 元数据

## 测试与生产分轨

- `waydroid-ota-repo <manifest>`：fixture / 本地文件入口，继续用于离线测试
- `waydroid-ota-repo --upstream-config ...`：真实上游入口，适合生产发布或本地 mock upstream 验证
- 默认 `pytest` 全离线；新增生产路径测试使用 mocked upstream client，不访问真实网络

当前版本故意不实现 APT proxy、Web UI、数据库或在线测试依赖。

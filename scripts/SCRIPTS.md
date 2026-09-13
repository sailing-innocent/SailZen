# Helpful Scripts

## generate_body_metrics.py — 内置身体指标注册表代码生成

`config/body_metrics.toml` 是内置身体指标（BUILTIN_METRICS）的**单一权威**。
三端 + mock 的注册表镜像均由该文件代码生成，不要手工同步多份清单：

- `sail_server/application/dto/body_data.py`（后端）
- `site/src/lib/data/body_data.ts`（site 前端）
- `android/app/src/main/java/com/sailzen/app/core/network/dto/BodyDataDtos.kt`（Android）
- `site/mock/server.js`（mock，仅开发用）

```bash
# 修改 config/body_metrics.toml 后重新生成四处镜像
uv run python scripts/generate_body_metrics.py

# 校验生成物是否最新（tests/unit/test_body_metrics_codegen.py 也会强制执行）
uv run python scripts/generate_body_metrics.py --check
```

生成块位于各文件的 `BEGIN/END GENERATED BODY METRICS` 标记之间，请勿手改；
`tests/unit/test_body_metrics_codegen.py` 保证生成物与配置永远同步。

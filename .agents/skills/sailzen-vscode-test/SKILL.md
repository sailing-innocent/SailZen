---
name: sailzen-vscode-test
description: "[已归档提示] 旧版 Dendron 衍生插件 packages/vscode_plugin 已归档至 archive/dendron_legacy/，新版 VS Code 插件开发、测试与 OTA 发布请使用 sailzen-workbench-dev 技能。"
---

# [已归档] SailZen 旧版 VSCode 插件测试说明

> **迁移提示（2026-11-28）**：旧版基于 Dendron 衍生的 `packages/vscode_plugin/` 及关联 7 包已整体归档至 `archive/dendron_legacy/`，请勿再对其开发或执行 `pnpm run test:vscode-plugin`。

新版单扩展工作台位于 `packages/sailzen-workbench/`，完整的开发、Jest 单元测试、VSIX 打包与云端 OTA 发布流程请阅读并使用 **[sailzen-workbench-dev](../sailzen-workbench-dev/SKILL.md)**：

```powershell
pnpm --filter=sailzen-workbench run typecheck
pnpm run test:workbench
pnpm run package-workbench
```

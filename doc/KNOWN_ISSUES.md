# Known Issues

## 第三方库问题

### remark-variables@1.4.9 - 变量未定义

**影响**: Markdown 解析功能  
**状态**: ✅ 已修复（通过 globalThis polyfill）

```typescript
// Workaround in extension.ts
(globalThis as any).actual = undefined;
(globalThis as any).val = undefined;
```

### Jest 依赖警告

```
WARN  2 deprecated subdependencies found: glob@7.2.3, inflight@1.0.6
```

**原因**: @jest/core 未升级  
**状态**: ⏳ 等待上游更新（不影响功能）

---

## Console Warnings

### DendronSideGraphPanel 未注册

**影响**: 控制台警告，Graph 面板无法渲染  
**修复**: 需在 dendron_plugin_views/src/index.tsx 注册组件  
**状态**: ⏳ 待实现

---

*Last updated: 2026-02*

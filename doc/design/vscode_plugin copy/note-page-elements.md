# Note Page Elements（笔记页面元素）

> 状态：底层接口已实现（`@saili/unified`）。渲染面：Note Preview（引擎 HTML 渲染管线），同时自动覆盖 hover preview / publishing。
> 代码位置：`packages/unified/src/remark/pageElements/`

## 1. 需求

为每一篇可管理的 Markdown note 提供**动态注入的页面区域**：

- **顶部区域**：frontmatter（metadata）之下、正文之上
- **底部区域**：所有可编辑内容之下
- 更一般地：一个**内部特殊符号关键词 → 内部特殊页面元素**的映射接口，元素内容在渲染时由 provider 动态计算，后续可基于 note 内容做 query（典型场景：通过当前日期 query 天气预报）
- 元素内容**不写回源文件**，源文件只保留 marker；默认内容为使用帮助（help）

## 2. 语法：XML 自定义元素

> **历史决策**：初版使用 `$$KEY$$` 语法，但与 LaTeX 数学语法（remark-math / katex）冲突——katex 启用时未注册 marker 会被当作公式渲染。因此重新设计为 XML 自定义元素语法：**通用 markdown 渲染器（GitHub、无插件编辑器）会将未知标签回退为普通元素**，自闭合形式渲染为空，成对形式显示内部 fallback 内容，天然优雅降级。

marker 必须是**独立的块级元素**（独占段落；成对形式的开放标签需独占一行，遵循 CommonMark raw-html-block 规则）：

```markdown
---
id: xxx
title: My Note
updated: ...
created: ...
---

<sail-elem key="PREFIX" />

正文内容……

<sail-elem key="POSTFIX" />
```

三种形式：

```markdown
<!-- 1. 自闭合（推荐） -->
<sail-elem key="WEATHER" city="hangzhou" day="0" />

<!-- 2. 成对带 fallback：provider 可通过 ctx.fallback 拿到内部内容；
        通用渲染器 / 未注册时会原样显示内部内容 -->
<sail-elem key="WEATHER" city="hangzhou">
天气加载中…
</sail-elem>

<!-- 3. 属性写法：双引号 / 单引号 / 无引号 / 布尔属性（值为 "true"） -->
<sail-elem key='FOO' level=2 detailed />
```

规则：

- 标签名固定为 `sail-elem`（带连字符，符合自定义元素惯例，不与真实 HTML 标签冲突）
- `key` 属性必需，值必须匹配 `[A-Z][A-Z0-9_]{0,63}`（全大写标识符）
- 除 `key` 外的所有属性成为命名参数，解析为 `PageElementArgs`（`{ _: [], ...named }`）
- **只有已在 registry 注册的 key 才会被转换**；未注册 marker 原样透传为 raw HTML（等价于通用渲染器的 fallback 行为）
- 段落/标题内联出现的标签不转换（页面元素按设计是块级区域）

## 3. 架构

```
note.body (含 <sail-elem .../> marker)
   │  remark-parse: marker 是 raw `html` 节点（不触发任何 Sail/数学语法）
   ▼  SailEngine._renderNote → MDUtilsV5.procRehypeFull (async proc.process)
pageElements transformer
   │  ├─ Pass 1: html 节点 → parseSailElem → PageElement AST 节点
   │  │         （所有模式，开销仅为一次标签名测试 + 属性解析）
   │  └─ Pass 2: 仅 dest=HTML 且 mode=FULL 时，await registry.render(key, ctx)
   │            结果挂到 node.data.hName/hProperties/hChildren
   ▼
remark-rehype (allowDangerousHtml) → rehype-raw
   ▼
<div class="sail-page-element sail-page-element-{key}" data-page-element="{KEY}">
  ...provider HTML...
</div>
   │
   ▼  ON_DID_CHANGE_ACTIVE_TEXT_EDITOR → webview
Note Preview (SailNote, dangerouslySetInnerHTML)
```

关键性质：

- **零语法冲突**：marker 在 markdown 层面就是 raw HTML，与 LaTeX、wikilink、`::` 指令等所有 Sail 语法完全正交
- **Round-trip 安全**：插件注册了 toMarkdown handler，parse → stringify 还原原始 marker（`PreviewPanel.rewriteImageUrls` 等 parse/stringify 流程不受影响）
- **零开销路径**：decorations 扫描、refactor 等只用 `proc.parse` 的流程完全不触发 provider 渲染
- **错误隔离**：provider 抛错渲染为非致命错误框，不会中断整篇 note 的渲染
- **优雅降级**：未注册 key / 无插件环境下，marker 按未知 HTML 元素处理（自闭合渲染为空；成对形式显示 fallback 内容）

## 4. 扩展 API

### 4.1 Provider

```typescript
import { NotePageElementProvider } from "@saili/unified";

const weatherProvider: NotePageElementProvider = {
  key: "WEATHER",                    // 大写 key
  title: "Weather Forecast",         // help 中展示的名称
  description: "根据笔记日期查询天气", // help 中展示的描述
  usage: '<sail-elem key="WEATHER" city="hangzhou" />',
  cacheTtlMs: 30 * 60 * 1000,        // 可选：按 (note, key, args) 缓存结果
  render: async (ctx) => {
    // ctx: { note, key, args, raw, fallback?, fname, vault, vaults, wsRoot, config, flavor }
    const city = ctx.args.city ?? "hangzhou";
    try {
      const forecast = await queryWeather(city, ctx.note.created);
      return `<span>🌤 ${forecast}</span>`;   // 返回 HTML 字符串
    } catch {
      return `<span>${ctx.fallback ?? "天气未知"}</span>`;  // 利用成对形式的 fallback
    }
  },
};
```

### 4.2 注册

```typescript
import { getDefaultPageElementRegistry } from "@saili/unified";

// 在扩展/engine 启动时注册一次即可，之后所有渲染生效
getDefaultPageElementRegistry().register(weatherProvider);

// 覆盖内置 help provider，为 PREFIX 注入真实内容
getDefaultPageElementRegistry().register(prefixProvider, { override: true });
```

也可以给单个 processor 传独立 registry（测试/隔离场景）：

```typescript
proc.use(pageElements, { registry: myRegistry });
```

### 4.3 内置元素

| Marker | 说明 |
|--------|------|
| `<sail-elem key="PREFIX" />` | 顶部区域占位，默认渲染 help（注册表概览） |
| `<sail-elem key="POSTFIX" />` | 底部区域占位，默认渲染 help |
| `<sail-elem key="HELP" />` | 始终渲染 help（列出全部已注册元素与用法） |

## 5. 性能与缓存

- **Pass 1 开销**：每个 html 节点一次标签名测试；无 marker 的 note 零额外开销
- **Provider 缓存**：provider 声明 `cacheTtlMs` 后，registry 按 `(key, note.id, note.contentHash, args)` 缓存 HTML；note 编辑（contentHash 变化）自动失效
- **引擎渲染缓存**：`SailEngine.renderNote` 以 `note.updated/contentHash` 为键缓存整篇 HTML。时间敏感内容（如天气）应通过 provider 的 `cacheTtlMs` 控制重渲染成本，并依赖 note 编辑触发整体刷新；后续如需"定时刷新"，可在 PreviewPanel 层对 page element 做增量刷新（见第 7 节）
- **并发渲染**：同一 note 中多个 marker 的 provider 渲染通过 `Promise.all` 并发执行

## 6. 输出契约

渲染产物统一包裹：

```html
<div class="sail-page-element sail-page-element-prefix" data-page-element="PREFIX">
  <!-- provider HTML -->
</div>
```

webview / 发布端可以用 `.sail-page-element` 选择器追加全局样式；provider HTML 内的 inline style 优先级更高。内置 help 使用 `var(--vscode-*, fallback)` 主题变量，VSCode webview 中自动适配深浅色，且示例 marker 全部经 HTML 转义（不会被误解析为真实元素）。

## 7. Demo：Daily Journal 天气卡片

> 实现位置：`packages/vscode_plugin/src/features/pageElements/weatherPageElement.ts`，在扩展激活时注册（`_extension.ts`）。

演示了本接口的两种扩展方式：

1. **`WEATHER` provider**：`<sail-elem key="WEATHER" />` 显式插入天气卡片
2. **`PREFIX` override（笔记感知）**：渲染时检测 fname，若为 daily journal（`journal.daily.YYYY.MM.DD`）则顶部区域自动显示天气卡片，其他笔记保持默认 help —— 即“根据笔记的项目/类型补充额外信息”的完整路径

技术要点：

- 数据源：**Open-Meteo**（`api.open-meteo.com`，免费、无需 API key、JSON），一次请求同时拿 `current` 实时天气与 `daily` 当日高低温
- 城市硬编码：杭州 / 上海 / 合肥（坐标见 `WEATHER_CITIES`）
- 三级缓存：provider `cacheTtlMs`（registry 级）→ 模块级共享缓存 `WEATHER_CACHE_TTL_MS`（所有笔记 30 分钟内共享一次查询）→ 引擎整篇渲染缓存（note.updated）
- 健壮性：单城市失败降级为该行“获取失败”；全部失败时优先显示成对 marker 的 `ctx.fallback`；请求带 10s `AbortController` 超时
- WMO weather code → emoji + 中文描述映射（`WMO_MAP`）

后续可将城市列表移到 workspace config（如 `sail.yaml` 的 `weather.cities`），或按笔记 frontmatter 的 `city` 字段动态查询。

## 8. 后续规划

1. **项目感知内容**：provider 依据 `ctx.note.fname`（如 `project.*` 命名空间）注入项目状态、任务摘要
2. **天气/日期 query provider**：基于 `ctx.note.created/updated` 或 `ctx.args` 调用外部 API（`cacheTtlMs` 控制频率，失败时回退 `ctx.fallback`）
3. **webview 侧增量刷新**：对带 `data-page-element` 的 div 做局部消息刷新，绕过整篇重渲染与引擎缓存，支持实时性强的元素
4. **与 decorations 体系打通**：编辑器内可在 marker 行旁以 decoration 提示元素状态（可编辑区内的"幽灵文本"，与本功能的 preview 渲染互补）
5. **参数位置语法**：`PageElementArgs._` 目前恒为空，为未来可能的简写形式（如 `<sail-elem key="WEATHER" _="hangzhou" />` 或别名属性）预留

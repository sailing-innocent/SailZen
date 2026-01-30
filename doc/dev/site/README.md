# 前端开发文档

> SailZen 前端项目开发指南

## 1. 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19.x | UI 框架 |
| TypeScript | 5.x | 类型安全 |
| Vite | 7.x | 构建工具 |
| React Router | 7.x | 路由管理 |
| Zustand | 5.x | 状态管理 |
| Radix UI | - | 无障碍 UI 组件 |
| Tailwind CSS | 4.x | 样式框架 |
| TanStack Table | 8.x | 数据表格 |
| TanStack Virtual | 3.x | 虚拟化列表 |
| Recharts | 3.x | 图表可视化 |
| date-fns | 4.x | 日期处理 |
| Lucide React | - | 图标库 |
| Jest | 30.x | 单元测试 |

## 2. 项目结构

```
packages/site/
├── src/
│   ├── pages/              # 页面组件
│   │   ├── main.tsx        # 主页（待办任务列表）
│   │   ├── money.tsx       # 财务管理
│   │   ├── health.tsx      # 健康管理
│   │   ├── project.tsx     # 项目管理
│   │   ├── content.tsx     # 历史事件管理
│   │   └── text.tsx        # 文本内容管理
│   │
│   ├── components/         # 组件
│   │   ├── ui/             # 基础 UI 组件（Radix + Tailwind）
│   │   ├── *_dialog.tsx    # 对话框组件
│   │   ├── *_data_table.tsx # 数据表格组件
│   │   └── *.tsx           # 业务组件
│   │
│   ├── lib/
│   │   ├── api/            # API 调用层
│   │   │   ├── config.ts   # API 配置（SERVER_URL）
│   │   │   ├── money.ts    # 财务 API
│   │   │   ├── project.ts  # 项目 API
│   │   │   ├── health.ts   # 健康 API
│   │   │   ├── history.ts  # 历史事件 API
│   │   │   └── text.ts     # 文本内容 API
│   │   │
│   │   ├── data/           # 数据类型定义
│   │   │   ├── money.ts    # 财务数据类型
│   │   │   ├── project.ts  # 项目数据类型
│   │   │   ├── health.ts   # 健康数据类型
│   │   │   ├── history.ts  # 历史事件数据类型
│   │   │   └── text.ts     # 文本数据类型
│   │   │
│   │   ├── store/          # Zustand 状态管理
│   │   │   ├── index.ts    # 服务器健康状态
│   │   │   ├── money.ts    # 财务 Store
│   │   │   ├── project.ts  # 项目 Store
│   │   │   ├── health.ts   # 健康 Store
│   │   │   └── history.ts  # 历史事件 Store
│   │   │
│   │   └── utils/          # 工具函数
│   │       ├── index.ts    # cn() 类名工具
│   │       ├── money.ts    # 金额计算 Money 类
│   │       ├── qbw_date.ts # 季度双周日期工具
│   │       └── cache.ts    # 数据缓存工具
│   │
│   ├── hooks/              # 自定义 Hooks
│   │   ├── use-mobile.tsx  # 移动端检测
│   │   ├── use-debounce.ts # 防抖
│   │   └── use-in-view.ts  # 视口检测
│   │
│   ├── config/             # 配置
│   │   └── basic.ts        # 基础配置
│   │
│   ├── App.tsx             # 应用入口（路由配置）
│   └── main.tsx            # 渲染入口
│
├── public/                 # 静态资源
├── .env.template           # 环境变量模板
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## 3. 开发指南

### 3.1 环境配置

```bash
# 复制环境变量模板
cp .env.template .env

# 编辑 .env 文件，设置后端服务器地址
VITE_SERVER_URL=http://localhost:8000
```

### 3.2 启动开发服务器

```bash
# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev
```

### 3.3 构建生产版本

```bash
pnpm build
```

### 3.4 运行测试

```bash
pnpm test
```

## 4. 架构模式

### 4.1 分层架构

```
Pages（页面层）
    ↓
Components（组件层）
    ↓
Store（状态层，Zustand）
    ↓
API（接口层）
    ↓
Data（数据类型层）
```

### 4.2 状态管理约定

- 使用 Zustand 管理全局状态
- 每个功能模块独立 Store
- Store 中包含：数据状态、加载状态、操作方法

```typescript
// 示例 Store 结构
interface ExampleStore {
  // 数据状态
  items: ItemData[]
  isLoading: boolean
  
  // 操作方法
  fetchItems: () => Promise<void>
  createItem: (data: CreateProps) => Promise<void>
  updateItem: (id: number, data: UpdateProps) => Promise<void>
  deleteItem: (id: number) => Promise<void>
}
```

### 4.3 API 调用约定

- API 函数以 `api_` 前缀命名
- 使用 `fetchJson` 封装请求
- 返回 Promise 类型

```typescript
// 示例 API 函数
export async function api_get_items(): Promise<ItemData[]> {
  return fetchJson(`${get_url()}/items/`)
}
```

## 5. 组件开发规范

### 5.1 UI 组件

基于 Radix UI + Tailwind CSS 的组件位于 `components/ui/`：

- `button.tsx` - 按钮
- `card.tsx` - 卡片
- `dialog.tsx` - 对话框
- `input.tsx` - 输入框
- `select.tsx` - 选择框
- `table.tsx` - 表格
- `tabs.tsx` - 标签页
- 等等...

### 5.2 业务组件命名

- 对话框：`*_dialog.tsx`（如 `mission_add_dialog.tsx`）
- 数据表格：`*_data_table.tsx`（如 `transactions_data_table.tsx`）
- 卡片：`*_card.tsx`（如 `mission_card.tsx`）

### 5.3 响应式设计

使用 `useIsMobile()` Hook 检测移动端：

```tsx
const isMobile = useIsMobile()

return (
  <div className={isMobile ? 'p-4' : 'p-6'}>
    {/* 响应式内容 */}
  </div>
)
```

## 6. 路由结构

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | MainPage | 主页，待办任务列表 |
| `/money` | MoneyPage | 财务管理 |
| `/health` | HealthPage | 健康管理 |
| `/project` | ProjectPage | 项目管理 |
| `/content` | ContentPage | 历史事件管理 |
| `/text` | TextPage | 文本内容管理 |

## 7. 相关文档

- [移动端适配](./mobile_adapt.md) - 移动端适配问题和解决方案
- [性能分析](./perf_analysis.md) - 性能分析框架
- [性能优化](./performance.md) - 性能问题和优化建议


# SailZen 代码重构计划

## 当前问题诊断

### 1. 后端架构问题

#### 1.1 Controller 过度拆分（高优先级）
**问题**：analysis 功能被拆分成 10+ 个 Controller，分布在 5 个文件中
- `analysis.py` - 7 个 Controller（TextRange, Evidence, Stats, Task, Progress, Result, LLMProvider）
- `analysis_llm.py` - 4 个 Controller（TaskExecution, PromptTemplate, PromptExport, LLMConfig）
- `outline_extraction.py` - 1 个 Controller
- `character_detection.py` - 1 个 Controller
- `setting_extraction.py` - 1 个 Controller

**影响**：
- 路由管理复杂，`analysis_router` 需要导入 12 个 Controller
- 代码分散，相关功能难以维护
- 重复代码（DTO 定义、错误处理等）

**重构方案**：
```
sail_server/controller/
├── analysis/
│   ├── __init__.py          # 统一导出
│   ├── base.py              # 共享 DTO、工具函数
│   ├── text_range.py        # TextRangeController
│   ├── evidence.py          # EvidenceController
│   ├── task.py              # 合并 Task + Progress + Result + LLM
│   └── extraction.py        # 合并 outline + character + setting extraction
└── [其他保持独立的 controller]
```

#### 1.2 Agent 系统重复（高优先级）
**问题**：存在三套 Agent 系统
- `sail_server/agent/` - 基础 Agent 框架
- `sail_server/model/agent/` - Agent runner/scheduler
- `sail_server/model/unified_agent.py` - Unified Agent
- `sail_server/router/agent.py` + `unified_agent.py` - 两套路由

**影响**：
- 概念混淆，开发者不知道该用哪套
- 代码重复，维护困难
- unified_agent 试图整合但增加了复杂度

**重构方案**：
- 保留 `unified_agent` 架构（更完整）
- 将 `agent/` 和 `model/agent/` 的功能合并到 `unified_agent`
- 删除旧的路由，只保留 `unified_agent.py`

#### 1.3 数据层混乱（中优先级）
**问题**：
- `data/` 和 `model/` 目录职责不清
- `data/analysis.py` 包含数据类型定义（应该叫 schemas/types）
- `service/` 和 `controller/` 边界模糊

**重构方案**：
```
sail_server/
├── schemas/                 # Pydantic/Dataclass 类型定义
│   ├── analysis.py
│   ├── text.py
│   └── ...
├── models/                  # SQLAlchemy ORM 模型
│   ├── analysis/
│   ├── text/
│   └── ...
├── services/                # 业务逻辑层
│   ├── analysis/
│   │   ├── text_range.py
│   │   ├── extraction.py    # 合并提取服务
│   │   └── ...
│   └── base.py              # 服务基类
└── controllers/             # 只负责 HTTP 协议处理
    └── analysis.py          # 合并后的 Controller
```

#### 1.4 缓存/状态管理碎片化（中优先级）
**问题**：
- `extraction_cache.py` - 大纲提取检查点
- `outline_extraction.py` 中的 `_outline_extraction_tasks` - 任务状态
- `unified_scheduler.py` - 统一调度器状态
- 多套持久化机制

**重构方案**：
- 统一使用 `unified_scheduler` 的任务管理
- 提取通用的检查点/恢复机制到 `services/checkpoint.py`
- 大纲提取使用统一的任务系统，不要单独管理状态

### 2. 前端架构问题

#### 2.1 类型定义冗长（高优先级）
**问题**：`packages/site/src/lib/data/analysis.ts` 有 850+ 行类型定义
- 大量重复的模式（id, created_at, updated_at）
- 缺乏基础类型的复用
- 类型和 API 混在一起

**重构方案**：
```typescript
// lib/schemas/base.ts
export interface BaseEntity {
  id: string
  created_at: string
  updated_at?: string
}

export interface BaseEditionEntity extends BaseEntity {
  edition_id: number
}

// lib/schemas/analysis.ts
export interface Outline extends BaseEditionEntity {
  title: string
  outline_type: OutlineType
  // ...
}

// 使用代码生成工具从后端 schema 生成 TypeScript 类型
// 或至少保持结构一致
```

#### 2.2 API 层重复代码（高优先级）
**问题**：`packages/site/src/lib/api/analysis.ts` 有 1000+ 行
- 每个 API 函数重复 error handling
- 重复构造 URL
- 缺乏请求/响应拦截器

**重构方案**：
```typescript
// lib/api/client.ts
class APIClient {
  private baseURL: string
  
  async request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseURL}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      throw new APIError(response.statusText, errorText)
    }
    return response.json()
  }
  
  get<T>(path: string) { return this.request<T>(path) }
  post<T>(path: string, body: unknown) { 
    return this.request<T>(path, { method: 'POST', body: JSON.stringify(body) })
  }
  // ...
}

// lib/api/analysis.ts - 精简后
export const analysisAPI = {
  // Text Range
  previewRange: (data: TextRangeSelection) => 
    client.post<TextRangePreview>('/analysis/range/preview', data),
  
  // Outlines
  getOutlines: (editionId: number) => 
    client.get<Outline[]>(`/analysis/outline/edition/${editionId}`),
  
  // ...
}
```

#### 2.3 组件过度拆分（中优先级）
**问题**：`components/` 目录有大量小组件
- `analysis/` 目录有 6 个组件
- 每个 dialog 都是单独文件
- 很多组件只有 100 行左右

**重构方案**：
```
components/
├── features/               # 功能模块（按业务组织）
│   ├── analysis/
│   │   ├── index.ts
│   │   ├── OutlinePanel.tsx
│   │   ├── CharacterPanel.tsx
│   │   └── components/     # 内部组件
│   │       ├── dialogs/    # 所有 dialog 放在一起
│   │       ├── cards/
│   │       └── forms/
│   └── ...
├── ui/                     # 基础 UI 组件（保持不变）
└── layouts/
```

#### 2.4 Store 分散（低优先级）
**问题**：Zustand store 可能分散在多个文件中
**方案**：按功能模块组织 store

### 3. 前后端数据不一致（高优先级）

**问题**：
- 后端用 dataclass/pydantic，前端用 interface，命名不一致
- 后端 `snake_case`，前端 `camelCase` 转换不一致
- 类型重复定义，容易不同步

**重构方案**：
- 使用工具从 Python schema 生成 TypeScript 类型
- 或建立映射表确保一致性
- API 层统一处理命名转换

## 重构实施计划

### Phase 1: 建立基础架构（1-2 周）

#### 后端
1. [ ] 创建 `schemas/` 目录，将 `data/` 中的类型定义迁移
2. [ ] 创建基础 APIClient 类，统一错误处理
3. [ ] 定义 Service 基类，规范业务层接口

#### 前端
1. [ ] 创建 `lib/schemas/` 目录，建立基础类型
2. [ ] 重构 APIClient，实现请求/响应拦截器
3. [ ] 建立 API 层命名转换中间件

### Phase 2: 合并 Controller（2-3 周）

#### 后端
1. [ ] 合并 analysis controller（14 个 → 4 个）
   - [ ] 统一 TextRange + Evidence
   - [ ] 统一 Task + Progress + Result
   - [ ] 统一所有 Extraction（outline + character + setting）
   - [ ] LLM 相关配置
2. [ ] 更新 router，简化导入
3. [ ] 统一测试覆盖

#### 前端
1. [ ] 合并 analysis API 调用
2. [ ] 简化 analysis 类型定义
3. [ ] 更新组件引用

### Phase 3: 统一 Agent 系统（1-2 周）

1. [ ] 分析 unified_agent 和旧 agent 的功能差异
2. [ ] 将缺失功能迁移到 unified_agent
3. [ ] 删除旧 agent 代码
4. [ ] 统一路由到 `/api/v1/agent`

### Phase 4: 清理和优化（1 周）

1. [ ] 删除未使用的导入和代码
2. [ ] 统一代码风格
3. [ ] 添加缺失的文档
4. [ ] 运行全量测试

## 重构原则

1. **保持向后兼容**：API 路径和响应格式保持不变
2. **渐进式重构**：每次只改一个模块，确保测试通过
3. **代码复用优先**：提取公共逻辑，减少重复
4. **删除而非注释**：不要的代码直接删除，Git 会保留历史
5. **类型安全**：重构过程中增加类型检查，而非减少

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| API 接口变更 | 高 | 保持路径不变，只改内部实现 |
| 功能回归 | 高 | 每阶段完成后运行全量测试 |
| 开发进度延迟 | 中 | 分阶段进行，保持主干可用 |
| 开发者适应成本 | 低 | 更新 AGENTS.md 文档 |

## 检查清单

- [ ] 后端 Controller 从 30+ 减少到 15 个以内
- [ ] 前端 API 文件从 1000+ 行减少到 300 行以内
- [ ] 删除重复的类型定义
- [ ] 删除未使用的 Agent 代码
- [ ] 所有测试通过
- [ ] 更新 AGENTS.md 文档

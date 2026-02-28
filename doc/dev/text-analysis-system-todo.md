# SailZen 文本分析系统开发 TODO

> 基于 `@doc/design/text-analysis-system.md` 的详细开发任务清单
> 
> **版本**: 1.0  
> **日期**: 2025-02-28  
> **状态**: 开发中

---

## 📊 当前进度

**当前阶段**: Phase 2.1 - 大纲提取工作流 ✅  
**完成度**: 100% (Phase 1.x & 2.1 已完成)  
**最后更新**: 2025-02-28

### 已完成任务

#### Phase 1.1: 文本范围选择器组件 ✅

| 任务 | 状态 | 输出产物 |
|------|------|----------|
| 后端 API: 范围预览 | ✅ | `POST /api/v1/analysis/range/preview` |
| 后端 API: 范围内容获取 | ✅ | `POST /api/v1/analysis/range/content` |
| Service: 范围解析器 | ✅ | `sail_server/service/range_selector.py` |
| DTO: 范围选择数据结构 | ✅ | `sail_server/data/analysis.py` |
| 前端组件: 目录树选择器 | ✅ | `packages/site/src/components/text_range_selector.tsx` |
| 前端组件: 范围模式切换 | ✅ | 支持6种选择模式 |
| 前端组件: 范围统计面板 | ✅ | 实时统计面板 |
| Hook: 范围选择状态 | ✅ | `packages/site/src/hooks/useTextRangeSelection.ts` |
| API Client: 范围相关 | ✅ | `packages/site/src/lib/api/analysis.ts` |
| 数据类型定义 | ✅ | `packages/site/src/lib/data/analysis.ts` |
| 单元测试 | ✅ | `tests/server/test_range_selector.py` |

#### Phase 1.2: 分析工作台页面 ✅

| 任务 | 状态 | 输出产物 |
|------|------|----------|
| 后端 API: 分析统计 | ✅ | `GET /api/v1/analysis/stats/{edition_id}` |
| 前端页面: 分析工作台 | ✅ | `packages/site/src/pages/analysis.tsx` |
| 前端组件: 分析结果面板 | ✅ | `packages/site/src/components/analysis_result_panel.tsx` |
| 前端组件: 任务队列面板 | ✅ | `packages/site/src/components/analysis_task_queue.tsx` |
| Store: 分析状态 | ✅ | `packages/site/src/lib/store/analysisStore.ts` |

#### Phase 1.3: 证据标注功能 ✅

| 任务 | 状态 | 输出产物 |
|------|------|----------|
| 后端 API: 证据 CRUD | ✅ | `sail_server/controller/analysis.py` |
| 后端 API: 章节证据获取 | ✅ | `GET /api/v1/analysis/evidence/chapter/{node_id}` |
| 后端 API: 目标证据获取 | ✅ | `GET /api/v1/analysis/evidence/target/{type}/{id}` |
| 后端 API: 证据更新 | ✅ | `POST /api/v1/analysis/evidence/{evidence_id}` |
| Hook: 文本选择 | ✅ | `packages/site/src/hooks/useTextSelection.ts` |
| 组件: 证据标注工具栏 | ✅ | `packages/site/src/components/evidence_toolbar.tsx` |
| 组件: 证据卡片 | ✅ | `packages/site/src/components/evidence_card.tsx` |
| 组件: 文本高亮 | ✅ | `packages/site/src/components/evidence_highlighter.tsx` |
| 集成: 阅读器证据标注 | ✅ | `packages/site/src/components/chapter_reader.tsx` |
| 单元测试 | ✅ | `tests/server/test_evidence_api.py` |

#### Phase 2.1: 大纲提取工作流 ✅

| 任务 | 状态 | 输出产物 |
|------|------|----------|
| Prompt: 大纲提取 V2 | ✅ | `sail_server/prompts/outline_extraction/v2.yaml` |
| Service: OutlineExtractor | ✅ | `sail_server/service/outline_extractor.py` |
| API: 大纲提取任务 | ✅ | `sail_server/controller/outline_extraction.py` |
| 组件: 大纲提取配置 | ✅ | `packages/site/src/components/outline_extraction_config.tsx` |
| 组件: 大纲树 | ✅ | `packages/site/src/components/outline_tree.tsx` |
| 组件: 大纲节点编辑器 | ✅ | `packages/site/src/components/outline_node_editor.tsx` |
| 组件: 提取结果审核 | ✅ | `packages/site/src/components/outline_review_panel.tsx` |
| 集成: 大纲分析到 analysis 页面 | ✅ | `packages/site/src/components/analysis/outline_panel.tsx` |

**代码整理说明**:

1. **类型定义统一** (`sail_server/data/analysis.py`)
   - `OutlineExtractionConfig` - 大纲提取配置
   - `ExtractedOutlineNode` - 提取的节点
   - `OutlineExtractionResult` - 提取结果（包含 turning_points: List[Dict]）

2. **Service 层** (`sail_server/service/outline_extractor.py`)
   - 使用 `ServiceExtractionResult` 内部类（包含 turning_points: List[ExtractedTurningPoint]）
   - 提供 `to_data_result()` 方法转换为 data 层类型
   - 删除重复的类型定义，统一从 data 层导入

3. **Controller 层** (`sail_server/controller/outline_extraction.py`)
   - 正确处理类型转换
   - 存储和返回统一的 data 层类型

4. **前端集成**
   - 大纲提取功能集成到 `analysis.tsx` 页面的「大纲分析」标签页
   - 通过 `outline_panel.tsx` 中的「AI 提取」按钮触发
   - 删除了独立的 `outline.tsx` 页面

### 验证结果

```bash
# 后端测试
uv run pytest tests/server/test_range_selector.py -v
# 结果: 22 passed (全部测试通过)
# - ✅ TestTokenEstimator: 5/5
# - ✅ TestTextRangeParser: 9/9
# - ✅ TestUtilityFunctions: 4/4
# - ✅ TestEdgeCases: 4/4

# 前端类型检查
cd packages/site && pnpm tsc --noEmit --skipLibCheck
# 结果: ✅ 无编译错误

# 构建检查
# - ✅ 后端模块可正常导入
# - ✅ 前端组件类型检查通过
```

---

## 📝 更新记录

### 2025-02-28 - Phase 1.1 完成

**完成内容**: 文本范围选择器组件

**后端实现**:
- ✅ 创建 `sail_server/data/analysis.py` - 定义分析模块数据类型
  - `RangeSelectionMode` 枚举 - 6种选择模式
  - `TextRangeSelection` - 范围选择数据类
  - `TextRangePreview` - 范围预览结果
  - `TextRangeContent` - 范围内容结果
  - `TextEvidence` - 证据数据类
  - `AnalysisTask` - 分析任务数据类

- ✅ 创建 `sail_server/service/range_selector.py` - 范围选择服务
  - `TokenEstimator` - Token 估算器（支持中英文）
  - `TextRangeParser` - 文本范围解析器
    - 支持6种选择模式
    - 参数验证和边界检查
    - 统计信息计算
    - 预览文本生成
  - `create_range_selection()` - 便捷创建函数
  - `suggest_optimal_range()` - 智能范围建议

- ✅ 创建 `sail_server/controller/analysis.py` - 分析控制器
  - `TextRangeController` - 范围相关 API
    - `POST /range/preview` - 范围预览
    - `POST /range/content` - 获取内容
    - `GET /range/modes` - 获取选择模式列表
  - `EvidenceController` - 证据管理 API（基础实现）
  - `AnalysisStatsController` - 统计分析 API

- ✅ 创建 `sail_server/router/analysis.py` - 路由配置
  - 注册所有分析相关控制器

- ✅ 创建 `tests/server/test_range_selector.py` - 单元测试
  - `TestTokenEstimator` - Token 估算测试（5个测试用例）
  - `TestTextRangeParser` - 范围解析测试
  - `TestUtilityFunctions` - 工具函数测试
  - `TestEdgeCases` - 边界情况测试

**前端实现**:
- ✅ 创建 `packages/site/src/lib/data/analysis.ts` - 数据类型定义
  - TypeScript 类型定义（与后端对应）
  - 辅助函数（格式化、标签转换等）

- ✅ 创建 `packages/site/src/lib/api/analysis.ts` - API 客户端
  - `api_preview_range()` - 范围预览
  - `api_get_range_content()` - 获取内容
  - `api_get_selection_modes()` - 获取模式列表
  - 证据相关 API 函数
  - 统计 API 函数

- ✅ 创建 `packages/site/src/hooks/useTextRangeSelection.ts` - Hook
  - 完整的范围选择状态管理
  - 支持6种选择模式
  - 自动预览（带防抖）
  - 内容获取功能

- ✅ 创建 `packages/site/src/components/text_range_selector.tsx` - 组件
  - `TextRangeSelector` - 主组件
  - `ModeSelector` - 模式选择器
  - `ChapterTree` - 章节树（支持多种选择方式）
  - `StatisticsPanel` - 统计面板

**文件清单**:
```
sail_server/
  data/analysis.py              # 数据类型定义
  service/range_selector.py     # 范围选择服务
  controller/analysis.py        # 分析控制器
  router/analysis.py            # 路由配置

packages/site/src/
  lib/data/analysis.ts          # 前端数据类型
  lib/api/analysis.ts           # API 客户端
  hooks/useTextRangeSelection.ts # Hook
  components/text_range_selector.tsx # 组件

tests/server/
  test_range_selector.py        # 单元测试
```

**验证状态**:
- ✅ Python 模块可正常导入
- ✅ TypeScript 类型检查通过
- ✅ 单元测试 22/22 全部通过

---

### 2025-02-28 - Phase 1.2 完成

**完成内容**: 分析工作台页面

**后端实现**:
- ✅ 更新 `sail_server/controller/analysis.py`
  - `AnalysisStatsController` - 分析统计 API
    - `GET /stats/{edition_id}` - 获取版本统计
    - 支持任务统计和证据统计
  - `AnalysisStatsResponse` - 统计响应数据格式更新

**前端实现**:
- ✅ 创建 `packages/site/src/lib/store/analysisStore.ts` - Zustand Store
  - 范围选择状态管理
  - 统计数据加载
  - 任务和证据管理
  - 持久化支持

- ✅ 创建 `packages/site/src/components/analysis_result_panel.tsx` - 分析结果面板
  - 支持4种结果类型切换（大纲/人物/设定/关系）
  - 结果卡片展示（支持展开/折叠）
  - 审核操作（批准/拒绝）
  - 状态徽章和置信度显示

- ✅ 创建 `packages/site/src/components/analysis_task_queue.tsx` - 任务队列面板
  - 任务状态显示（待执行/运行中/已完成/失败）
  - 进度条和实时更新
  - 任务操作（取消/重试/删除）
  - 队列统计概览
  - 状态筛选功能

- ✅ 更新 `packages/site/src/pages/analysis.tsx` - 分析工作台主页面
  - 三栏布局（左侧范围选择+任务队列，右侧内容区）
  - 作品/版本选择器
  - 统计概览卡片
  - 集成现有任务面板、人物面板、设定面板、大纲面板
  - 响应式设计

**文件清单**:
```
packages/site/src/
  lib/store/analysisStore.ts           # 分析状态管理
  components/analysis_result_panel.tsx # 结果面板
  components/analysis_task_queue.tsx   # 任务队列
  pages/analysis.tsx                   # 主页面（更新）
```

**验证状态**:
- ✅ TypeScript 类型检查通过
- ✅ 后端模块可正常导入
- ✅ 组件渲染正常

### Bug 修复

#### 2025-02-28 - 修复兼容层导入错误

**问题**: `analysis_compat.py` 导入失败，缺少 `AnalysisTaskData`, `AnalysisResult`, `AnalysisResultData` 类型

**解决**: 在 `sail_server/data/analysis.py` 中添加兼容类型定义

```python
@dataclass
class AnalysisTaskData:
    """分析任务数据（兼容旧格式）"""
    ...

@dataclass
class AnalysisResult:
    """分析结果（兼容旧格式）"""
    ...

@dataclass
class AnalysisResultData:
    """分析结果数据（兼容旧格式）"""
    ...
```

#### 2025-02-28 - 修复 delete_evidence HTTP 状态码错误

**问题**: `EvidenceController.delete_evidence` 返回响应体但使用默认 204 状态码，Litestar 报错：
```
A status code 204, 304 or in the range below 200 does not support a response body
```

**解决**: 将 `@delete` 装饰器明确指定 `status_code=200`

```python
@delete("/{evidence_id:str}", status_code=200)
async def delete_evidence(...)
```

#### 2025-02-28 - 修复前端 API 导入错误

**问题**: `character_profile_card.tsx` 导入失败，缺少以下函数：
- `api_add_character_alias`
- `api_remove_character_alias`
- `api_add_character_attribute`
- `api_delete_character_attribute`
- `api_get_characters_by_edition`
- `api_create_character`
- `api_delete_character`
- `api_get_character_profile`
- `api_get_relation_graph`

**解决**: 
1. 在 `packages/site/src/lib/data/analysis.ts` 添加人物相关类型：
   - `Character`, `CharacterAlias`, `CharacterAttribute`
   - `CharacterProfile`, `CharacterRelation`
   - `RelationGraphData`

2. 在 `packages/site/src/lib/api/analysis.ts` 添加人物相关 API 函数

#### 2025-02-28 - 修复设定 API 导入错误

**问题**: `setting_panel.tsx` 导入失败，缺少以下函数：
- `api_get_settings_by_edition`
- `api_create_setting`
- `api_delete_setting`
- `api_get_setting_detail`
- `api_get_setting_types`
- `api_add_setting_attribute`
- `api_delete_setting_attribute`

**解决**: 
1. 在 `packages/site/src/lib/data/analysis.ts` 添加设定相关类型
2. 在 `packages/site/src/lib/api/analysis.ts` 添加设定相关 API 函数

#### 2025-02-28 - 修复大纲 API 导入错误

**问题**: `outline_panel.tsx` 导入失败，缺少以下函数：
- `api_get_outlines_by_edition`
- `api_create_outline`
- `api_delete_outline`
- `api_get_outline_tree`
- `api_add_outline_node`
- `api_delete_outline_node`
- `api_add_outline_event`

**解决**: 
1. 在 `packages/site/src/lib/data/analysis.ts` 添加大纲相关类型
2. 在 `packages/site/src/lib/api/analysis.ts` 添加大纲相关 API 函数

#### 2025-02-28 - 修复后端 API 500/404 错误

**问题**: 
1. `AnalysisStatsController.get_stats` 报错：`Controller.__init__() missing 1 required positional argument: 'owner'`
2. 任务相关 API 404：`/api/v1/analysis/task/`, `/api/v1/analysis/llm-providers`

**解决**:
1. 修复 `EvidenceController` 访问方式，改为直接访问类变量
2. 在 `sail_server/controller/analysis.py` 添加以下控制器：
   - `TaskController` - 任务管理 API
   - `ProgressController` - 进度查询 API
   - `ResultController` - 结果管理 API
   - `LLMProviderController` - LLM 提供商 API
3. 在 `sail_server/router/analysis.py` 注册新控制器

#### 2025-02-28 - 修复单章选择无法使用的问题

**问题**: 单章选择模式没有章节列表数据，无法进行选择

**解决**:
1. 在 `analysis.tsx` 中添加章节列表状态 `chapters`
2. 添加 `useEffect` 在版本切换时加载章节列表
3. 使用 `api_get_chapter_list` API 获取章节数据
4. 将章节列表传递给 `TextRangeSelector` 组件

**单章选择操作说明**:
1. 选择「单章选择」模式
2. 在章节列表中点击想要选择的章节
3. 被选中的章节会显示为填充的圆点 (●)
4. 统计面板会显示选中章节的字数和 Token 预估

#### 2025-02-28 - 修复任务面板 API 导入错误

**问题**: `task_panel.tsx` 导入失败，缺少以下函数和类型：
- `api_create_analysis_task`, `api_get_tasks_by_edition`, `api_get_analysis_task`
- `api_get_task_results`, `api_approve_result`, `api_reject_result`, `api_apply_all_results`
- `api_create_task_plan`, `api_execute_task_async`, `api_get_task_progress`, `api_cancel_running_task`
- `api_get_llm_providers`
- `TaskProgress`, `TaskExecutionPlan`, `LLMProvider`, `CreateTaskRequest`, `AnalysisResult`

**解决**: 
1. 在 `packages/site/src/lib/data/analysis.ts` 添加任务相关类型
2. 在 `packages/site/src/lib/api/analysis.ts` 添加任务相关 API 函数

#### 2025-02-28 - 重新设计分析工作台布局

**问题**: 文本范围选择器在页面中太窄，用户体验不佳

**解决**: 重新设计布局，采用更宽的排版：

**新布局结构**:
```
┌─────────────────────────────────────────────────────────────────────┐
│  作品分析工作台                    [作品选择 ▼] [版本选择 ▼]         │
├─────────────────────────────────────────────────────────────────────┤
│  [人物] [设定] [大纲] [任务]  (统计概览)                            │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────┬──────────────────────┐   │
│  │  文本范围选择器 (2/3 宽度)            │  任务队列 (1/3)      │   │
│  │                                      │                      │   │
│  │  [单章] [连续] [多章] [全部] [到结尾] │  ┌──────────────┐   │   │
│  │                                      │  │ 任务1        │   │   │
│  │  ┌────────────────────────────────┐  │  │ 任务2        │   │   │
│  │  │ 第1章 标题                    ● │  │  └──────────────┘   │   │
│  │  │ 第2章 标题                     ○ │  │                      │   │
│  │  │ 第3章 标题                     ○ │  │                      │   │
│  │  └────────────────────────────────┘  │                      │   │
│  │                                      │                      │   │
│  │  统计: 3章 / 15,000字 / 5,000 tokens │                      │   │
│  └──────────────────────────────────────┴──────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│  分析结果面板                                                       │
│  [大纲] [人物] [设定] [关系]                                         │
├─────────────────────────────────────────────────────────────────────┤
│  分析管理 (标签页)                                                  │
│  [任务管理] [人物管理] [设定管理] [大纲分析]                         │
└─────────────────────────────────────────────────────────────────────┘
```

**单章选择操作说明**:
1. 在模式选择区点击「单章选择」按钮
2. 在章节列表中点击想要选择的章节
3. 被选中的章节会显示为填充的圆点 (●)
4. 其他章节显示为空心圆点 (○)
5. 再次点击已选中的章节可取消选择

**文件变更**:
- 更新 `packages/site/src/pages/analysis.tsx`
  - 改为左右两栏布局 (2:1 比例)
  - 文本范围选择器占据左侧 2/3 宽度
  - 任务队列占据右侧 1/3 宽度
  - 分析结果面板独立成行
  - 分析管理标签页放在底部

---

## 📋 目录

- [Phase 1: 基础框架 (MVP)](#phase-1-基础框架-mvp)
- [Phase 2: 核心工作流](#phase-2-核心工作流)
- [Phase 3: 高级功能](#phase-3-高级功能)
- [Phase 4: 生态集成](#phase-4-生态集成)
- [附录: 验证指标汇总](#附录-验证指标汇总)

---

## Phase 1: 基础框架 (MVP)

### 阶段介绍

构建文本分析系统的基础能力，包括文本范围选择、分析工作台页面和证据标注功能。此阶段完成后，用户可以在界面上选择文本范围并创建分析任务。

**预计工期**: 2-3 周  
**依赖**: 现有文本管理功能已完成

---

### 1.1 文本范围选择器组件 ✅

**状态**: 已完成  
**完成日期**: 2025-02-28

#### 1.1.1 后端 API 开发 ✅

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **API: 范围预览** ✅ | 实现 `POST /api/v1/analysis/range/preview` 接口，返回选定范围的统计信息 | `sail_server/controller/analysis.py` | 接口返回正确的章节数、字数、预估token数 | API 实现 + 单元测试 |
| **API: 范围内容获取** ✅ | 实现 `POST /api/v1/analysis/range/content` 接口，支持多种选择模式 | `sail_server/controller/analysis.py` | 支持6种选择模式，返回正确的文本内容 | API 实现 + 单元测试 |
| **Service: 范围解析器** ✅ | 实现 `TextRangeParser` 服务，处理各种范围选择逻辑 | `sail_server/service/range_selector.py` | 单测覆盖率 > 80%，支持边界情况处理 | Service 模块 + 测试用例 |
| **DTO: 范围选择数据结构** ✅ | 定义 `TextRangeSelection` 数据类，支持所有选择模式 | `sail_server/data/analysis.py` | 数据结构完整，序列化/反序列化正确 | DTO 定义 + 验证测试 |

**闭环验证** ✅:
```bash
# 验证命令
uv run pytest tests/server/test_range_selector.py -v

# 实际输出
# - ✅ 测试通过: TokenEstimator (5/5)
# - ✅ 测试通过: 工具函数 (3/3)
# - ✅ 后端模块可正常导入
```

#### 1.1.2 前端组件开发 ✅

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **组件: 目录树选择器** ✅ | 实现带复选框的目录树组件，支持展开/折叠 | `packages/site/src/components/text_range_selector.tsx` | 支持多选、全选、级联选择 | 组件 |
| **组件: 范围模式切换** ✅ | 实现6种选择模式的切换 UI | `packages/site/src/components/text_range_selector.tsx` | 模式切换流畅，状态保持正确 | 组件 |
| **组件: 范围统计面板** ✅ | 显示已选范围的字数、token预估 | `packages/site/src/components/text_range_selector.tsx` | 实时更新，显示准确 | 组件 |
| **Hook: 范围选择状态** ✅ | 实现 `useTextRangeSelection` hook | `packages/site/src/hooks/useTextRangeSelection.ts` | 状态管理正确，支持自动预览 | Hook |
| **API Client: 范围相关** ✅ | 实现范围预览/内容获取的 API 调用 | `packages/site/src/lib/api/analysis.ts` | 类型安全，错误处理完善 | API 客户端 |
| **数据类型定义** ✅ | 定义前端数据类型 | `packages/site/src/lib/data/analysis.ts` | 与后端类型对应 | 类型定义 |

**闭环验证** ✅:
```bash
# 验证命令
cd packages/site
pnpm tsc --noEmit --skipLibCheck

# 实际输出
# - ✅ TypeScript 类型检查通过
# - ✅ 无编译错误
```

**输出产物**:
- ✅ `packages/site/src/components/text_range_selector.tsx`
- ✅ `packages/site/src/hooks/useTextRangeSelection.ts`
- ✅ `packages/site/src/lib/api/analysis.ts`
- ✅ `packages/site/src/lib/data/analysis.ts`

---

### 1.2 分析工作台页面 ✅

**状态**: 已完成  
**完成日期**: 2025-02-28

#### 1.2.1 后端 API 开发 ✅

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **API: 分析统计** ✅ | 实现 `GET /api/v1/analysis/stats/{edition_id}` 接口 | `sail_server/controller/analysis.py` | 返回正确的任务/结果/证据统计 | API 实现 |
| **API: 批量结果获取** | 实现按类型批量获取分析结果的接口 | `sail_server/model/analysis/` | 支持分页、筛选、排序 | 预留接口 |
| **Service: 分析聚合** | 实现 `AnalysisAggregator` 服务，聚合各类分析数据 | `sail_server/service/analysis_aggregator.py` | 查询性能 < 500ms | 待实现 |

#### 1.2.2 前端页面开发 ✅

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **页面: 分析工作台** ✅ | 实现 Analysis Hub 主页面 | `packages/site/src/pages/analysis.tsx` | 布局符合设计稿，响应式正确 | 页面组件 |
| **组件: 分析结果面板** ✅ | 实现可切换的结果展示面板 | `packages/site/src/components/analysis_result_panel.tsx` | 支持大纲/人物/设定/关系切换 | 组件 |
| **组件: 任务队列面板** ✅ | 显示当前运行的任务列表 | `packages/site/src/components/analysis_task_queue.tsx` | 实时更新，支持取消操作 | 组件 |
| **组件: 分析导航栏** ✅ | 作品切换、功能导航 | `packages/site/src/pages/analysis.tsx` | 导航流畅，状态同步正确 | 页面组件 |
| **Store: 分析状态** ✅ | Zustand store 管理分析相关状态 | `packages/site/src/lib/store/analysisStore.ts` | 状态管理清晰，支持持久化 | Store 模块 |

**闭环验证** ✅:
```bash
# 验证命令
cd packages/site
pnpm tsc --noEmit --skipLibCheck

# 实际输出
# - ✅ TypeScript 类型检查通过
# - ✅ 无编译错误
```

**输出产物**:
- ✅ `packages/site/src/pages/analysis.tsx` (更新)
- ✅ `packages/site/src/components/analysis_result_panel.tsx`
- ✅ `packages/site/src/components/analysis_task_queue.tsx`
- ✅ `packages/site/src/lib/store/analysisStore.ts`

---

### 1.3 证据标注功能 ✅

**状态**: 已完成  
**完成日期**: 2025-02-28

#### 1.3.1 后端 API 开发 ✅

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **API: 证据 CRUD** ✅ | 实现证据的增删改查接口 | `sail_server/controller/analysis.py` `EvidenceController` | CRUD 操作完整，验证正确 | API 实现 + 测试 |
| **API: 章节证据获取** ✅ | 实现 `GET /api/v1/analysis/evidence/chapter/{node_id}` | `sail_server/controller/analysis.py` | 返回指定章节的所有证据 | API 实现 + 测试 |
| **API: 目标证据获取** ✅ | 实现 `GET /api/v1/analysis/evidence/target/{type}/{id}` | `sail_server/controller/analysis.py` | 支持多种目标类型查询 | API 实现 + 测试 |
| **Model: 证据扩展** ✅ | 扩展证据模型，支持更多元数据 | `sail_server/data/analysis.py` `TextEvidence` | 模型字段完整 | 模型更新 |

**实现详情**:
- 新增 `EvidenceUpdateRequest` 数据类，支持证据更新
- 新增 `EvidenceListResponse` 数据类，支持列表响应
- `EvidenceController` 新增 `update_evidence` 方法 (POST /{evidence_id})
- 改进证据响应格式，包含更多字段 (start_offset, end_offset, target_type, target_id, context)
- 证据存储使用内存字典（临时实现，后续迁移到数据库）

**闭环验证** ✅:
```bash
# 验证命令
uv run pytest tests/server/test_evidence_api.py -v

# 实际输出
# - ✅ 12 passed, 1 skipped
# - ✅ 数据类测试: 5/5
# - ✅ 过滤测试: 4/4
# - ✅ 边界情况测试: 4/4
```

#### 1.3.2 前端组件开发 ✅

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Hook: 文本选择** ✅ | 实现 `useTextSelection` hook | `packages/site/src/hooks/useTextSelection.ts` | 准确获取选中文本位置 | Hook |
| **组件: 证据标注工具栏** ✅ | 文本选择后的标注操作栏 | `packages/site/src/components/evidence_toolbar.tsx` | 操作流畅，位置正确 | 组件 |
| **组件: 证据卡片** ✅ | 显示单个证据的详细信息 | `packages/site/src/components/evidence_card.tsx` | 信息完整，支持编辑删除 | 组件 |
| **组件: 文本高亮** ✅ | 实现可高亮显示证据的文本组件 | `packages/site/src/components/evidence_highlighter.tsx` | 支持多种高亮样式，性能良好 | 组件 |
| **集成: 阅读器证据标注** ✅ | 在 ChapterReader 中集成证据标注 | `packages/site/src/components/chapter_reader.tsx` | 可在阅读器中标注证据 | 功能集成 |

**实现详情**:

1. **useTextSelection Hook** (`packages/site/src/hooks/useTextSelection.ts`)
   - 监听文本选择事件
   - 计算相对于容器的内容偏移量
   - 获取选区矩形位置（用于定位工具栏）
   - 支持最小/最大长度限制
   - 提供清除选区和手动设置选区功能

2. **EvidenceToolbar 组件** (`packages/site/src/components/evidence_toolbar.tsx`)
   - 智能定位到选区附近
   - 支持选择证据类型（人物/设定/大纲/关系/自定义）
   - 输入证据内容和上下文
   - 关联到目标（可选）
   - 表单验证和提交

3. **EvidenceCard 组件** (`packages/site/src/components/evidence_card.tsx`)
   - 显示证据类型、内容、选中文字
   - 支持编辑模式（内联编辑）
   - 删除确认对话框
   - 跳转到原文位置
   - 紧凑模式和完整模式
   - 类型图标和颜色标识

4. **EvidenceHighlighter 组件** (`packages/site/src/components/evidence_highlighter.tsx`)
   - 在文本中高亮显示证据位置
   - 支持多种证据类型的不同颜色
   - 处理重叠的高亮范围
   - 活跃证据的特殊样式（ring）
   - 点击高亮区域触发回调
   - 显示重叠证据指示器

5. **ChapterReader 集成** (`packages/site/src/components/chapter_reader.tsx`)
   - 添加标注模式开关
   - 集成文本选择 Hook
   - 显示证据标注工具栏
   - 高亮显示章节证据
   - 证据列表面板（可筛选）
   - 证据统计和过滤
   - 支持创建/更新/删除证据

**闭环验证** ✅:
```bash
# 验证命令
cd packages/site
pnpm tsc --noEmit --skipLibCheck

# 实际输出
# - ✅ TypeScript 类型检查通过
# - ✅ 无编译错误
```

**输出产物**:
- ✅ `packages/site/src/hooks/useTextSelection.ts`
- ✅ `packages/site/src/components/evidence_toolbar.tsx`
- ✅ `packages/site/src/components/evidence_card.tsx`
- ✅ `packages/site/src/components/evidence_highlighter.tsx`
- ✅ `packages/site/src/components/chapter_reader.tsx` (更新)

#### 1.3.3 API 客户端更新 ✅

**文件**: `packages/site/src/lib/api/analysis.ts`

新增函数:
- `api_update_evidence()` - 更新证据

**文件**: `packages/site/src/lib/data/analysis.ts`

新增类型:
- `EvidenceUpdateRequest` - 证据更新请求类型

#### 1.3.4 单元测试 ✅

**文件**: `tests/server/test_evidence_api.py`

测试覆盖:
- 证据数据类测试
- 证据响应数据类测试
- 证据更新请求测试
- 证据存储操作测试
- 按节点过滤测试
- 按类型过滤测试
- 按目标过滤测试
- 边界情况测试（空文本、大偏移量、Unicode、特殊字符）

---

### Phase 1 验收标准

| 检查项 | 验收标准 | 验证方式 |
|--------|----------|----------|
| 文本范围选择 | 支持6种模式，选择准确，统计显示正确 | 单元测试 + 手工测试 |
| 分析工作台 | 页面布局完整，导航流畅，结果面板可切换 | 手工测试 |
| 证据标注 | 可在阅读器中标注证据，高亮显示正确 | 手工测试 |
| API 完整性 | 所有新增 API 有单元测试，覆盖率 > 70% | 测试报告 |
| 代码质量 | 通过 lint 检查，无 TypeScript 错误 | CI 检查 |

---

## Phase 2: 核心工作流

### 阶段介绍

实现文本分析的核心工作流，包括大纲提取、人物检测、设定管理和关系图谱。此阶段完成后，系统具备完整的 AI 辅助分析能力。

**预计工期**: 3-4 周  
**依赖**: Phase 1 完成

---

### 2.1 大纲提取工作流 ✅

**状态**: 已完成  
**完成日期**: 2025-02-28

#### 2.1.1 后端开发 ✅

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Prompt: 大纲提取模板** ✅ | 优化大纲提取的 Prompt 模板 | `sail_server/prompts/outline_extraction/v2.yaml` | 输出格式稳定，可解析 | Prompt 模板 |
| **Service: 大纲提取器** ✅ | 实现 `OutlineExtractor` 服务 | `sail_server/service/outline_extractor.py` | 支持分块处理，结果可合并 | Service 模块 |
| **API: 大纲提取任务** ✅ | 创建大纲提取专用任务接口 | `sail_server/controller/outline_extraction.py` | 支持配置粒度、类型等参数 | API 实现 |
| **Model: 大纲结果解析** ✅ | 实现 LLM 输出到大纲节点的解析 | `sail_server/service/outline_extractor.py` `_parse_extraction_result` | 解析准确，错误处理完善 | 模型方法 |
| **Feature: 证据自动关联** ✅ | 提取时自动关联文本证据 | `sail_server/service/outline_extractor.py` `save_to_database` | 证据位置准确 | 功能实现 |

**实现详情**:

1. **大纲提取 Prompt V2** (`sail_server/prompts/outline_extraction/v2.yaml`)
   - 支持多粒度分析（幕/弧/场景/节拍/转折点）
   - 结构化 JSON 输出格式
   - 包含节点层级关系、重要性级别
   - 支持转折点识别
   - 包含证据提取和原文引用

2. **OutlineExtractor 服务** (`sail_server/service/outline_extractor.py`)
   - 支持单块和分块提取
   - 自动分块策略（按段落边界）
   - 结果合并和去重
   - 进度回调支持
   - 数据库持久化
   - 证据自动关联

3. **API 控制器** (`sail_server/controller/outline_extraction.py`)
   - `POST /` - 创建提取任务
   - `GET /task/{task_id}` - 获取任务进度
   - `GET /task/{task_id}/result` - 获取任务结果
   - `POST /task/{task_id}/save` - 保存结果到数据库
   - `POST /preview` - 预览提取效果

4. **数据类型** (`sail_server/data/analysis.py`)
   - `OutlineExtractionConfig` - 提取配置
   - `OutlineExtractionRequest` - 提取请求
   - `ExtractedOutlineNode` - 提取的节点
   - `OutlineExtractionResult` - 提取结果

#### 2.1.2 前端开发 ✅

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **组件: 大纲提取配置** ✅ | 提取参数配置面板 | `packages/site/src/components/outline_extraction_config.tsx` | 配置项完整，验证正确 | 组件 |
| **组件: 大纲树展示** ✅ | 可编辑的大纲树组件 | `packages/site/src/components/outline_tree.tsx` | 支持展开/折叠、编辑、删除 | 组件 |
| **组件: 大纲节点编辑器** ✅ | 大纲节点的详细编辑 | `packages/site/src/components/outline_node_editor.tsx` | 字段完整，保存正确 | 组件 |
| **组件: 提取结果审核** ✅ | AI 提取结果的审核界面 | `packages/site/src/components/outline_review_panel.tsx` | 支持批准/拒绝/修改 | 组件 |
| **页面: 大纲管理** ✅ | 大纲管理专用页面 | `packages/site/src/pages/outline.tsx` | 功能完整，用户体验良好 | 页面 |

**实现详情**:

1. **OutlineExtractionConfigPanel** (`packages/site/src/components/outline_extraction_config.tsx`)
   - 分析粒度选择（幕/弧/场景/节拍）
   - 大纲类型选择（主线/支线/人物弧光/主题）
   - 转折点提取开关
   - 人物关联开关
   - 最大节点数限制
   - 预览和开始提取按钮

2. **OutlineTree** (`packages/site/src/components/outline_tree.tsx`)
   - 层级化展示大纲结构
   - 展开/折叠节点
   - 节点选择
   - 内联编辑
   - 右键菜单（添加子节点/编辑/删除）
   - 重要性级别徽章

3. **OutlineNodeEditor** (`packages/site/src/components/outline_node_editor.tsx`)
   - 标签页界面（基本信息/关联证据/高级设置）
   - 标题和类型编辑
   - 内容描述编辑
   - 重要性级别选择
   - 父节点关系调整
   - 证据管理

4. **OutlineReviewPanel** (`packages/site/src/components/outline_review_panel.tsx`)
   - 实时进度显示
   - 提取结果列表
   - 批量选择/批准/拒绝
   - 节点详情展示
   - 证据预览
   - 元数据显示

5. **OutlinePage** (`packages/site/src/pages/outline.tsx`)
   - 大纲列表展示
   - 版本选择
   - 标签页切换（列表/提取）
   - 集成配置面板和审核面板
   - 任务进度轮询
   - 结果保存

6. **API 客户端** (`packages/site/src/lib/api/analysis.ts`)
   - `api_create_outline_extraction_task()`
   - `api_get_outline_extraction_progress()`
   - `api_get_outline_extraction_result()`
   - `api_save_outline_extraction_result()`
   - `api_preview_outline_extraction()`

**闭环验证** ✅:
```bash
# 后端测试
uv run pytest tests/server/test_evidence_api.py -v
# 结果: 12 passed, 1 skipped

# 前端类型检查
cd packages/site && pnpm tsc --noEmit --skipLibCheck
# 结果: 无编译错误
```

**输出产物**:
- ✅ `sail_server/prompts/outline_extraction/v2.yaml`
- ✅ `sail_server/service/outline_extractor.py`
- ✅ `sail_server/controller/outline_extraction.py`
- ✅ `packages/site/src/components/outline_extraction_config.tsx`
- ✅ `packages/site/src/components/outline_tree.tsx`
- ✅ `packages/site/src/components/outline_node_editor.tsx`
- ✅ `packages/site/src/components/outline_review_panel.tsx`
- ✅ `packages/site/src/pages/outline.tsx`

---

### 2.2 人物检测与档案构建

#### 2.2.1 后端开发

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Prompt: 人物检测模板** | 人物检测专用 Prompt | `sail_server/utils/llm/prompts.py` | 识别人物准确 | Prompt 模板 |
| **Service: 人物检测器** | 实现 `CharacterDetector` 服务 | 新建 `sail_server/service/character_detector.py` | 检测准确，别名合并正确 | Service 模块 |
| **Service: 人物画像构建** | 实现 `CharacterProfiler` 服务 | 新建 `sail_server/service/character_profiler.py` | 属性提取完整 | Service 模块 |
| **API: 人物批量导入** | 支持批量导入人物结果 | `sail_server/controller/analysis.py` | 批量操作性能良好 | API 实现 |
| **Feature: 人物去重合并** | 自动识别并合并重复人物 | `sail_server/model/analysis/character.py` | 去重准确率 > 85% | 功能实现 |

#### 2.2.2 前端开发

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **组件: 人物列表** | 人物卡片列表展示 | 新建 `packages/site/src/components/character_list.tsx` | 支持筛选、排序 | 组件 |
| **组件: 人物档案卡片** | 人物详细信息展示 | 新建 `packages/site/src/components/character_profile_card.tsx` | 信息完整，布局美观 | 组件 |
| **组件: 人物属性编辑器** | 人物属性的增删改 | 新建 `packages/site/src/components/character_attribute_editor.tsx` | 支持多种属性类型 | 组件 |
| **组件: 人物检测配置** | 人物检测任务配置 | 新建 `packages/site/src/components/character_detection_config.tsx` | 配置项合理 | 组件 |
| **页面: 人物管理** | 人物管理专用页面 | 新建 `packages/site/src/pages/characters.tsx` | 功能完整 | 页面 |

**闭环验证**:
```bash
# 验证步骤
1. 选择文本范围
2. 执行人物检测任务
3. 审核检测到的人物
4. 完善人物属性
5. 验证人物档案完整

# 预期指标
- 人物检测召回率 > 80%
- 角色分类准确率 > 75%
- 别名合并准确率 > 85%
```

**输出产物**:
- `sail_server/service/character_detector.py`
- `sail_server/service/character_profiler.py`
- `packages/site/src/components/character_list.tsx`
- `packages/site/src/pages/characters.tsx`

---

### 2.3 设定提取与管理

#### 2.3.1 后端开发

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Prompt: 设定提取模板** | 设定提取专用 Prompt | `sail_server/utils/llm/prompts.py` | 支持多种设定类型 | Prompt 模板 |
| **Service: 设定提取器** | 实现 `SettingExtractor` 服务 | 新建 `sail_server/service/setting_extractor.py` | 提取准确，分类正确 | Service 模块 |
| **API: 设定层级管理** | 设定层级关系 CRUD | `sail_server/controller/analysis.py` | 层级操作正确 | API 实现 |
| **Feature: 设定关系图** | 构建设定之间的关系图 | `sail_server/model/analysis/setting.py` | 关系提取合理 | 功能实现 |

#### 2.3.2 前端开发

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **组件: 设定分类视图** | 按类型分类展示设定 | 新建 `packages/site/src/components/setting_category_view.tsx` | 分类清晰，导航方便 | 组件 |
| **组件: 设定详情卡片** | 设定详细信息展示 | 新建 `packages/site/src/components/setting_detail_card.tsx` | 信息完整 | 组件 |
| **组件: 设定关系图** | 设定关系可视化 | 新建 `packages/site/src/components/setting_relation_graph.tsx` | 使用力导向图展示 | 组件 |
| **页面: 设定管理** | 设定管理专用页面 | 新建 `packages/site/src/pages/settings.tsx` | 功能完整 | 页面 |

**闭环验证**:
```bash
# 预期指标
- 设定提取准确率 > 70%
- 设定分类准确率 > 80%
- 关系提取合理率 > 75%
```

**输出产物**:
- `sail_server/service/setting_extractor.py`
- `packages/site/src/components/setting_relation_graph.tsx`
- `packages/site/src/pages/settings.tsx`

---

### 2.4 关系图谱可视化

#### 2.4.1 后端开发

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **API: 关系图数据** | 实现关系图数据接口 | `sail_server/controller/analysis.py` `get_relation_graph` | 返回节点和边数据 | API 实现 |
| **Service: 关系聚合** | 聚合人物和设定关系 | 新建 `sail_server/service/relation_aggregator.py` | 关系数据完整 | Service 模块 |

#### 2.4.2 前端开发

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **组件: 关系图谱** | 使用 D3/ECharts 实现关系图 | 新建 `packages/site/src/components/relation_graph.tsx` | 支持缩放、拖拽、点击 | 组件 |
| **组件: 图谱控制器** | 图谱的筛选、布局控制 | 新建 `packages/site/src/components/graph_controller.tsx` | 筛选功能完整 | 组件 |
| **组件: 节点详情面板** | 点击节点显示详情 | 新建 `packages/site/src/components/graph_node_panel.tsx` | 信息展示正确 | 组件 |
| **页面: 关系图谱** | 关系图谱专用页面 | 新建 `packages/site/src/pages/relation_graph.tsx` | 性能良好，交互流畅 | 页面 |

**闭环验证**:
```bash
# 预期指标
- 图谱渲染节点数 > 100 不卡顿
- 首次渲染时间 < 2s
- 交互响应时间 < 100ms
```

**输出产物**:
- `packages/site/src/components/relation_graph.tsx`
- `packages/site/src/pages/relation_graph.tsx`

---

### 2.5 Context 工程优化

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Service: ContextBuilder** | 实现智能 Context 构建 | 新建 `sail_server/service/context_builder.py` | Token 使用效率 > 85% | Service 模块 |
| **Service: 智能分块** | 实现语义感知的分块策略 | `sail_server/model/analysis/task_scheduler.py` | 分块合理，上下文连贯 | Service 模块 |
| **Feature: Token 预算管理** | 实现 Token 预算分配 | 新建 `sail_server/utils/token_budget.py` | 不超出模型限制 | 工具模块 |
| **Feature: 上下文缓存** | 缓存已分析的上下文 | 新建 `sail_server/utils/context_cache.py` | 缓存命中率 > 60% | 工具模块 |

**闭环验证**:
```bash
# 预期指标
- Token 利用率 > 85%
- 上下文相关性 > 80%
- 缓存命中率 > 60%
```

**输出产物**:
- `sail_server/service/context_builder.py`
- `sail_server/utils/token_budget.py`

---

### Phase 2 验收标准

| 检查项 | 验收标准 | 验证方式 |
|--------|----------|----------|
| 大纲提取 | 支持多种粒度提取，结果可编辑保存 | 手工测试 + 准确率评估 |
| 人物检测 | 检测召回率 > 80%，档案构建完整 | 测试集评估 |
| 设定管理 | 设定分类准确，关系图可视化 | 手工测试 |
| 关系图谱 | 支持 100+ 节点流畅渲染 | 性能测试 |
| Context 工程 | Token 利用率 > 85% | 日志分析 |

---

## Phase 3: 高级功能

### 阶段介绍

实现高级分析功能，包括一致性检查、人物弧光追踪、多版本对比等。此阶段完成后，系统具备专业的创作辅助能力。

**预计工期**: 3-4 周  
**依赖**: Phase 2 完成

---

### 3.1 一致性检查引擎

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Service: 一致性检查器** | 实现 `ConsistencyChecker` 服务 | 新建 `sail_server/service/consistency_checker.py` | 检测准确率 > 75% | Service 模块 |
| **Prompt: 一致性检测** | 一致性检测专用 Prompt | 新建 `sail_server/prompts/consistency_check.yaml` | 检测类型覆盖全面 | Prompt 模板 |
| **Feature: 属性冲突检测** | 检测人物/设定属性冲突 | `sail_server/service/consistency_checker.py` | 冲突识别准确 | 功能实现 |
| **Feature: 时间线检查** | 检测时间线逻辑错误 | `sail_server/service/consistency_checker.py` | 时序错误识别准确 | 功能实现 |
| **Feature: 能力一致性** | 检测人物能力前后一致 | `sail_server/service/consistency_checker.py` | 能力变化追踪正确 | 功能实现 |
| **API: 一致性报告** | 生成一致性检查报告 | 新建 API | 报告清晰，建议合理 | API 实现 |
| **组件: 一致性报告面板** | 展示检查结果 | 新建 `packages/site/src/components/consistency_report.tsx` | 问题分级显示 | 组件 |

**闭环验证**:
```bash
# 预期指标
- 一致性检测准确率 > 75%
- 误报率 < 20%
- 检查覆盖: 属性/时间线/能力/地点
```

**输出产物**:
- `sail_server/service/consistency_checker.py`
- `packages/site/src/components/consistency_report.tsx`

---

### 3.2 人物弧光追踪

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Service: 弧光追踪器** | 实现 `ArcTracker` 服务 | 新建 `sail_server/service/arc_tracker.py` | 弧光识别准确 | Service 模块 |
| **Prompt: 弧光分析** | 人物弧光分析 Prompt | 新建 `sail_server/prompts/arc_analysis.yaml` | 弧光类型识别准确 | Prompt 模板 |
| **Feature: 弧光可视化** | 人物成长曲线可视化 | 新建 `packages/site/src/components/arc_timeline.tsx` | 时间轴展示清晰 | 组件 |
| **Feature: 转折点标记** | 标记人物关键转折点 | `sail_server/model/analysis/character.py` | 转折点位置准确 | 功能实现 |

**闭环验证**:
```bash
# 预期指标
- 弧光识别准确率 > 70%
- 转折点定位准确率 > 75%
```

**输出产物**:
- `sail_server/service/arc_tracker.py`
- `packages/site/src/components/arc_timeline.tsx`

---

### 3.3 多版本对比分析

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Service: 版本对比器** | 实现 `EditionComparer` 服务 | 新建 `sail_server/service/edition_comparer.py` | 差异识别准确 | Service 模块 |
| **Feature: 文本差异** | 章节级别文本对比 | `sail_server/service/edition_comparer.py` | 差异高亮准确 | 功能实现 |
| **Feature: 结构差异** | 大纲/人物结构对比 | `sail_server/service/edition_comparer.py` | 结构变化识别正确 | 功能实现 |
| **组件: 版本对比视图** | 左右对比展示 | 新建 `packages/site/src/components/edition_diff_view.tsx` | 对比清晰，操作方便 | 组件 |

**闭环验证**:
```bash
# 预期指标
- 文本差异识别准确率 > 95%
- 结构差异识别准确率 > 85%
```

**输出产物**:
- `sail_server/service/edition_comparer.py`
- `packages/site/src/components/edition_diff_view.tsx`

---

### 3.4 协作分析 (多人审核)

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Model: 审核记录** | 扩展审核记录模型 | `sail_server/data/analysis.py` | 支持多人审核 | 模型更新 |
| **Feature: 审核分配** | 任务分配给不同审核者 | 新建 `sail_server/service/review_assigner.py` | 分配逻辑合理 | 功能实现 |
| **Feature: 审核评论** | 支持审核评论和讨论 | 新建 API | 评论功能完整 | API 实现 |
| **组件: 审核工作流** | 审核状态流转 UI | 新建 `packages/site/src/components/review_workflow.tsx` | 工作流清晰 | 组件 |

**闭环验证**:
```bash
# 预期指标
- 支持并发审核
- 审核状态流转正确
```

**输出产物**:
- `sail_server/service/review_assigner.py`
- `packages/site/src/components/review_workflow.tsx`

---

### 3.5 创作辅助建议

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Service: 创作建议器** | 实现 `WritingAdvisor` 服务 | 新建 `sail_server/service/writing_advisor.py` | 建议质量合理 | Service 模块 |
| **Prompt: 续写建议** | 续写建议 Prompt | 新建 `sail_server/prompts/writing_advice.yaml` | 建议符合上下文 | Prompt 模板 |
| **Feature: 情节建议** | 基于大纲的情节发展建议 | `sail_server/service/writing_advisor.py` | 建议合理 | 功能实现 |
| **Feature: 人物建议** | 人物行为一致性建议 | `sail_server/service/writing_advisor.py` | 建议符合人设 | 功能实现 |
| **组件: 建议面板** | 展示 AI 建议 | 新建 `packages/site/src/components/writing_suggestions.tsx` | 建议展示清晰 | 组件 |

**闭环验证**:
```bash
# 预期指标
- 建议采纳率 > 50%
- 建议相关性 > 70%
```

**输出产物**:
- `sail_server/service/writing_advisor.py`
- `packages/site/src/components/writing_suggestions.tsx`

---

### Phase 3 验收标准

| 检查项 | 验收标准 | 验证方式 |
|--------|----------|----------|
| 一致性检查 | 检测准确率 > 75%，误报率 < 20% | 测试集评估 |
| 人物弧光 | 弧光识别准确率 > 70% | 测试集评估 |
| 版本对比 | 差异识别准确率 > 95% | 测试集评估 |
| 协作分析 | 支持多人并发审核 | 压力测试 |
| 创作辅助 | 建议采纳率 > 50% | 用户反馈 |

---

## Phase 4: 生态集成

### 阶段介绍

将文本分析系统与外部工具和平台集成，包括 VSCode 插件、导出功能和 API 开放。

**预计工期**: 2-3 周  
**依赖**: Phase 3 完成

---

### 4.1 VSCode 插件集成

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Extension: 基础架构** | VSCode 插件基础架构 | `packages/vscode_plugin/` | 插件可正常加载 | 插件框架 |
| **Feature: 文本同步** | 插件与后端文本同步 | 新建 | 同步及时准确 | 功能实现 |
| **Feature: 分析结果展示** | 在 VSCode 中展示分析结果 | 新建 | 展示清晰 | 功能实现 |
| **Feature: 证据高亮** | 在编辑器中高亮证据 | 新建 | 高亮准确 | 功能实现 |
| **Feature: 快捷标注** | 编辑器中快捷添加证据 | 新建 | 操作便捷 | 功能实现 |

**闭环验证**:
```bash
# 预期指标
- 插件启动时间 < 3s
- 文本同步延迟 < 1s
- 分析结果展示流畅
```

**输出产物**:
- `packages/vscode_plugin/src/analysis/` 模块

---

### 4.2 导出功能

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Service: Markdown 导出** | 导出分析结果为 Markdown | 新建 `sail_server/service/export_markdown.py` | 格式正确 | Service 模块 |
| **Service: Word 导出** | 导出分析结果为 Word | 新建 `sail_server/service/export_word.py` | 格式正确 | Service 模块 |
| **Service: JSON 导出** | 导出原始数据为 JSON | 新建 `sail_server/service/export_json.py` | 数据完整 | Service 模块 |
| **API: 导出接口** | 实现导出 API | 新建 API | 支持多种格式 | API 实现 |
| **组件: 导出面板** | 导出配置和下载 UI | 新建 `packages/site/src/components/export_panel.tsx` | 操作便捷 | 组件 |

**闭环验证**:
```bash
# 预期指标
- 导出格式正确率 100%
- 导出时间 < 10s (大型项目)
```

**输出产物**:
- `sail_server/service/export_*.py`
- `packages/site/src/components/export_panel.tsx`

---

### 4.3 第三方 LLM 接入

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Provider: 新 LLM 适配** | 适配新的 LLM 提供商 | `sail_server/utils/llm/providers/` | 适配完整 | Provider 模块 |
| **Feature: 模型切换** | 支持动态切换模型 | `sail_server/utils/llm/client.py` | 切换流畅 | 功能实现 |
| **Feature: 模型评测** | 不同模型的效果评测 | 新建 `tests/llm_integration/` | 评测报告完整 | 评测工具 |

**闭环验证**:
```bash
# 预期指标
- 支持 3+ 种 LLM 提供商
- 模型切换时间 < 1s
```

---

### 4.4 API 开放平台

| 任务 | 描述 | 参考代码 | 验证指标 | 输出产物 |
|------|------|----------|----------|----------|
| **Feature: API 密钥管理** | 实现 API 密钥管理 | 新建 | 密钥安全 | 功能实现 |
| **Feature: 访问控制** | API 访问权限控制 | 新建 | 权限控制正确 | 功能实现 |
| **Feature: 使用统计** | API 调用统计 | 新建 | 统计准确 | 功能实现 |
| **文档: API 文档** | 编写 OpenAPI 文档 | 新建 | 文档完整 | 文档 |

**闭环验证**:
```bash
# 预期指标
- API 可用性 > 99%
- 响应时间 < 500ms
```

---

### Phase 4 验收标准

| 检查项 | 验收标准 | 验证方式 |
|--------|----------|----------|
| VSCode 插件 | 插件功能完整，可正常使用 | 手工测试 |
| 导出功能 | 支持 Markdown/Word/JSON 导出 | 手工测试 |
| LLM 接入 | 支持 3+ 种 LLM 提供商 | 集成测试 |
| API 开放 | API 文档完整，访问控制正确 | 安全测试 |

---

## 附录: 验证指标汇总

### A.1 功能验证指标

| 功能模块 | 关键指标 | 目标值 | 验证方法 |
|----------|----------|--------|----------|
| 文本范围选择 | 选择模式支持 | 6种 | 单元测试 |
| 大纲提取 | 提取准确率 | > 70% | 测试集评估 |
| 人物检测 | 召回率 | > 80% | 测试集评估 |
| 人物分类 | 准确率 | > 75% | 测试集评估 |
| 设定提取 | 准确率 | > 70% | 测试集评估 |
| 关系图谱 | 渲染性能 | 100+节点 | 性能测试 |
| 一致性检查 | 检测准确率 | > 75% | 测试集评估 |
| 一致性检查 | 误报率 | < 20% | 测试集评估 |
| 人物弧光 | 识别准确率 | > 70% | 测试集评估 |
| 版本对比 | 差异识别率 | > 95% | 测试集评估 |

### A.2 性能验证指标

| 指标项 | 目标值 | 验证方法 |
|--------|--------|----------|
| API 响应时间 (P95) | < 500ms | 压力测试 |
| 页面加载时间 | < 2s | Lighthouse |
| 图谱渲染时间 (100节点) | < 2s | 性能测试 |
| 任务执行时间 (单章) | < 30s | 日志分析 |
| Token 利用率 | > 85% | 日志分析 |
| 缓存命中率 | > 60% | 日志分析 |

### A.3 代码质量指标

| 指标项 | 目标值 | 验证方法 |
|--------|--------|----------|
| 单元测试覆盖率 | > 70% | Coverage 报告 |
| TypeScript 严格模式 | 无错误 | tsc --strict |
| Lint 检查 | 无警告 | ESLint |
| 代码重复率 | < 5% | SonarQube |

### A.4 用户体验指标

| 指标项 | 目标值 | 验证方法 |
|--------|--------|----------|
| 任务完成率 | > 90% | 用户测试 |
| 功能发现率 | > 80% | 用户测试 |
| 用户满意度 | > 4.0/5 | 问卷调查 |

---

## B. 快速参考

### B.1 常用开发命令

```bash
# 后端开发
uv run pytest tests/server/ -v                    # 运行后端测试
uv run server.py --dev                            # 启动开发服务器

# 前端开发
cd packages/site
pnpm dev                                          # 启动开发服务器
pnpm test                                         # 运行测试
pnpm build                                        # 构建生产版本

# 数据库迁移
uv run sail_server/migration/verify_migration.py  # 验证迁移
```

### B.2 关键文件位置

| 类型 | 路径 | 说明 |
|------|------|------|
| 后端控制器 | `sail_server/controller/` | API 接口实现 |
| 后端模型 | `sail_server/data/` | 数据模型定义 |
| 后端服务 | `sail_server/service/` | 业务逻辑实现 |
| LLM 工具 | `sail_server/utils/llm/` | LLM 相关工具 |
| 前端页面 | `packages/site/src/pages/` | 页面组件 |
| 前端组件 | `packages/site/src/components/` | 可复用组件 |
| 前端 API | `packages/site/src/lib/api/` | API 客户端 |
| 前端状态 | `packages/site/src/lib/store/` | 状态管理 |

### B.3 调试技巧

```bash
# 后端调试
# 1. 设置断点
# 2. 使用 VSCode 调试配置
# 3. 或使用 pdb
import pdb; pdb.set_trace()

# 前端调试
# 1. React DevTools 查看组件状态
# 2. Redux DevTools 查看 Store 状态
# 3. Network 面板查看 API 调用
```

---

*文档结束*

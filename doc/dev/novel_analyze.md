# 作品大纲分析模块开发计划

基于 `doc/design/manager/novel_analyse.md` 设计文档的分阶段实现计划。

## 项目概述

**目标**：为 SailZen 添加作品分析功能，支持从已导入的长篇小说中提取大纲、识别人物、管理设定，并提供人工+AI混合的分析工作流。

**前置依赖**：
- 文本管理模块已实现（`text.py` 相关代码）
- PostgreSQL 数据库已配置
- 基本的前端框架已搭建

---

## Phase 1: 基础数据模型

### 1.1 数据库迁移

**文件**: `sail_server/migration/create_novel_analysis_tables.sql`

**任务清单**：

- [ ] 创建大纲相关表
  - `outlines` - 大纲表
  - `outline_nodes` - 大纲节点表
  - `outline_events` - 大纲事件表

- [ ] 创建人物相关表
  - `characters` - 人物表
  - `character_aliases` - 人物别名表
  - `character_attributes` - 人物属性表
  - `character_arcs` - 人物弧线表
  - `character_relations` - 人物关系表

- [ ] 创建设定相关表
  - `settings` - 设定表
  - `setting_attributes` - 设定属性表
  - `setting_relations` - 设定关系表
  - `character_setting_links` - 人物-设定关联表

- [ ] 创建分析任务相关表
  - `text_evidence` - 文本证据表
  - `analysis_tasks` - 分析任务表
  - `analysis_results` - 分析结果表

- [ ] 添加必要索引
  - 全文搜索索引（`gin_trgm_ops`）
  - 外键索引
  - 状态筛选索引

**验收标准**：
- 所有表成功创建
- 外键关系正确
- 测试数据可正常插入

### 1.2 ORM 模型实现

**文件**: `sail_server/data/analysis.py`

**任务清单**：

- [ ] 实现大纲 ORM 模型
  ```python
  class Outline(ORMBase)
  class OutlineNode(ORMBase)
  class OutlineEvent(ORMBase)
  ```

- [ ] 实现人物 ORM 模型
  ```python
  class Character(ORMBase)
  class CharacterAlias(ORMBase)
  class CharacterAttribute(ORMBase)
  class CharacterArc(ORMBase)
  class CharacterRelation(ORMBase)
  ```

- [ ] 实现设定 ORM 模型
  ```python
  class Setting(ORMBase)
  class SettingAttribute(ORMBase)
  class SettingRelation(ORMBase)
  class CharacterSettingLink(ORMBase)
  ```

- [ ] 实现分析任务 ORM 模型
  ```python
  class TextEvidence(ORMBase)
  class AnalysisTask(ORMBase)
  class AnalysisResult(ORMBase)
  ```

- [ ] 实现对应的 DTO 数据类
  ```python
  @dataclass
  class OutlineData
  class OutlineNodeData
  class CharacterData
  class SettingData
  class AnalysisTaskData
  # ... 等
  ```

**验收标准**：
- ORM 模型与数据库表一一对应
- DTO 提供 `read_from_orm()` 和 `create_orm()` 方法
- 关联关系正确配置

---

## Phase 2: 人工标注功能

### 2.1 人物管理业务逻辑

**文件**: `sail_server/model/analysis/character.py`

**任务清单**：

- [ ] 人物 CRUD 操作
  ```python
  def create_character_impl(db, data: CharacterData) -> CharacterData
  def get_character_impl(db, character_id: int) -> Optional[CharacterData]
  def get_characters_by_edition_impl(db, edition_id: int) -> List[CharacterData]
  def update_character_impl(db, character_id: int, data: CharacterData) -> Optional[CharacterData]
  def delete_character_impl(db, character_id: int) -> bool
  ```

- [ ] 人物别名管理
  ```python
  def add_character_alias_impl(db, character_id: int, alias: str, alias_type: str) -> CharacterAliasData
  def remove_character_alias_impl(db, alias_id: int) -> bool
  def get_character_by_alias_impl(db, edition_id: int, alias: str) -> Optional[CharacterData]
  ```

- [ ] 人物属性管理
  ```python
  def add_character_attribute_impl(db, character_id: int, category: str, key: str, value: Any) -> CharacterAttributeData
  def update_character_attribute_impl(db, attr_id: int, value: Any) -> CharacterAttributeData
  def get_character_profile_impl(db, character_id: int) -> Dict  # 完整人物档案
  ```

- [ ] 人物关系管理
  ```python
  def create_character_relation_impl(db, data: CharacterRelationData) -> CharacterRelationData
  def get_character_relations_impl(db, character_id: int) -> List[CharacterRelationData]
  def get_relation_graph_impl(db, edition_id: int) -> Dict  # 返回图数据结构
  ```

**验收标准**：
- 所有 CRUD 操作正确执行
- 别名模糊搜索可用
- 关系图数据结构可被前端直接使用

### 2.2 设定管理业务逻辑

**文件**: `sail_server/model/analysis/setting.py`

**任务清单**：

- [ ] 设定 CRUD 操作
  ```python
  def create_setting_impl(db, data: SettingData) -> SettingData
  def get_settings_by_edition_impl(db, edition_id: int, setting_type: Optional[str] = None) -> List[SettingData]
  def update_setting_impl(db, setting_id: int, data: SettingData) -> Optional[SettingData]
  def delete_setting_impl(db, setting_id: int) -> bool
  ```

- [ ] 设定属性管理
  ```python
  def add_setting_attribute_impl(db, setting_id: int, key: str, value: Any) -> SettingAttributeData
  def get_setting_detail_impl(db, setting_id: int) -> Dict  # 包含属性的完整设定
  ```

- [ ] 设定关系管理
  ```python
  def create_setting_relation_impl(db, data: SettingRelationData) -> SettingRelationData
  def get_setting_relations_impl(db, setting_id: int) -> List[SettingRelationData]
  ```

- [ ] 人物-设定关联
  ```python
  def link_character_setting_impl(db, character_id: int, setting_id: int, link_type: str) -> CharacterSettingLinkData
  def get_character_settings_impl(db, character_id: int) -> List[SettingData]
  def get_setting_characters_impl(db, setting_id: int) -> List[CharacterData]
  ```

**验收标准**：
- 按类型筛选设定可用
- 设定关系可正确建立
- 人物-设定双向查询可用

### 2.3 大纲管理业务逻辑

**文件**: `sail_server/model/analysis/outline.py`

**任务清单**：

- [ ] 大纲 CRUD 操作
  ```python
  def create_outline_impl(db, data: OutlineData) -> OutlineData
  def get_outlines_by_edition_impl(db, edition_id: int) -> List[OutlineData]
  def update_outline_impl(db, outline_id: int, data: OutlineData) -> Optional[OutlineData]
  def delete_outline_impl(db, outline_id: int) -> bool
  ```

- [ ] 大纲节点操作
  ```python
  def add_outline_node_impl(db, outline_id: int, parent_id: Optional[int], data: OutlineNodeData) -> OutlineNodeData
  def update_outline_node_impl(db, node_id: int, data: OutlineNodeData) -> Optional[OutlineNodeData]
  def delete_outline_node_impl(db, node_id: int) -> bool
  def move_outline_node_impl(db, node_id: int, new_parent_id: Optional[int], new_index: int) -> bool
  def get_outline_tree_impl(db, outline_id: int) -> Dict  # 返回树形结构
  ```

- [ ] 大纲事件操作
  ```python
  def add_outline_event_impl(db, node_id: int, data: OutlineEventData) -> OutlineEventData
  def get_node_events_impl(db, node_id: int) -> List[OutlineEventData]
  ```

- [ ] 链接章节功能
  ```python
  def link_node_to_chapters_impl(db, node_id: int, start_chapter_id: int, end_chapter_id: Optional[int]) -> bool
  ```

**验收标准**：
- 大纲树形结构正确维护（path 字段自动更新）
- 节点移动不破坏树结构
- 可链接到具体章节

### 2.4 文本证据管理

**文件**: `sail_server/model/analysis/evidence.py`

**任务清单**：

- [ ] 证据 CRUD 操作
  ```python
  def add_text_evidence_impl(db, data: TextEvidenceData) -> TextEvidenceData
  def get_evidence_for_target_impl(db, target_type: str, target_id: int) -> List[TextEvidenceData]
  def delete_text_evidence_impl(db, evidence_id: int) -> bool
  ```

- [ ] 章节标注查询
  ```python
  def get_chapter_annotations_impl(db, node_id: int) -> Dict  # 按类型分组的标注
  ```

**验收标准**：
- 证据可关联到任意实体
- 章节标注高亮区间不重叠时正确返回

---

## Phase 3: API 层实现

### 3.1 路由和控制器

**文件**: 
- `sail_server/router/analysis.py`
- `sail_server/controller/analysis.py`

**任务清单**：

- [ ] 人物 API
  ```python
  # POST /api/v1/analysis/character
  # GET /api/v1/analysis/character/{character_id}
  # PUT /api/v1/analysis/character/{character_id}
  # DELETE /api/v1/analysis/character/{character_id}
  # GET /api/v1/analysis/character/edition/{edition_id}
  # POST /api/v1/analysis/character/{character_id}/alias
  # POST /api/v1/analysis/character/{character_id}/attribute
  # GET /api/v1/analysis/character/{character_id}/profile
  # POST /api/v1/analysis/relation
  # GET /api/v1/analysis/relation/edition/{edition_id}
  ```

- [ ] 设定 API
  ```python
  # POST /api/v1/analysis/setting
  # GET /api/v1/analysis/setting/{setting_id}
  # PUT /api/v1/analysis/setting/{setting_id}
  # DELETE /api/v1/analysis/setting/{setting_id}
  # GET /api/v1/analysis/setting/edition/{edition_id}
  # POST /api/v1/analysis/setting/{setting_id}/attribute
  # POST /api/v1/analysis/setting/relation
  # POST /api/v1/analysis/character-setting-link
  ```

- [ ] 大纲 API
  ```python
  # POST /api/v1/analysis/outline
  # GET /api/v1/analysis/outline/{outline_id}
  # PUT /api/v1/analysis/outline/{outline_id}
  # DELETE /api/v1/analysis/outline/{outline_id}
  # GET /api/v1/analysis/outline/edition/{edition_id}
  # POST /api/v1/analysis/outline/{outline_id}/node
  # PUT /api/v1/analysis/outline/node/{node_id}
  # DELETE /api/v1/analysis/outline/node/{node_id}
  # GET /api/v1/analysis/outline/{outline_id}/tree
  # POST /api/v1/analysis/outline/node/{node_id}/event
  ```

- [ ] 证据 API
  ```python
  # POST /api/v1/analysis/evidence
  # GET /api/v1/analysis/evidence/target/{type}/{id}
  # DELETE /api/v1/analysis/evidence/{evidence_id}
  # GET /api/v1/analysis/chapter/{node_id}/annotations
  ```

**验收标准**：
- 所有 API 端点可访问
- 请求/响应格式符合设计
- 错误处理完善

### 3.2 前端 API 客户端

**文件**: `packages/site/src/lib/api/analysis.ts`

**任务清单**：

- [ ] 定义 TypeScript 类型
  ```typescript
  interface Character { ... }
  interface CharacterAlias { ... }
  interface Setting { ... }
  interface Outline { ... }
  interface OutlineNode { ... }
  interface AnalysisTask { ... }
  ```

- [ ] 实现 API 调用函数
  ```typescript
  // 人物
  export async function createCharacter(data: CreateCharacterRequest): Promise<Character>
  export async function getCharactersByEdition(editionId: number): Promise<Character[]>
  export async function getCharacterProfile(characterId: number): Promise<CharacterProfile>
  export async function getRelationGraph(editionId: number): Promise<RelationGraphData>
  
  // 设定
  export async function createSetting(data: CreateSettingRequest): Promise<Setting>
  export async function getSettingsByEdition(editionId: number, type?: string): Promise<Setting[]>
  
  // 大纲
  export async function createOutline(data: CreateOutlineRequest): Promise<Outline>
  export async function getOutlineTree(outlineId: number): Promise<OutlineTree>
  export async function addOutlineNode(outlineId: number, data: CreateNodeRequest): Promise<OutlineNode>
  ```

**验收标准**：
- API 调用封装完整
- 类型定义准确
- 错误处理统一

---

## Phase 4: 前端页面实现

### 4.1 人物管理页面

**文件**: `packages/site/src/pages/analysis/characters.tsx`

**任务清单**：

- [ ] 人物列表组件
  - 按角色类型筛选
  - 搜索人物名称/别名
  - 显示出场频率

- [ ] 人物编辑对话框
  - 基本信息编辑
  - 别名管理
  - 属性编辑（按分类）

- [ ] 人物档案详情页
  - 完整属性展示
  - 关系列表
  - 相关设定
  - 出场章节列表

**验收标准**：
- 人物可增删改查
- 别名可管理
- 属性分类清晰

### 4.2 人物关系图

**文件**: `packages/site/src/components/analysis/relation_graph.tsx`

**任务清单**：

- [ ] 使用力导向图布局（推荐 D3.js 或 @visx/network）
- [ ] 节点显示人物名称和头像（如有）
- [ ] 边显示关系类型
- [ ] 支持缩放和拖拽
- [ ] 点击节点高亮相关关系
- [ ] 关系类型筛选器

**验收标准**：
- 图谱正确渲染
- 交互流畅
- 大量节点时性能可接受

### 4.3 设定管理页面

**文件**: `packages/site/src/pages/analysis/settings.tsx`

**任务清单**：

- [ ] 设定列表组件
  - Tab 切换设定类型（物品/地点/组织等）
  - 分类筛选
  - 搜索

- [ ] 设定编辑对话框
  - 基本信息编辑
  - 属性编辑
  - 关联人物

- [ ] 设定详情卡片
  - 属性展示
  - 关联人物列表
  - 相关设定

**验收标准**：
- 按类型管理设定
- 属性可自定义
- 关联关系可建立

### 4.4 大纲管理页面

**文件**: `packages/site/src/pages/analysis/outline.tsx`

**任务清单**：

- [ ] 大纲树编辑器
  - 树形结构展示
  - 拖拽调整顺序和层级
  - 内联编辑标题
  - 展开/折叠节点

- [ ] 节点详情面板
  - 摘要编辑
  - 重要性标记
  - 链接章节
  - 添加事件

- [ ] 时间线视图（可选）
  - 按时间顺序展示事件
  - 显示事件类型颜色编码

**验收标准**：
- 大纲树可编辑
- 拖拽操作正确保存
- 与章节关联正确

### 4.5 章节标注视图

**文件**: `packages/site/src/components/analysis/chapter_annotation_view.tsx`

**任务清单**：

- [ ] 原文显示组件
  - 高亮显示已标注文本
  - 不同类型使用不同颜色

- [ ] 悬停提示
  - 显示标注详情
  - 快速跳转到实体

- [ ] 手动标注工具
  - 选中文本
  - 选择标注类型
  - 关联到已有实体或创建新实体

**验收标准**：
- 标注高亮正确
- 新增标注可保存
- 与实体正确关联

---

## Phase 5: AI 分析集成

### 5.1 分析任务调度器

**文件**: `sail_server/model/analysis/task_scheduler.py`

**任务清单**：

- [ ] 任务队列管理
  ```python
  def create_analysis_task_impl(db, data: AnalysisTaskData) -> AnalysisTaskData
  def get_pending_tasks_impl(db, limit: int = 10) -> List[AnalysisTaskData]
  def update_task_status_impl(db, task_id: int, status: str, result_summary: Optional[Dict] = None) -> bool
  def cancel_task_impl(db, task_id: int) -> bool
  ```

- [ ] 任务执行框架
  ```python
  class AnalysisTaskRunner:
      async def run_task(self, task: AnalysisTaskData) -> Dict
      async def run_outline_extraction(self, task: AnalysisTaskData) -> Dict
      async def run_character_detection(self, task: AnalysisTaskData) -> Dict
      async def run_setting_extraction(self, task: AnalysisTaskData) -> Dict
      async def run_relation_analysis(self, task: AnalysisTaskData) -> Dict
  ```

- [ ] 后台任务工作线程
  ```python
  class AnalysisWorker:
      async def start(self)
      async def stop(self)
      async def process_next_task(self)
  ```

**验收标准**：
- 任务可创建和调度
- 后台执行不阻塞主进程
- 任务状态正确更新

### 5.2 LLM 调用封装

**文件**: `sail_server/utils/llm.py`

**任务清单**：

- [ ] LLM 客户端封装
  ```python
  class LLMClient:
      def __init__(self, model: str = "gpt-4", api_key: Optional[str] = None)
      async def complete(self, prompt: str, temperature: float = 0.3) -> str
      async def complete_json(self, prompt: str, schema: Dict) -> Dict
  ```

- [ ] 提示词模板管理
  ```python
  class PromptTemplateManager:
      def get_template(self, template_name: str) -> str
      def render_template(self, template_name: str, variables: Dict) -> str
  ```

- [ ] 结果解析器
  ```python
  class AnalysisResultParser:
      def parse_outline_extraction(self, raw_result: str) -> List[OutlineNodeData]
      def parse_character_detection(self, raw_result: str) -> List[CharacterData]
      def parse_setting_extraction(self, raw_result: str) -> List[SettingData]
  ```

**验收标准**：
- LLM 调用可用
- 结果解析健壮
- 模板可外部配置

### 5.3 分析结果审核

**文件**: `sail_server/model/analysis/review.py`

**任务清单**：

- [ ] 结果存储
  ```python
  def save_analysis_results_impl(db, task_id: int, results: List[Dict]) -> List[AnalysisResultData]
  ```

- [ ] 审核操作
  ```python
  def approve_result_impl(db, result_id: int, reviewer: str) -> bool
  def reject_result_impl(db, result_id: int, reviewer: str, notes: str) -> bool
  def modify_result_impl(db, result_id: int, modified_data: Dict, reviewer: str) -> bool
  ```

- [ ] 批量应用
  ```python
  def apply_approved_results_impl(db, task_id: int) -> Dict  # 返回应用统计
  ```

**验收标准**：
- 结果可单独审核
- 批量应用正确写入主表
- 审核历史可追溯

### 5.4 分析任务 API

**文件**: 添加到 `sail_server/router/analysis.py`

**任务清单**：

- [ ] 任务管理 API
  ```python
  # POST /api/v1/analysis/task
  # GET /api/v1/analysis/task/{task_id}
  # GET /api/v1/analysis/task/edition/{edition_id}
  # POST /api/v1/analysis/task/{task_id}/cancel
  # POST /api/v1/analysis/task/{task_id}/retry
  ```

- [ ] 结果审核 API
  ```python
  # GET /api/v1/analysis/task/{task_id}/results
  # POST /api/v1/analysis/result/{result_id}/approve
  # POST /api/v1/analysis/result/{result_id}/reject
  # POST /api/v1/analysis/result/{result_id}/modify
  # POST /api/v1/analysis/task/{task_id}/apply-all
  ```

**验收标准**：
- 可创建各类分析任务
- 可查看任务状态和结果
- 审核流程完整

### 5.5 分析任务前端

**文件**: `packages/site/src/pages/analysis/tasks.tsx`

**任务清单**：

- [ ] 任务创建向导
  - 选择分析类型
  - 配置参数
  - 选择章节范围

- [ ] 任务列表
  - 状态筛选
  - 进度显示
  - 快速操作

- [ ] 结果审核页面
  - 逐条展示分析结果
  - 显示原文证据
  - 批准/拒绝/修改操作
  - 批量操作

**验收标准**：
- 可创建并监控任务
- 可审核分析结果
- 操作反馈及时

---

## Phase 6: 高级功能

### 6.1 规则匹配引擎

**文件**: `sail_server/utils/pattern_matcher.py`

**任务清单**：

- [ ] 人名模式匹配
  ```python
  class CharacterPatternMatcher:
      def find_potential_names(self, text: str) -> List[Tuple[str, int, int]]
      def merge_similar_names(self, names: List[str]) -> Dict[str, List[str]]
  ```

- [ ] 可配置规则
  ```python
  # 支持从配置文件加载
  patterns:
    character_names:
      - pattern: '「([^」]+)」'
        description: "对话中的人名"
      - pattern: '([^\s]{2,4})(?:道|说|笑道)'
        description: "说话动作前的人名"
  ```

**验收标准**：
- 常见人名格式可识别
- 规则可配置
- 与 LLM 结果可合并

### 6.2 统计与可视化

**任务清单**：

- [ ] 人物出场统计
  - 各章节出场频率
  - 出场曲线图

- [ ] 设定使用统计
  - 物品使用频率
  - 地点出现频率

- [ ] 大纲覆盖度
  - 已分析章节比例
  - 标注完成度

**验收标准**：
- 统计数据准确
- 图表可视化清晰

### 6.3 导出功能

**任务清单**：

- [ ] 大纲导出
  - Markdown 格式
  - JSON 格式

- [ ] 人物设定导出
  - 人物卡片 Markdown
  - 关系图 SVG

- [ ] 世界观文档导出
  - 完整世界观设定书

**验收标准**：
- 导出格式规范
- 内容完整

---

## 测试计划

### 单元测试

**文件**: `tests/server/test_analysis_*.py`

- [ ] 人物 CRUD 测试
- [ ] 设定 CRUD 测试
- [ ] 大纲树操作测试
- [ ] 证据关联测试
- [ ] 分析任务状态机测试

### 集成测试

- [ ] API 端到端测试
- [ ] LLM 集成测试（使用 mock）
- [ ] 前后端联调测试

### 性能测试

- [ ] 大量人物时关系图渲染
- [ ] 长篇小说大纲提取耗时
- [ ] 并发分析任务处理

---

## 技术债务与风险

### 已知技术债务

1. `text.md` 设计文档中定义的完整表结构尚未全部实现，本模块使用简化版本
2. 暂未实现 `universe` 跨作品世界观共享功能
3. 向量搜索功能暂未集成

### 风险项

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM API 调用成本 | 大规模分析成本高 | 设置限额，优先规则匹配 |
| LLM 结果不稳定 | 需要大量人工审核 | 调优提示词，设置高置信度阈值 |
| 大纲树操作复杂 | 前端实现难度大 | 使用成熟的树组件库 |
| 关系图性能 | 大量节点时卡顿 | 分层加载，虚拟化渲染 |

---

## 里程碑

| 里程碑 | 范围 | 关键交付物 |
|--------|------|------------|
| M1 | Phase 1 | 数据库表、ORM 模型 |
| M2 | Phase 2 | 人物/设定/大纲业务逻辑 |
| M3 | Phase 3 | 完整 API 层 |
| M4 | Phase 4 | 前端页面基础版 |
| M5 | Phase 5 | AI 分析功能 |
| M6 | Phase 6 | 高级功能、优化 |

---

## 文件清单

### 后端新增文件

```
sail_server/
├── migration/
│   └── create_novel_analysis_tables.sql   # 数据库迁移
├── data/
│   └── analysis.py                         # ORM 模型和 DTO
├── model/
│   └── analysis/
│       ├── __init__.py
│       ├── character.py                    # 人物业务逻辑
│       ├── setting.py                      # 设定业务逻辑
│       ├── outline.py                      # 大纲业务逻辑
│       ├── evidence.py                     # 证据业务逻辑
│       ├── task_scheduler.py               # 任务调度
│       └── review.py                       # 审核逻辑
├── controller/
│   └── analysis.py                         # API 控制器
├── router/
│   └── analysis.py                         # 路由定义
└── utils/
    ├── llm.py                              # LLM 调用封装
    └── pattern_matcher.py                  # 规则匹配
```

### 前端新增文件

```
packages/site/src/
├── pages/
│   └── analysis/
│       ├── index.tsx                       # 分析模块入口
│       ├── characters.tsx                  # 人物管理
│       ├── settings.tsx                    # 设定管理
│       ├── outline.tsx                     # 大纲管理
│       └── tasks.tsx                       # 任务管理
├── components/
│   └── analysis/
│       ├── character_list.tsx              # 人物列表
│       ├── character_edit_dialog.tsx       # 人物编辑
│       ├── character_profile.tsx           # 人物档案
│       ├── relation_graph.tsx              # 关系图
│       ├── setting_list.tsx                # 设定列表
│       ├── setting_edit_dialog.tsx         # 设定编辑
│       ├── outline_tree_editor.tsx         # 大纲树编辑器
│       ├── outline_node_panel.tsx          # 节点详情面板
│       ├── chapter_annotation_view.tsx     # 章节标注视图
│       ├── task_create_wizard.tsx          # 任务创建向导
│       └── result_review_panel.tsx         # 结果审核面板
└── lib/
    ├── api/
    │   └── analysis.ts                     # API 客户端
    └── data/
        └── analysis.ts                     # 类型定义
```

---

## 参考资料

- 设计文档: `doc/design/manager/novel_analyse.md`
- 文本管理设计: `doc/design/manager/text.md`
- 已实现的文本模块: `sail_server/data/text.py`, `sail_server/model/text.py`

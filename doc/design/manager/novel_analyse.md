# 作品大纲分析与管理模块

基于 `doc/design/manager/text.md` 文本内容管理器，扩展实现对作品的结构化分析与创作辅助功能。

## 1. 模块概述

### 1.1 设计目标

- **大纲提取**：从已导入的长篇小说中提取主线大纲、情节脉络
- **人物分析**：识别和管理作品中的人物形象、人物关系图谱
- **设定管理**：创建和维护世界观设定、物品系统、势力组织等
- **AI辅助工作流**：结合人工校对与LLM分析，实现半自动化的内容抽取
- **溯源支持**：所有分析结果可回溯到原文具体位置

### 1.2 核心能力

```
┌─────────────────────────────────────────────────────────────────────┐
│                         作品大纲分析模块                              │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  主线大纲   │  │  人物细纲   │  │  设定物品   │  │  关系图谱   │ │
│  │  Outline    │  │  Character  │  │  Setting    │  │  Relation   │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
│         │                │                │                │        │
│         └────────────────┴────────────────┴────────────────┘        │
│                                   │                                  │
│                    ┌──────────────┴──────────────┐                   │
│                    │     分析任务调度器          │                   │
│                    │   AnalysisTaskScheduler     │                   │
│                    └──────────────┬──────────────┘                   │
│                                   │                                  │
│         ┌─────────────────────────┼─────────────────────────┐        │
│         │                         │                         │        │
│  ┌──────▼──────┐          ┌───────▼──────┐          ┌───────▼──────┐│
│  │  人工标注   │          │  AI 分析     │          │  规则匹配    ││
│  │  Manual     │          │  LLM-based   │          │  Pattern     ││
│  └─────────────┘          └──────────────┘          └──────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 与现有模块关系

```
text.md (已实现)                    novel_analyse.md (本模块)
┌────────────────┐                  ┌────────────────────────────┐
│ works          │◄─────────────────│ outlines                   │
│ editions       │◄─────────────────│ characters                 │
│ document_nodes │◄─────────────────│ settings                   │
│ ingest_jobs    │                  │ analysis_tasks             │
└────────────────┘                  │ text_evidence              │
                                    └────────────────────────────┘
```

---

## 2. 数据模型设计

### 2.1 实体关系图

```
edition ──< outline ──< outline_node ──< text_evidence
    │           │
    │           └──< outline_event
    │
    ├──< character ──< character_alias
    │        │
    │        ├──< character_attribute ──< text_evidence
    │        │
    │        └──< character_arc ──< text_evidence
    │
    ├──< setting ──< setting_attribute ──< text_evidence
    │        │
    │        └──< setting_relation
    │
    ├──< character_relation ──< text_evidence
    │
    └──< analysis_task ──< analysis_result
```

### 2.2 表结构设计

#### 2.2.1 大纲相关表

```sql
-- ============================================================================
-- 大纲表 (outlines)
-- ============================================================================
CREATE TABLE outlines (
    id SERIAL PRIMARY KEY,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    outline_type VARCHAR NOT NULL DEFAULT 'main',  -- main | subplot | character_arc
    title VARCHAR NOT NULL,
    description TEXT,
    status VARCHAR DEFAULT 'draft',  -- draft | analyzing | reviewed | finalized
    source VARCHAR DEFAULT 'manual',  -- manual | ai_generated | hybrid
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_by VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_outlines_edition ON outlines(edition_id);
CREATE INDEX idx_outlines_type ON outlines(outline_type);

COMMENT ON TABLE outlines IS '大纲表 - 存储作品的各类大纲结构';

-- ============================================================================
-- 大纲节点表 (outline_nodes)
-- ============================================================================
CREATE TABLE outline_nodes (
    id SERIAL PRIMARY KEY,
    outline_id INTEGER NOT NULL REFERENCES outlines(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES outline_nodes(id) ON DELETE CASCADE,
    node_type VARCHAR NOT NULL,  -- act | arc | beat | scene | turning_point
    sort_index INTEGER NOT NULL,
    depth INTEGER NOT NULL DEFAULT 0,
    title VARCHAR NOT NULL,
    summary TEXT,
    significance VARCHAR DEFAULT 'normal',  -- critical | major | normal | minor
    chapter_start_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,
    chapter_end_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,
    path VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'draft',
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_outline_nodes_outline ON outline_nodes(outline_id);
CREATE INDEX idx_outline_nodes_parent ON outline_nodes(parent_id);
CREATE INDEX idx_outline_nodes_path ON outline_nodes(outline_id, path);

COMMENT ON TABLE outline_nodes IS '大纲节点表 - 树形结构表示情节层级';
COMMENT ON COLUMN outline_nodes.node_type IS '节点类型: act(幕), arc(弧), beat(节拍), scene(场景), turning_point(转折点)';
COMMENT ON COLUMN outline_nodes.significance IS '重要程度: critical(关键), major(主要), normal(普通), minor(次要)';

-- ============================================================================
-- 大纲事件表 (outline_events)
-- ============================================================================
CREATE TABLE outline_events (
    id SERIAL PRIMARY KEY,
    outline_node_id INTEGER NOT NULL REFERENCES outline_nodes(id) ON DELETE CASCADE,
    event_type VARCHAR NOT NULL,  -- plot | conflict | revelation | resolution | climax
    title VARCHAR NOT NULL,
    description TEXT,
    chronology_order NUMERIC(10, 2),  -- 故事内时间线顺序
    narrative_order INTEGER,  -- 叙事顺序（实际出现的章节顺序）
    importance VARCHAR DEFAULT 'normal',
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_outline_events_node ON outline_events(outline_node_id);
CREATE INDEX idx_outline_events_chrono ON outline_events(chronology_order);

COMMENT ON TABLE outline_events IS '大纲事件表 - 记录情节中的关键事件';
```

#### 2.2.2 人物相关表

```sql
-- ============================================================================
-- 人物表 (characters)
-- ============================================================================
CREATE TABLE characters (
    id SERIAL PRIMARY KEY,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    canonical_name VARCHAR NOT NULL,
    role_type VARCHAR DEFAULT 'supporting',  -- protagonist | antagonist | deuteragonist | supporting | minor | mentioned
    description TEXT,
    first_appearance_node_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,
    status VARCHAR DEFAULT 'draft',  -- draft | analyzed | reviewed | finalized
    source VARCHAR DEFAULT 'manual',
    importance_score NUMERIC(5, 4),  -- 0-1 基于出场频率等计算
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(edition_id, canonical_name)
);

CREATE INDEX idx_characters_edition ON characters(edition_id);
CREATE INDEX idx_characters_role ON characters(role_type);
CREATE INDEX idx_characters_name_trgm ON characters USING GIN (canonical_name gin_trgm_ops);

COMMENT ON TABLE characters IS '人物表 - 存储作品中的人物信息';
COMMENT ON COLUMN characters.role_type IS '角色类型: protagonist(主角), antagonist(反派), deuteragonist(二号主角), supporting(配角), minor(龙套), mentioned(提及)';

-- ============================================================================
-- 人物别名表 (character_aliases)
-- ============================================================================
CREATE TABLE character_aliases (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    alias VARCHAR NOT NULL,
    alias_type VARCHAR DEFAULT 'nickname',  -- nickname | title | formal_name | pen_name | code_name
    usage_context TEXT,  -- 使用场景说明
    is_preferred BOOLEAN DEFAULT FALSE,
    source VARCHAR DEFAULT 'manual',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(character_id, alias)
);

CREATE INDEX idx_character_aliases_char ON character_aliases(character_id);
CREATE INDEX idx_character_aliases_alias_trgm ON character_aliases USING GIN (alias gin_trgm_ops);

COMMENT ON TABLE character_aliases IS '人物别名表 - 存储人物的各种称呼';

-- ============================================================================
-- 人物属性表 (character_attributes)
-- ============================================================================
CREATE TABLE character_attributes (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    category VARCHAR NOT NULL,  -- basic | appearance | personality | ability | background | goal
    attr_key VARCHAR NOT NULL,
    attr_value JSONB NOT NULL,
    confidence NUMERIC(5, 4),  -- 置信度 0-1
    source VARCHAR DEFAULT 'manual',
    source_node_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,
    status VARCHAR DEFAULT 'pending',  -- pending | approved | rejected
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(character_id, category, attr_key)
);

CREATE INDEX idx_character_attrs_char ON character_attributes(character_id);
CREATE INDEX idx_character_attrs_category ON character_attributes(category);

COMMENT ON TABLE character_attributes IS '人物属性表 - 存储人物的各类属性';
COMMENT ON COLUMN character_attributes.category IS '属性类别: basic(基础), appearance(外貌), personality(性格), ability(能力), background(背景), goal(目标)';

-- ============================================================================
-- 人物弧线表 (character_arcs)
-- ============================================================================
CREATE TABLE character_arcs (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    arc_type VARCHAR NOT NULL,  -- growth | fall | flat | transformation | redemption
    title VARCHAR NOT NULL,
    description TEXT,
    start_node_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,
    end_node_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,
    status VARCHAR DEFAULT 'draft',
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_character_arcs_char ON character_arcs(character_id);

COMMENT ON TABLE character_arcs IS '人物弧线表 - 记录人物的成长变化轨迹';
COMMENT ON COLUMN character_arcs.arc_type IS '弧线类型: growth(成长), fall(堕落), flat(平稳), transformation(转变), redemption(救赎)';

-- ============================================================================
-- 人物关系表 (character_relations)
-- ============================================================================
CREATE TABLE character_relations (
    id SERIAL PRIMARY KEY,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    source_character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    target_character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    relation_type VARCHAR NOT NULL,  -- family | romance | friendship | rivalry | mentor | alliance | enemy
    relation_subtype VARCHAR,  -- 具体关系，如 family 下的 father, mother, sibling
    description TEXT,
    strength NUMERIC(5, 4),  -- 关系强度 0-1
    is_mutual BOOLEAN DEFAULT TRUE,  -- 是否双向关系
    start_node_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,  -- 关系开始的章节
    end_node_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,  -- 关系结束的章节（如有）
    status VARCHAR DEFAULT 'draft',
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_char_relations_edition ON character_relations(edition_id);
CREATE INDEX idx_char_relations_source ON character_relations(source_character_id);
CREATE INDEX idx_char_relations_target ON character_relations(target_character_id);

COMMENT ON TABLE character_relations IS '人物关系表 - 存储人物之间的关系';
```

#### 2.2.3 设定相关表

```sql
-- ============================================================================
-- 设定表 (settings)
-- ============================================================================
CREATE TABLE settings (
    id SERIAL PRIMARY KEY,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    setting_type VARCHAR NOT NULL,  -- item | location | organization | concept | magic_system | creature | event_type
    canonical_name VARCHAR NOT NULL,
    category VARCHAR,  -- 子分类，如 item 下的 weapon, artifact, consumable
    description TEXT,
    first_appearance_node_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,
    importance VARCHAR DEFAULT 'normal',  -- critical | major | normal | minor
    status VARCHAR DEFAULT 'draft',
    source VARCHAR DEFAULT 'manual',
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(edition_id, setting_type, canonical_name)
);

CREATE INDEX idx_settings_edition ON settings(edition_id);
CREATE INDEX idx_settings_type ON settings(setting_type);
CREATE INDEX idx_settings_name_trgm ON settings USING GIN (canonical_name gin_trgm_ops);

COMMENT ON TABLE settings IS '设定表 - 存储世界观设定元素';
COMMENT ON COLUMN settings.setting_type IS '设定类型: item(物品), location(地点), organization(组织), concept(概念), magic_system(力量体系), creature(生物), event_type(事件类型)';

-- ============================================================================
-- 设定属性表 (setting_attributes)
-- ============================================================================
CREATE TABLE setting_attributes (
    id SERIAL PRIMARY KEY,
    setting_id INTEGER NOT NULL REFERENCES settings(id) ON DELETE CASCADE,
    attr_key VARCHAR NOT NULL,
    attr_value JSONB NOT NULL,
    source VARCHAR DEFAULT 'manual',
    source_node_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,
    status VARCHAR DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(setting_id, attr_key)
);

CREATE INDEX idx_setting_attrs_setting ON setting_attributes(setting_id);

COMMENT ON TABLE setting_attributes IS '设定属性表 - 存储设定的详细属性';

-- ============================================================================
-- 设定关系表 (setting_relations)
-- ============================================================================
CREATE TABLE setting_relations (
    id SERIAL PRIMARY KEY,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    source_setting_id INTEGER NOT NULL REFERENCES settings(id) ON DELETE CASCADE,
    target_setting_id INTEGER NOT NULL REFERENCES settings(id) ON DELETE CASCADE,
    relation_type VARCHAR NOT NULL,  -- contains | belongs_to | produces | requires | opposes
    description TEXT,
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_setting_relations_source ON setting_relations(source_setting_id);
CREATE INDEX idx_setting_relations_target ON setting_relations(target_setting_id);

COMMENT ON TABLE setting_relations IS '设定关系表 - 存储设定之间的关系';

-- ============================================================================
-- 人物-设定关联表 (character_setting_links)
-- ============================================================================
CREATE TABLE character_setting_links (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    setting_id INTEGER NOT NULL REFERENCES settings(id) ON DELETE CASCADE,
    link_type VARCHAR NOT NULL,  -- owns | belongs_to | created | uses | guards
    description TEXT,
    start_node_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,
    end_node_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(character_id, setting_id, link_type)
);

CREATE INDEX idx_char_setting_links_char ON character_setting_links(character_id);
CREATE INDEX idx_char_setting_links_setting ON character_setting_links(setting_id);

COMMENT ON TABLE character_setting_links IS '人物-设定关联表 - 记录人物与设定的关系';
```

#### 2.2.4 文本证据与分析任务表

```sql
-- ============================================================================
-- 文本证据表 (text_evidence)
-- ============================================================================
CREATE TABLE text_evidence (
    id SERIAL PRIMARY KEY,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    node_id INTEGER NOT NULL REFERENCES document_nodes(id) ON DELETE CASCADE,
    target_type VARCHAR NOT NULL,  -- outline_node | character | character_attribute | setting | relation
    target_id INTEGER NOT NULL,
    start_char INTEGER,  -- 在章节内的起始字符位置
    end_char INTEGER,  -- 在章节内的结束字符位置
    text_snippet TEXT,  -- 证据文本片段
    context_before TEXT,  -- 前文上下文
    context_after TEXT,  -- 后文上下文
    evidence_type VARCHAR DEFAULT 'explicit',  -- explicit(明确) | implicit(隐含) | inferred(推断)
    confidence NUMERIC(5, 4),
    source VARCHAR DEFAULT 'manual',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_text_evidence_edition ON text_evidence(edition_id);
CREATE INDEX idx_text_evidence_node ON text_evidence(node_id);
CREATE INDEX idx_text_evidence_target ON text_evidence(target_type, target_id);

COMMENT ON TABLE text_evidence IS '文本证据表 - 存储分析结果的原文依据';
COMMENT ON COLUMN text_evidence.evidence_type IS '证据类型: explicit(明确陈述), implicit(隐含暗示), inferred(推断得出)';

-- ============================================================================
-- 分析任务表 (analysis_tasks)
-- ============================================================================
CREATE TABLE analysis_tasks (
    id SERIAL PRIMARY KEY,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    task_type VARCHAR NOT NULL,  -- outline_extraction | character_detection | setting_extraction | relation_analysis | attribute_extraction
    target_scope VARCHAR NOT NULL,  -- full | range | chapter
    target_node_ids INTEGER[],  -- 目标章节ID列表
    parameters JSONB DEFAULT '{}'::jsonb,
    llm_model VARCHAR,  -- 使用的LLM模型
    llm_prompt_template VARCHAR,  -- 使用的提示词模板
    status VARCHAR DEFAULT 'pending',  -- pending | running | completed | failed | cancelled
    priority INTEGER DEFAULT 0,
    scheduled_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    result_summary JSONB,
    created_by VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analysis_tasks_edition ON analysis_tasks(edition_id);
CREATE INDEX idx_analysis_tasks_status ON analysis_tasks(status);
CREATE INDEX idx_analysis_tasks_type ON analysis_tasks(task_type);

COMMENT ON TABLE analysis_tasks IS '分析任务表 - 管理AI分析和人工标注任务';
COMMENT ON COLUMN analysis_tasks.task_type IS '任务类型: outline_extraction(大纲提取), character_detection(人物识别), setting_extraction(设定提取), relation_analysis(关系分析), attribute_extraction(属性提取)';

-- ============================================================================
-- 分析结果表 (analysis_results)
-- ============================================================================
CREATE TABLE analysis_results (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES analysis_tasks(id) ON DELETE CASCADE,
    result_type VARCHAR NOT NULL,  -- 与 target_type 对应
    result_data JSONB NOT NULL,  -- 结构化的分析结果
    confidence NUMERIC(5, 4),
    review_status VARCHAR DEFAULT 'pending',  -- pending | approved | rejected | modified
    reviewer VARCHAR,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    review_notes TEXT,
    applied BOOLEAN DEFAULT FALSE,  -- 是否已应用到主表
    applied_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analysis_results_task ON analysis_results(task_id);
CREATE INDEX idx_analysis_results_status ON analysis_results(review_status);

COMMENT ON TABLE analysis_results IS '分析结果表 - 存储待审核的分析结果';
```

---

## 3. 分析工作流设计

### 3.1 工作流概览

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           分析工作流                                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │
│  │ 任务创建 │ -> │ 文本准备 │ -> │ 分析执行 │ -> │ 结果审核 │ -> │ 数据应用 │ │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘ │
│       │              │              │              │              │      │
│       ▼              ▼              ▼              ▼              ▼      │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │
│  │ 选择范围 │    │ 分段切片 │    │ AI/人工 │    │ 校对确认 │    │ 写入主表 │ │
│  │ 设置参数 │    │ 上下文   │    │ 混合模式 │    │ 修正补充 │    │ 更新索引 │ │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘ │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 任务类型定义

#### 3.2.1 大纲提取 (outline_extraction)

```python
class OutlineExtractionConfig:
    """大纲提取任务配置"""
    outline_type: str  # main | subplot | character_arc
    granularity: str  # act | arc | beat  # 提取粒度
    include_events: bool = True
    max_nodes_per_level: int = 10
    
    # LLM 参数
    llm_model: str = "gpt-4"
    temperature: float = 0.3
    
    # 提示词模板
    prompt_template: str = "outline_extraction_v1"
```

**处理流程**：
1. 按章节范围分批处理
2. 每批提取局部情节点
3. 合并生成完整大纲树
4. 识别关键转折点
5. 生成文本证据链接

#### 3.2.2 人物识别 (character_detection)

```python
class CharacterDetectionConfig:
    """人物识别任务配置"""
    detect_aliases: bool = True
    detect_roles: bool = True
    min_mention_count: int = 3  # 最少出场次数
    merge_similar: bool = True  # 合并相似名称
    
    # 规则匹配
    use_pattern_matching: bool = True
    name_patterns: List[str] = [
        r'「([^」]+)」',  # 对话中的人名
        r'([^\s]{2,4})(?:道|说|笑道)',  # 说话动作前的人名
    ]
```

**处理流程**：
1. 规则匹配初筛人名候选
2. LLM 分析上下文确认
3. 合并别名和同一人物
4. 判断角色重要性
5. 记录首次出场位置

#### 3.2.3 设定提取 (setting_extraction)

```python
class SettingExtractionConfig:
    """设定提取任务配置"""
    setting_types: List[str]  # item | location | organization | ...
    extract_attributes: bool = True
    detect_relations: bool = True
    
    # 分类特定配置
    item_config: Dict = {
        "categories": ["weapon", "artifact", "consumable", "material"],
        "extract_effects": True,
    }
    
    location_config: Dict = {
        "extract_geography": True,
        "build_hierarchy": True,  # 构建地点层级
    }
```

**处理流程**：
1. 按设定类型分批提取
2. 识别设定的属性信息
3. 建立设定之间的关系
4. 关联到人物（持有/归属）
5. 标记重要程度

#### 3.2.4 关系分析 (relation_analysis)

```python
class RelationAnalysisConfig:
    """关系分析任务配置"""
    relation_types: List[str]  # family | romance | friendship | ...
    detect_changes: bool = True  # 检测关系变化
    build_timeline: bool = True  # 构建关系时间线
    
    # 图谱参数
    max_depth: int = 2  # 关系图最大深度
    include_indirect: bool = False  # 是否包含间接关系
```

**处理流程**：
1. 基于已识别人物进行分析
2. 提取直接描述的关系
3. 推断隐含的关系
4. 检测关系状态变化
5. 构建关系图谱

### 3.3 人工-AI 混合模式

#### 3.3.1 模式选择

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **Pure Manual** | 完全人工标注 | 小规模、高精度需求 |
| **AI-Assist** | AI 生成初稿，人工审核修改 | 推荐模式，平衡效率和质量 |
| **AI-Auto** | AI 自动处理，低置信度触发人工 | 大规模批处理 |
| **Pattern-First** | 规则匹配优先，AI 补充 | 格式规范的内容 |

#### 3.3.2 审核工作流

```
┌────────────────────────────────────────────────────────────────┐
│                      结果审核流程                               │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│   AI 分析结果                                                   │
│        │                                                       │
│        ▼                                                       │
│   ┌─────────────────┐                                          │
│   │ 置信度 >= 0.9   │──Yes──> 自动应用                         │
│   └────────┬────────┘                                          │
│            │ No                                                │
│            ▼                                                   │
│   ┌─────────────────┐                                          │
│   │ 置信度 >= 0.7   │──Yes──> 人工快速确认                     │
│   └────────┬────────┘                                          │
│            │ No                                                │
│            ▼                                                   │
│   ┌─────────────────┐                                          │
│   │ 置信度 >= 0.5   │──Yes──> 人工详细审核                     │
│   └────────┬────────┘                                          │
│            │ No                                                │
│            ▼                                                   │
│        丢弃或标记为待人工补充                                   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 4. API 设计

### 4.1 大纲管理 API

```yaml
# 大纲 CRUD
POST   /api/v1/analysis/outline                    # 创建大纲
GET    /api/v1/analysis/outline/{outline_id}       # 获取大纲详情
PUT    /api/v1/analysis/outline/{outline_id}       # 更新大纲
DELETE /api/v1/analysis/outline/{outline_id}       # 删除大纲
GET    /api/v1/analysis/outline/edition/{edition_id}  # 获取版本的所有大纲

# 大纲节点操作
POST   /api/v1/analysis/outline/{outline_id}/node      # 添加节点
PUT    /api/v1/analysis/outline/node/{node_id}         # 更新节点
DELETE /api/v1/analysis/outline/node/{node_id}         # 删除节点
GET    /api/v1/analysis/outline/{outline_id}/tree      # 获取大纲树

# 大纲事件
POST   /api/v1/analysis/outline/node/{node_id}/event   # 添加事件
```

### 4.2 人物管理 API

```yaml
# 人物 CRUD
POST   /api/v1/analysis/character                      # 创建人物
GET    /api/v1/analysis/character/{character_id}       # 获取人物详情
PUT    /api/v1/analysis/character/{character_id}       # 更新人物
DELETE /api/v1/analysis/character/{character_id}       # 删除人物
GET    /api/v1/analysis/character/edition/{edition_id} # 获取版本的所有人物

# 人物别名
POST   /api/v1/analysis/character/{character_id}/alias      # 添加别名
DELETE /api/v1/analysis/character/alias/{alias_id}          # 删除别名

# 人物属性
POST   /api/v1/analysis/character/{character_id}/attribute  # 添加属性
PUT    /api/v1/analysis/character/attribute/{attr_id}       # 更新属性
GET    /api/v1/analysis/character/{character_id}/profile    # 获取完整人物档案

# 人物弧线
POST   /api/v1/analysis/character/{character_id}/arc        # 添加弧线
GET    /api/v1/analysis/character/{character_id}/arcs       # 获取人物弧线

# 人物关系
POST   /api/v1/analysis/relation                     # 创建关系
GET    /api/v1/analysis/relation/edition/{edition_id}  # 获取版本的关系图
GET    /api/v1/analysis/relation/character/{character_id}  # 获取人物的关系
```

### 4.3 设定管理 API

```yaml
# 设定 CRUD
POST   /api/v1/analysis/setting                      # 创建设定
GET    /api/v1/analysis/setting/{setting_id}         # 获取设定详情
PUT    /api/v1/analysis/setting/{setting_id}         # 更新设定
DELETE /api/v1/analysis/setting/{setting_id}         # 删除设定
GET    /api/v1/analysis/setting/edition/{edition_id} # 获取版本的设定
GET    /api/v1/analysis/setting/type/{type}          # 按类型获取设定

# 设定属性
POST   /api/v1/analysis/setting/{setting_id}/attribute  # 添加属性

# 设定关系
POST   /api/v1/analysis/setting/relation             # 创建设定关系

# 人物-设定关联
POST   /api/v1/analysis/character-setting-link       # 创建关联
```

### 4.4 分析任务 API

```yaml
# 任务管理
POST   /api/v1/analysis/task                         # 创建分析任务
GET    /api/v1/analysis/task/{task_id}               # 获取任务状态
GET    /api/v1/analysis/task/edition/{edition_id}    # 获取版本的任务列表
POST   /api/v1/analysis/task/{task_id}/cancel        # 取消任务
POST   /api/v1/analysis/task/{task_id}/retry         # 重试任务

# 结果审核
GET    /api/v1/analysis/task/{task_id}/results       # 获取任务结果
POST   /api/v1/analysis/result/{result_id}/approve   # 批准结果
POST   /api/v1/analysis/result/{result_id}/reject    # 拒绝结果
POST   /api/v1/analysis/result/{result_id}/modify    # 修改并应用
POST   /api/v1/analysis/task/{task_id}/apply-all     # 批量应用所有已批准结果
```

### 4.5 文本证据 API

```yaml
# 证据查询
GET    /api/v1/analysis/evidence/target/{type}/{id}  # 获取目标的证据
POST   /api/v1/analysis/evidence                     # 添加证据
DELETE /api/v1/analysis/evidence/{evidence_id}       # 删除证据

# 章节分析视图
GET    /api/v1/analysis/chapter/{node_id}/annotations  # 获取章节的所有标注
```

---

## 5. 前端页面设计

### 5.1 页面结构

```
/text/{work_id}/analysis
├── /outline          # 大纲管理页
│   ├── /tree         # 大纲树视图
│   ├── /timeline     # 时间线视图
│   └── /edit/{id}    # 大纲编辑
├── /characters       # 人物管理页
│   ├── /list         # 人物列表
│   ├── /graph        # 关系图谱
│   └── /profile/{id} # 人物档案
├── /settings         # 设定管理页
│   ├── /items        # 物品设定
│   ├── /locations    # 地点设定
│   └── /organizations # 组织设定
└── /tasks            # 分析任务页
    ├── /list         # 任务列表
    └── /review/{id}  # 结果审核
```

### 5.2 核心组件

#### 5.2.1 大纲树编辑器 (OutlineTreeEditor)

```tsx
interface OutlineTreeEditorProps {
  outlineId: number;
  editionId: number;
  onNodeSelect: (node: OutlineNode) => void;
}

// 功能：
// - 拖拽调整节点层级和顺序
// - 内联编辑节点标题和摘要
// - 链接到原文章节
// - 标记节点重要性
// - 添加/删除节点
```

#### 5.2.2 人物关系图 (CharacterRelationGraph)

```tsx
interface CharacterRelationGraphProps {
  editionId: number;
  focusCharacterId?: number;
  relationTypes?: string[];
}

// 功能：
// - 力导向图展示人物关系
// - 点击人物查看详情
// - 筛选关系类型
// - 高亮特定人物的关系网
```

#### 5.2.3 分析任务面板 (AnalysisTaskPanel)

```tsx
interface AnalysisTaskPanelProps {
  editionId: number;
}

// 功能：
// - 创建新分析任务
// - 查看任务进度
// - 审核分析结果
// - 批量操作
```

#### 5.2.4 章节标注视图 (ChapterAnnotationView)

```tsx
interface ChapterAnnotationViewProps {
  nodeId: number;
  showEvidence: boolean;
}

// 功能：
// - 原文阅读
// - 高亮显示已标注内容
// - 悬停查看标注详情
// - 手动添加标注
```

---

## 6. LLM 提示词模板

### 6.1 大纲提取模板

```markdown
# 任务：提取小说章节的情节大纲

## 输入
- 章节范围：第 {start_chapter} 章至第 {end_chapter} 章
- 章节内容：
{chapter_contents}

## 要求
1. 识别主要情节点（plot points）
2. 标注情节类型：冲突、转折、高潮、解决等
3. 评估每个情节点的重要程度（1-5）
4. 提取关键对话和行动
5. 识别涉及的人物

## 输出格式
```json
{
  "plot_points": [
    {
      "title": "情节标题",
      "type": "conflict|revelation|climax|resolution",
      "importance": 1-5,
      "summary": "简要描述",
      "chapter_range": [start, end],
      "evidence": "原文引用",
      "characters": ["人物1", "人物2"]
    }
  ],
  "overall_summary": "本段落的整体概述"
}
```
```

### 6.2 人物识别模板

```markdown
# 任务：识别小说中的人物

## 输入
- 章节内容：
{chapter_content}

## 要求
1. 识别所有出现的人物名称
2. 合并同一人物的不同称呼
3. 判断人物在本章的重要程度
4. 提取人物的基本特征描述

## 输出格式
```json
{
  "characters": [
    {
      "canonical_name": "标准名称",
      "aliases": ["别名1", "别名2"],
      "role_in_chapter": "protagonist|supporting|mentioned",
      "first_mention": "首次出现的句子",
      "description": "本章对该人物的描述",
      "actions": ["主要行动1", "主要行动2"]
    }
  ]
}
```
```

### 6.3 设定提取模板

```markdown
# 任务：提取世界观设定元素

## 输入
- 设定类型：{setting_type}  # item | location | organization
- 章节内容：
{chapter_content}

## 要求
1. 识别本章出现的所有{setting_type}
2. 提取其名称、描述、属性
3. 识别与人物的关联
4. 判断重要程度

## 输出格式
```json
{
  "settings": [
    {
      "name": "名称",
      "type": "{setting_type}",
      "category": "子类别",
      "description": "描述",
      "attributes": {
        "属性名": "属性值"
      },
      "related_characters": ["人物1"],
      "importance": "critical|major|normal|minor",
      "evidence": "原文引用"
    }
  ]
}
```
```

---

## 7. 实现优先级

### Phase 1: 基础数据模型
- [ ] 创建数据库表（迁移脚本）
- [ ] 实现 ORM 模型和 DTO
- [ ] 基础 CRUD API

### Phase 2: 人工标注功能
- [ ] 人物手动创建和管理
- [ ] 设定手动创建和管理
- [ ] 大纲手动编辑
- [ ] 文本证据关联

### Phase 3: AI 分析集成
- [ ] 分析任务调度器
- [ ] LLM 调用封装
- [ ] 结果解析和存储
- [ ] 审核工作流

### Phase 4: 前端交互
- [ ] 大纲树编辑器
- [ ] 人物关系图
- [ ] 章节标注视图
- [ ] 分析任务面板

### Phase 5: 高级功能
- [ ] 批量分析优化
- [ ] 跨作品实体合并
- [ ] 统计和可视化
- [ ] 导出功能

---

## 8. 技术实现要点

### 8.1 性能优化
- 大纲树使用 `path` 字段 materialized path 模式，支持高效的层级查询
- 人物别名使用 `pg_trgm` 扩展进行模糊匹配
- 分析任务使用队列机制，避免阻塞主请求

### 8.2 数据一致性
- 分析结果先存入 `analysis_results`，审核通过后才写入主表
- 使用事务保证数据完整性
- 软删除保留历史记录

### 8.3 扩展性
- `meta_data` JSONB 字段存储扩展属性
- 任务参数使用 JSONB 配置，支持未来新任务类型
- 提示词模板外部化管理

---

## 9. 与其他模块集成

### 9.1 与 text.md 集成
- 复用 `document_nodes` 作为文本证据的锚点
- 复用 `editions` 和 `works` 的层级结构
- 可选择性实现 `text.md` 中定义的完整表结构

### 9.2 与 necessity.md 物品管理集成
- 可考虑将虚拟世界的物品设定与现实物品管理形成映射
- 共享物品分类体系

### 9.3 未来集成可能
- 向量数据库集成（语义搜索）
- 知识图谱可视化
- 创作辅助建议系统

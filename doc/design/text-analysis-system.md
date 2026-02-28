# SailZen 文本分析系统产品设计文档

## 文档信息

- **版本**: 1.0
- **日期**: 2025-02-28
- **状态**: 设计阶段
- **作者**: AI Agent

---

## 1. 概述

### 1.1 产品背景

SailZen 目前已完成基础的文本管理功能（作品/版本/章节管理）和初步的分析数据模型（人物、设定、大纲、证据）。本设计文档旨在系统化地规划**文本分析工作流**，构建一个完整的小说辅助创作与分析平台。

### 1.2 设计目标

1. **结构化分析**: 将非结构化文本转化为可查询、可分析的结构化数据
2. **人机协作**: AI 辅助提取 + 人工审核确认的工作流
3. **上下文工程**: 支持灵活的文本范围选择和 Context 构建
4. **证据追踪**: 所有分析结果均可追溯至原文出处
5. **创作辅助**: 为作者提供人物一致性检查、情节逻辑验证等工具

### 1.3 核心用户场景

| 场景 | 描述 | 优先级 |
|------|------|--------|
| 大纲提取 | 从已有文本中提取/生成故事大纲 | P0 |
| 人物档案 | 构建人物画像，追踪人物弧光 | P0 |
| 设定管理 | 管理世界观设定，检查设定一致性 | P0 |
| 文本证据 | 为分析结论标注原文证据 | P1 |
| 关系图谱 | 可视化人物/设定之间的关系 | P1 |
| 创作辅助 | 基于已有内容提供续写建议 | P2 |

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端 (React + TypeScript)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ 文本阅读器   │  │ 分析工作台   │  │ 可视化视图   │  │ 任务管理面板     │ │
│  │ ChapterReader│  │ AnalysisHub  │  │ GraphView    │  │ TaskPanel        │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                     文本范围选择器 (TextRangeSelector)                  │ │
│  │   [章节多选] [范围滑块] [全文] [自定义范围(输入页码/字数)]              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API 层 (Litestar + Python)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ /text        │  │ /analysis    │  │ /analysis/   │  │ /analysis/task-  │ │
│  │ 文本管理     │  │ 分析数据 CRUD│  │ llm          │  │ execution        │ │
│  │              │  │              │  │ LLM 分析接口 │  │ 任务执行管理     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         服务层 (Service Layer)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    任务调度器 (AnalysisTaskRunner)                    │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │  │
│  │  │ 分块策略     │  │ 进度追踪     │  │ 结果合并     │               │  │
│  │  │ Chunking     │  │ Progress     │  │ Merge        │               │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    Context 工程 (ContextBuilder)                      │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │  │
│  │  │ 文本获取     │  │ 上下文组装   │  │ Token 控制   │               │  │
│  │  │ Fetch        │  │ Assemble     │  │ Budget       │               │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         数据层 (PostgreSQL + SQLAlchemy)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ works        │  │ characters   │  │ outlines     │  │ analysis_tasks   │ │
│  │ editions     │  │ settings     │  │ outline_nodes│  │ analysis_results │ │
│  │ document_    │  │ relations    │  │ events       │  │ text_evidence    │ │
│  │ nodes        │  │ character_   │  │              │  │                  │ │
│  │              │  │ arcs         │  │              │  │                  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据模型关系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据模型关系图                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Work (作品)
  │
  ├──► Edition (版本)
  │      │
  │      ├──► DocumentNode (章节) ◄──────────────┐
  │      │      │                                 │
  │      │      └── referenced by ────────────────┤
  │      │                                        │
  │      ├──► Character (人物)                    │
  │      │      ├──► CharacterAlias (别名)        │
  │      │      ├──► CharacterAttribute (属性)    │
  │      │      ├──► CharacterArc (人物弧光)      │
  │      │      └──► CharacterRelation (关系)     │
  │      │                                         │
  │      ├──► Setting (设定) ◄────────────────────┤
  │      │      ├──► SettingAttribute (属性)      │
  │      │      └──► SettingRelation (设定关系)   │
  │      │                                         │
  │      ├──► Outline (大纲)                      │
  │      │      └──► OutlineNode (大纲节点)       │
  │      │             └──► OutlineEvent (事件)   │
  │      │                                         │
  │      ├──► AnalysisTask (分析任务)             │
  │      │      └──► AnalysisResult (分析结果)    │
  │      │                                         │
  │      └──► TextEvidence (文本证据) ────────────┘
  │             (关联到 DocumentNode 和各类分析实体)
```

---

## 3. 核心功能模块

### 3.1 文本范围选择器 (Text Range Selector)

#### 3.1.1 功能描述

提供灵活的方式选择需要分析的文本范围，支持多种选择模式。

#### 3.1.2 选择模式

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| `single_chapter` | 单章选择 | 精细分析特定章节 |
| `chapter_range` | 连续多章 | 分析情节段落 |
| `discrete_chapters` | 离散多选 | 对比分析 |
| `full_text` | 全文 | 整体分析 |
| `custom_range` | 自定义范围 | 精确到段落/字数 |
| `by_outline_node` | 按大纲节点 | 分析特定情节单元 |

#### 3.1.3 数据结构

```typescript
interface TextRangeSelection {
  mode: 'single_chapter' | 'chapter_range' | 'discrete_chapters' | 
        'full_text' | 'custom_range' | 'by_outline_node';
  edition_id: number;
  // 模式特定字段
  chapter_index?: number;           // single_chapter
  chapter_start?: number;           // chapter_range
  chapter_end?: number;             // chapter_range
  chapter_indices?: number[];       // discrete_chapters
  outline_node_id?: number;         // by_outline_node
  custom_start_char?: number;       // custom_range
  custom_end_char?: number;         // custom_range
  // 元数据
  estimated_tokens: number;
  estimated_chars: number;
}
```

#### 3.1.4 UI 设计

```
┌─────────────────────────────────────────────────────────────────┐
│  📄 文本范围选择                                    [?] [帮助]  │
├─────────────────────────────────────────────────────────────────┤
│  选择模式:                                                      │
│  [● 单章] [○ 连续范围] [○ 多选] [○ 全文] [○ 大纲节点] [○ 自定义] │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 目录树 (可展开/折叠)                                     │   │
│  │ ▼ 第一卷                                                │   │
│  │   ☑ 第一章 起始 (5,200字)                               │   │
│  │   ☐ 第二章 启程 (8,100字)                               │   │
│  │ ▶ 第二卷                                                │   │
│  │ ...                                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│  已选择: 第1章 - 第3章 (约 18,000 字 / 预估 6,000 tokens)       │
│  [清除选择]                                    [确认选择 ▶]     │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.2 大纲提取工作流 (Outline Extraction Workflow)

#### 3.2.1 功能描述

从选定文本中提取情节结构，支持自动生成和人工编辑。

#### 3.2.2 工作流程

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  选择范围   │───▶│  配置参数   │───▶│  AI 分析    │───▶│  结果审核   │
│  Select     │    │  Configure  │    │  Analyze    │    │  Review     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                              │
                    ┌─────────────────────────────────────────┘
                    ▼
              ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
              │  人工修正   │───▶│  保存大纲   │───▶│  关联证据   │
              │  Refine     │    │  Save       │    │  Evidence   │
              └─────────────┘    └─────────────┘    └─────────────┘
```

#### 3.2.3 分析参数配置

```typescript
interface OutlineExtractionConfig {
  // 分析粒度
  granularity: 'act' | 'arc' | 'scene' | 'beat';
  // 大纲类型
  outline_type: 'main' | 'subplot' | 'character_arc' | 'theme';
  // 是否提取转折点
  extract_turning_points: boolean;
  // 是否关联人物
  link_characters: boolean;
  // 是否生成摘要
  generate_summary: boolean;
  // 证据提取设置
  evidence_config: {
    extract_quotes: boolean;      // 提取原文引用
    max_quote_length: number;     // 最大引用长度
    min_confidence: number;       // 最小置信度
  };
  // LLM 参数
  llm_config: {
    provider: string;
    model: string;
    temperature: number;
  };
}
```

#### 3.2.4 输出结构

```typescript
interface ExtractedOutlineNode {
  id?: number;  // 新节点无 ID
  node_type: 'act' | 'arc' | 'scene' | 'beat' | 'turning_point';
  title: string;
  summary: string;
  significance: 'critical' | 'major' | 'normal' | 'minor';
  // 位置信息
  chapter_start_id: number;
  chapter_end_id: number;
  // 关联数据
  involved_characters: number[];  // character IDs
  related_settings: number[];     // setting IDs
  // 证据
  evidence: TextEvidence[];
  // 元数据
  confidence: number;
  source: 'ai_extracted' | 'manual' | 'hybrid';
}
```

---

### 3.3 人物档案工作流 (Character Profile Workflow)

#### 3.3.1 功能描述

构建完整的人物画像，包括基本信息、属性、弧光和关系。

#### 3.3.2 人物档案结构

```
┌─────────────────────────────────────────────────────────────────┐
│                      人物档案 (Character Profile)                │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 基本信息                                                 │   │
│  │ 名称: 张三                                              │   │
│  │ 角色类型: 主角 (Protagonist)                            │   │
│  │ 首次出现: 第一章                                        │   │
│  │ 重要度评分: 9.5/10                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 别名 (Aliases)                                          │   │
│  │ • 张三爷 [称谓]                                         │   │
│  │ • 张公子 [正式名]                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 属性 (Attributes)                                       │   │
│  │ ┌──────────┬─────────┬────────────────────────────────┐ │   │
│  │ │ 类别     │ 属性    │ 值                             │ │   │
│  │ ├──────────┼─────────┼────────────────────────────────┤ │   │
│  │ │ basic    │ age     │ 25                             │ │   │
│  │ │ basic    │ gender  │ male                           │ │   │
│  │ │ appearance│ height │ 180cm                          │ │   │
│  │ │ personality│ trait │ 沉稳内敛 [置信度: 0.85]        │ │   │
│  │ │ ability  │ skill   │ 剑术 [证据: 第三章]            │ │   │
│  │ └──────────┴─────────┴────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 人物弧光 (Character Arcs)                               │   │
│  │ • 成长弧: 从懵懂少年到成熟领袖 [第1章 → 第50章]         │   │
│  │ • 救赎弧: 从复仇执念到宽恕释怀 [第30章 → 第80章]        │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 关系网络 (Relations)                                    │   │
│  │ [可视化关系图]                                          │   │
│  │ • 李四 (family/brother) [强度: 0.9]                     │   │
│  │ • 王五 (rivalry) [强度: 0.8]                            │   │
│  │ • 赵六 (romance) [强度: 0.7]                            │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.3.3 人物检测工作流

```
Phase 1: 初筛检测
  └─► 扫描文本识别人名实体
  └─► 记录出现位置和频次
  └─► 生成候选人物列表

Phase 2: 角色分类
  └─► 根据出场频次和描述判断角色重要性
  └─► protagonist / deuteragonist / supporting / minor / mentioned

Phase 3: 属性提取
  └─► 提取基本信息 (年龄、性别、外貌等)
  └─► 提取性格特征
  └─► 提取能力/技能
  └─► 提取背景信息

Phase 4: 关系分析
  └─► 识别人物间互动
  └─► 判断关系类型
  └─► 评估关系强度

Phase 5: 弧光追踪
  └─► 追踪人物变化轨迹
  └─► 识别关键转折点
  └─► 构建成长曲线
```

---

### 3.4 设定管理工作流 (Setting Management Workflow)

#### 3.4.1 功能描述

管理世界观设定元素，包括物品、地点、组织、概念等。

#### 3.4.2 设定类型体系

```typescript
type SettingType = 
  | 'item'           // 物品、道具
  | 'location'       // 地点、场景
  | 'organization'   // 组织、势力
  | 'concept'        // 概念、规则
  | 'magic_system'   // 魔法/能力体系
  | 'creature'       // 生物、种族
  | 'event_type';    // 事件类型

interface SettingHierarchy {
  // 设定层级关系
  parent_id?: number;           // 父设定
  children: number[];           // 子设定
  
  // 设定关系类型
  relations: {
    type: 'contains' | 'belongs_to' | 'produces' | 
          'requires' | 'opposes' | 'evolves_to';
    target_setting_id: number;
    description?: string;
  }[];
}
```

#### 3.4.3 设定一致性检查

```typescript
interface ConsistencyCheck {
  // 检查类型
  check_type: 'attribute_conflict' | 'location_anomaly' | 
              'timeline_error' | 'capability_break';
  
  // 问题描述
  description: string;
  
  // 涉及设定
  involved_settings: number[];
  
  // 冲突证据
  conflicting_evidence: {
    evidence_id: number;
    setting_id: number;
    attribute_value: any;
    node_id: number;  // 出处章节
  }[];
  
  // 严重程度
  severity: 'critical' | 'major' | 'minor';
  
  // 建议修复
  suggestions: string[];
}
```

---

### 3.5 文本证据管理 (Text Evidence Management)

#### 3.5.1 功能描述

为所有分析结果提供原文证据支持，支持双向追溯。

#### 3.5.2 证据类型

| 类型 | 描述 | 示例 |
|------|------|------|
| `explicit` | 明确陈述 | 直接描述人物外貌的段落 |
| `implicit` | 隐含推断 | 通过行为推断性格特征 |
| `inferred` | 推理得出 | 基于多段文本的综合判断 |

#### 3.5.3 证据数据结构

```typescript
interface TextEvidence {
  id: number;
  edition_id: number;
  node_id: number;           // 关联章节
  
  // 目标对象
  target_type: 'character' | 'character_attribute' | 'character_arc' |
               'setting' | 'setting_attribute' | 'outline_node' | 
               'outline_event' | 'relation';
  target_id: number;
  
  // 文本位置
  start_char: number;        // 起始字符位置
  end_char: number;          // 结束字符位置
  
  // 内容
  text_snippet: string;      // 引用文本
  context_before: string;    // 前文 (可选)
  context_after: string;     // 后文 (可选)
  
  // 元数据
  evidence_type: 'explicit' | 'implicit' | 'inferred';
  confidence: number;        // 置信度 0-1
  source: 'manual' | 'ai_extracted';
  
  created_at: string;
}
```

#### 3.5.4 证据标注 UI

```
┌─────────────────────────────────────────────────────────────────┐
│  章节内容 - 第三章                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ...前文内容...                                                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 张三身材高大，面容俊朗，一双剑眉下是炯炯有神的双眼。    │◄──┼── [证据标注]
│  │ 他身着青色长衫，腰间悬挂着一柄古朴的长剑。              │   │    类型: explicit
│  └─────────────────────────────────────────────────────────┘   │    目标: 张三/外貌
│                                                                 │
│  ...后文内容...                                                  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  [◀ 上一处] [下一处 ▶]                              [添加证据]  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.6 LLM Context 工程 (Context Engineering)

#### 3.6.1 功能描述

智能构建 LLM 的输入 Context，优化分析质量和 Token 使用效率。

#### 3.6.2 Context 构建策略

```typescript
interface ContextBuildStrategy {
  // 基础文本
  base_text: string;           // 选定的分析文本
  
  // 上下文增强
  enhancements: {
    // 前置知识
    known_characters?: CharacterSummary[];  // 已知人物简介
    known_settings?: SettingSummary[];      // 已知设定简介
    previous_summary?: string;              // 前文摘要
    
    // 结构化信息
    existing_outline?: OutlineNode[];       // 已有大纲节点
    related_evidence?: TextEvidence[];      // 相关证据
    
    // 任务特定
    extraction_focus?: string[];            // 提取重点
    question_prompts?: string[];            // 引导问题
  };
  
  // Token 预算分配
  token_budget: {
    system_prompt: number;
    context_info: number;
    base_text: number;
    output_reserved: number;
  };
}
```

#### 3.6.3 Context 组装流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    Context 组装流程                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 基础文本获取                                                 │
│     └─► 根据 TextRangeSelection 获取原始文本                    │
│     └─► 如超长则分块 (Chunking)                                 │
│                                                                 │
│  2. 上下文信息收集                                               │
│     └─► 查询已有人物/设定 (用于一致性)                          │
│     └─► 获取前文摘要 (用于连贯性)                               │
│     └─► 提取相关证据 (用于准确性)                               │
│                                                                 │
│  3. Token 预算计算                                               │
│     └─► 计算各组件 Token 占用                                   │
│     └─► 如超出预算则裁剪/摘要                                   │
│                                                                 │
│  4. Prompt 渲染                                                  │
│     └─► 使用模板引擎渲染最终 Prompt                             │
│     └─► 生成多格式输出 (OpenAI/Anthropic/Gemini)                │
│                                                                 │
│  5. 输出验证                                                     │
│     └─► 检查 Token 限制                                         │
│     └─► 验证必要字段完整                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.6.4 分块策略 (Chunking Strategy)

```typescript
interface ChunkingStrategy {
  // 分块方式
  method: 'by_chapter' | 'by_token_count' | 'by_paragraph' | 'semantic';
  
  // 分块参数
  max_chunk_tokens: number;     // 每块最大 Token 数
  overlap_tokens: number;       // 块间重叠 Token 数 (保持连贯性)
  
  // 边界处理
  respect_boundaries: boolean;  // 是否尊重章节边界
  min_chunk_tokens: number;     // 最小块大小 (避免碎片)
}

// 分块示例
// 原文: [Chapter1][Chapter2][Chapter3][Chapter4][Chapter5]
// 分块 (max=2章, overlap=0.5章):
//   Chunk1: [Chapter1][Chapter2][Half of Ch3]
//   Chunk2: [Half of Ch3][Chapter4][Chapter5]
```

---

## 4. 任务调度系统

### 4.1 分析任务生命周期

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ PENDING │───▶│QUEUED   │───▶│RUNNING  │───▶│COMPLETED│    │CANCELLED│
│ 待处理  │    │队列中   │    │运行中   │    │已完成   │    │已取消   │
└─────────┘    └─────────┘    └────┬────┘    └─────────┘    └─────────┘
     │                             │
     │                             ▼
     │                        ┌─────────┐
     └───────────────────────▶│ FAILED  │
                              │ 失败    │
                              └─────────┘
```

### 4.2 任务类型定义

```typescript
type AnalysisTaskType = 
  | 'outline_extraction'      // 大纲提取
  | 'character_detection'     // 人物检测
  | 'character_profiling'     // 人物画像完善
  | 'setting_extraction'      // 设定提取
  | 'relation_analysis'       // 关系分析
  | 'consistency_check'       // 一致性检查
  | 'attribute_extraction'    // 属性提取
  | 'evidence_collection'     // 证据收集
  | 'summary_generation';     // 摘要生成

interface AnalysisTask {
  id: number;
  edition_id: number;
  task_type: AnalysisTaskType;
  
  // 目标范围
  target_scope: 'full' | 'range' | 'chapter' | 'custom';
  target_node_ids: number[];
  
  // 任务配置
  parameters: {
    // 通用参数
    granularity?: string;
    extract_evidence?: boolean;
    
    // 类型特定参数
    focus_characters?: number[];    // 人物分析时关注的人物
    setting_types?: string[];       // 设定提取时关注的类型
    check_types?: string[];         // 一致性检查时检查的类型
  };
  
  // LLM 配置
  llm_model?: string;
  llm_prompt_template?: string;
  
  // 状态
  status: TaskStatus;
  priority: number;              // 优先级 0-10
  
  // 时间戳
  scheduled_at?: string;
  started_at?: string;
  completed_at?: string;
  
  // 结果摘要
  result_summary?: {
    total_results: number;
    approved_results: number;
    rejected_results: number;
    chunks_processed: number;
  };
}
```

### 4.3 执行模式

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| `llm_direct` | 直接调用 LLM API | 快速分析、小文本量 |
| `prompt_only` | 仅生成 Prompt | 外部工具处理、审核 Prompt |
| `manual` | 人工处理 | 复杂分析、需要人工判断 |
| `batch` | 批量处理 | 大规模分析、后台任务 |

---

## 5. 前端界面设计

### 5.1 分析工作台 (Analysis Hub)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  SailZen Analysis Hub                                    [用户] [设置] [帮助]   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ 导航栏                                                                   │   │
│  │ [📚 作品] [📖 当前: 《XXX》] [🔍 分析工作台] [👥 人物] [⚙️ 设定] [📊 大纲] │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌──────────────────────┐  ┌──────────────────────────────────────────────┐   │
│  │                      │  │                                              │   │
│  │  文本范围选择器      │  │           分析结果面板                       │   │
│  │  ┌────────────────┐  │  │  ┌────────────────────────────────────────┐ │   │
│  │  │ 📄 目录树      │  │  │  │ [大纲] [人物] [设定] [关系] [证据]     │ │   │
│  │  │ ▼ 第一卷       │  │  │  ├────────────────────────────────────────┤ │   │
│  │  │   ☑ 第一章     │  │  │  │                                        │ │   │
│  │  │   ☑ 第二章     │  │  │  │  [分析结果可视化展示区域]              │ │   │
│  │  │   ☐ 第三章     │  │  │  │                                        │ │   │
│  │  │ ▶ 第二卷       │  │  │  │  • 点击结果项可定位到原文              │ │   │
│  │  └────────────────┘  │  │  │  • 支持拖拽编辑                        │ │   │
│  │                      │  │  │  • 支持批量操作                        │ │   │
│  │  [全选] [清除]       │  │  │                                        │ │   │
│  │                      │  │  │                                        │ │   │
│  │  已选: 2章 (15k字)   │  │  │                                        │ │   │
│  │                      │  │  │                                        │ │   │
│  │  [▶ 开始分析]        │  │  │                                        │ │   │
│  │                      │  │  │                                        │ │   │
│  └──────────────────────┘  │  └────────────────────────────────────────┘ │   │
│                            │                                               │   │
│                            │  ┌────────────────────────────────────────┐   │   │
│                            │  │ 任务队列                               │   │   │
│                            │  │ • 任务1: 人物检测 [运行中] [取消]      │   │   │
│                            │  │ • 任务2: 大纲提取 [等待中]             │   │   │
│                            │  └────────────────────────────────────────┘   │   │
│                            └───────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 人物档案详情页

```
┌─────────────────────────────────────────────────────────────────┐
│  人物档案 - 张三                                    [编辑] [✕]  │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 头像区    张三                    [主角] [重要度: 9.5]  │   │
│  │          首次出现: 第一章                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌──────────────┬──────────────────────────────────────────┐   │
│  │              │                                          │   │
│  │  标签导航    │  [基本信息] [属性] [弧光] [关系] [证据]  │   │
│  │              │                                          │   │
│  │  [基本信息]  │  ┌────────────────────────────────────┐  │   │
│  │  [属性]      │  │ 别名                               │  │   │
│  │  [弧光]      │  │ • 张三爷 (称谓)                    │  │   │
│  │  [关系]      │  │ • 张公子 (正式名)                  │  │   │
│  │  [证据]      │  │                                    │  │   │
│  │              │  │ 描述                               │  │   │
│  │              │  │ 本章主角，性格沉稳...              │  │   │
│  │              │  │                                    │  │   │
│  │              │  │ 属性摘要                           │  │   │
│  │              │  │ 年龄: 25 | 性别: 男 | 身高: 180cm  │  │   │
│  │              │  │                                    │  │   │
│  │              │  │ [查看完整属性 ▶]                   │  │   │
│  │              │  └────────────────────────────────────┘  │   │
│  │              │                                          │   │
│  └──────────────┴──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. API 接口设计

### 6.1 文本范围相关接口

```typescript
// POST /api/v1/text/range/preview
// 预览选定范围的内容统计
interface PreviewRangeRequest {
  edition_id: number;
  selection: TextRangeSelection;
}
interface PreviewRangeResponse {
  chapter_count: number;
  total_chars: number;
  total_tokens_estimate: number;
  preview_text: string;  // 前500字预览
}

// POST /api/v1/text/range/content
// 获取选定范围的完整内容
interface GetRangeContentRequest {
  edition_id: number;
  selection: TextRangeSelection;
  include_metadata?: boolean;
}
interface GetRangeContentResponse {
  contents: {
    node_id: number;
    title: string;
    content: string;
    char_count: number;
  }[];
  total_chars: number;
}
```

### 6.2 分析任务接口

```typescript
// POST /api/v1/analysis/task
// 创建分析任务
interface CreateAnalysisTaskRequest {
  edition_id: number;
  task_type: AnalysisTaskType;
  selection: TextRangeSelection;
  parameters?: Record<string, unknown>;
  llm_config?: {
    provider?: string;
    model?: string;
    temperature?: number;
  };
}

// POST /api/v1/analysis/task-execution/{task_id}/execute
// 执行任务 (同步)
interface ExecuteTaskRequest {
  mode: 'llm_direct' | 'prompt_only';
  llm_provider?: string;
  llm_model?: string;
  api_key?: string;
}

// POST /api/v1/analysis/task-execution/{task_id}/execute-async
// 异步执行任务
// GET /api/v1/analysis/task-execution/{task_id}/progress
// 获取任务进度
// GET /api/v1/analysis/task-execution/{task_id}/status-stream
// SSE 实时状态流
```

### 6.3 证据管理接口

```typescript
// POST /api/v1/analysis/evidence
// 添加文本证据
interface AddEvidenceRequest {
  edition_id: number;
  node_id: number;
  target_type: string;
  target_id: number;
  start_char: number;
  end_char: number;
  evidence_type: 'explicit' | 'implicit' | 'inferred';
  confidence?: number;
}

// GET /api/v1/analysis/evidence/target/{target_type}/{target_id}
// 获取目标的所有证据

// GET /api/v1/analysis/evidence/chapter/{node_id}
// 获取章节的所有证据标注 (用于阅读器高亮)
```

---

## 7. 数据流设计

### 7.1 分析任务数据流

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   用户操作   │────▶│  创建任务   │────▶│  构建Context │────▶│  分块处理   │
│  (UI交互)   │     │  (API)      │     │  (Service)  │     │  (Chunking) │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
                              ┌────────────────────────────────────┘
                              ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   结果展示   │◀────│  结果审核   │◀────│  结果存储   │◀────│  LLM 调用   │
│  (UI)       │     │  (Review)   │     │  (DB)       │     │  (Provider) │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### 7.2 证据追溯数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              证据追溯数据流                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  分析结果 (AnalysisResult)                                                  │
│       │                                                                     │
│       ├──► 人物属性 (CharacterAttribute)                                    │
│       │         │                                                           │
│       │         └──► 文本证据 (TextEvidence)                                │
│       │                   │                                                 │
│       │                   └──► 文档节点 (DocumentNode) ──▶ 原文位置        │
│       │                                                                     │
│       ├──► 设定属性 (SettingAttribute)                                      │
│       │         │                                                           │
│       │         └──► 文本证据 (TextEvidence)                                │
│       │                                                                     │
│       └──► 大纲节点 (OutlineNode)                                           │
│                 │                                                           │
│                 └──► 文本证据 (TextEvidence)                                │
│                                                                             │
│  双向追溯:                                                                  │
│  • 从分析结果 → 查看原文证据                                                │
│  • 从原文 → 查看关联的所有分析结果                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. 实现路线图

### Phase 1: 基础框架 (MVP)

- [x] 文本管理基础 (作品/版本/章节)
- [x] 分析数据模型 (人物/设定/大纲/证据)
- [x] 基础 LLM 集成
- [x] 任务调度框架
- [ ] **文本范围选择器组件**
- [ ] **分析工作台页面**
- [ ] **证据标注功能**

### Phase 2: 核心工作流

- [ ] 大纲提取完整工作流
- [ ] 人物检测与档案构建
- [ ] 设定提取与管理
- [ ] 关系图谱可视化
- [ ] Context 工程优化

### Phase 3: 高级功能

- [ ] 一致性检查引擎
- [ ] 人物弧光追踪
- [ ] 多版本对比分析
- [ ] 协作分析 (多人审核)
- [ ] 创作辅助建议

### Phase 4: 生态集成

- [ ] VSCode 插件集成
- [ ] 导出功能 (Markdown/Word)
- [ ] 第三方 LLM 接入
- [ ] API 开放平台

---

## 9. 技术注意事项

### 9.1 Token 预算管理

```python
# Token 预算分配策略
TOKEN_BUDGET = {
    'gpt-4': 8192,
    'gpt-4-turbo': 128000,
    'gemini-1.5-pro': 2000000,
}

# 预留比例
RESERVE_RATIO = {
    'system_prompt': 0.05,      # 5% 系统提示词
    'output': 0.30,             # 30% 输出预留
    'context': 0.10,            # 10% 上下文信息
    'text': 0.55,               # 55% 实际文本
}
```

### 9.2 性能优化

1. **分块并行**: 多个文本块可并行处理
2. **缓存机制**: 已分析的章节结果可缓存
3. **增量更新**: 仅分析新增/修改的章节
4. **流式输出**: LLM 结果流式返回，提升用户体验

### 9.3 数据一致性

1. **事务处理**: 分析结果写入使用数据库事务
2. **版本控制**: 支持分析结果的版本历史
3. **软删除**: 使用状态标记而非物理删除

---

## 10. 附录

### 10.1 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| 作品 | Work | 一本小说或书籍 |
| 版本 | Edition | 作品的特定版本或译本 |
| 文档节点 | DocumentNode | 章节、卷等文本单元 |
| 大纲节点 | OutlineNode | 情节结构的节点 |
| 设定 | Setting | 世界观设定元素 |
| 人物弧光 | Character Arc | 人物的成长变化轨迹 |
| 文本证据 | Text Evidence | 分析结果的原文依据 |

### 10.2 相关文件

- 后端数据模型: `sail_server/data/analysis.py`
- 后端控制器: `sail_server/controller/analysis.py`, `analysis_llm.py`
- 任务调度: `sail_server/model/analysis/task_scheduler.py`
- 提示词模板: `sail_server/utils/llm/prompts.py`
- 前端数据类型: `packages/site/src/lib/data/analysis.ts`
- 前端文本页面: `packages/site/src/pages/text.tsx`

---

*文档结束*

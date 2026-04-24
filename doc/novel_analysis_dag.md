# 超长网文大纲提取 DAG 设计

> **版本**: 1.0 Draft  
> **作者**: sailing-innocent  
> **日期**: 2026-04-16  
> **状态**: 设计阶段  
> **依赖**: [novel_analysis_system.md](./design/novel_system/novel_analysis_system.md) | [novel_create_system.md](./design/novel_system/novel_create_system.md)

---

## 1. 问题定义

### 1.1 核心挑战

当前 LLM 在分析超长网文（1000+ 章节，每章 3000+ 字，总计 300万-1500万字）时面临的根本性瓶颈：

| 挑战 | 具体表现 | 根因 |
|------|----------|------|
| **上下文窗口爆炸** | 单卷 50 章 ≈ 15 万字，远超 LLM 有效处理长度 | 网文信息密度低，有效 token 占比不足 |
| **跨卷依赖断裂** | 第 50 卷揭示的"王大锤"实为第 3 卷的"小黑" | 前序分析结果无法有效传递给后序 |
| **并行与一致性的矛盾** | 全部分块并行 → 实体割裂；全部串行 → 时间不可接受 | 缺乏分层归一化机制 |
| **增量信息反写** | 后序章节的设定更新需要修正前序大纲 | DAG 通常是单向数据流，缺乏反馈环 |
| **网络/调用不稳定** | 1000+ 次 LLM 调用，任何一次失败都可能导致全局阻塞 | 缺乏细粒度断点续传 |

### 1.2 传统方案的问题

现有 `novel-analyze` Pipeline（见 [novel_analysis_system.md](./design/novel_system/novel_analysis_system.md)）采用 **"分块并行 + 单次合并"** 策略：

```
prepare → [char_detect]×N  [outline_extract]×N  [setting_extract]×N
                ↓                    ↓                   ↓
           char_merge           outline_merge        setting_merge
                \                    |                   /
                 \-------------------+------------------/
                                     ↓
                               evidence_link
```

**问题**：
1. `outline_merge` 一次性合并 140 个 chunk 结果，上下文超载
2. 没有跨 chunk 的实体传递，"小黑"和"王大锤"在合并前互不感知
3. 所有 chunk 基于同一（空）初始上下文，无法利用前面分析出的设定约束后续分析

---

## 2. 核心设计原则

### 2.1 分层递进（Hierarchical Convergence）

将全书分析建模为 **四层递进的收敛结构**：

```
Micro-Batch Layer    (章 → 微批,  ~9K-15K字,  最高并行度)
       ↓
Volume Layer         (微批 → 卷,   ~20-100章,  串行传递)
       ↓
Arc Layer            (卷 → 弧,    ~3-5卷,     弧间并行)
       ↓
Book Layer           (弧 → 全书,  所有弧,     单次汇聚)
```

**关键洞察**：信息传递遵循 **"低频高层信息向前传播，高频底层信息向后收敛"** 原则：
- **向下传播**（Book → Volume）：全局实体注册表、世界观总纲、核心设定约束
- **向上收敛**（Micro-Batch → Book）：事件流、候选实体、局部关系

### 2.2 Entity Registry 作为状态中枢

将实体归一化从"最后一步合并"改为"贯穿全程的状态传递"：

```
Entity Registry (v0: 空)
        ↓
┌─────────────────────────────────────────────┐
│ Vol-01 微批分析 (基于 Registry v0)           │
│ → 产出候选实体 + 局部归一化                  │
└─────────────────────────────────────────────┘
        ↓
Vol-01 Merge → Entity Registry (v1)
        ↓
┌─────────────────────────────────────────────┐
│ Vol-02 微批分析 (基于 Registry v1)           │
│ → "小黑" 已注册，新出现的 "王大锤"           │
│   被标记为 "疑似新实体 / 待关联"             │
└─────────────────────────────────────────────┘
        ↓
Vol-02 Merge → Entity Registry (v2)
   → 发现 Vol-02 中 "王大锤" 的描述            │
      与 Registry 中 "小黑" 高度相似           │
   → 创建关联: {entity: "小黑", alias: "王大锤"}│
        ↓
... (逐卷传递) ...
```

### 2.3 增量反写（Incremental Back-Propagation）

后序分析产生的新信息需要修正前序结果。DAG 中引入 **反写通道（Back-Write Channel）**：

- 反写不是修改已完成的节点输出（DAG 不可变原则）
- 而是生成 **Delta Patch**，在下一次 checkpoint 时合并到 Artifact
- 反写通道仅用于 **Entity Registry** 和 **Book Outline** 两个全局状态

### 2.4 完备上下文契约

每个 LLM 子任务的输入必须满足 **5C 完备性**：

| 维度 | 含义 | 示例 |
|------|------|------|
| **Content** | 待分析的原始内容 | 当前微批的 3 章原文 |
| **Context** | 前置分析结果的摘要 | 上一卷总纲 + 本卷已分析微批的摘要 |
| **Constraint** | 已知设定和规则 | Entity Registry 中的相关实体定义 |
| **Continuity** | 与前后文的衔接点 | 上一微批的结尾事件 + 下一微批的开头事件 |
| **Confidence** | 当前信息的置信度 | 哪些实体是确定的，哪些是推测的 |

---

## 3. 数据模型

### 3.1 核心数据结构

#### Entity Registry（实体注册表）

贯穿全 DAG 的**唯一可变全局状态**，每完成一卷 merge 更新一次版本。

```typescript
interface EntityRegistry {
  version: number;              // 递增版本号，每次卷合并后 +1
  last_updated_volume: string;  // 最后更新到此卷的结束位置
  entities: Record<string, CanonicalEntity>;
  alias_index: Record<string, string>;  // alias -> canonical_id 快速查找
  pending_resolutions: PendingResolution[]; // 待确认的疑似关联
}

interface CanonicalEntity {
  id: string;                   // 全局唯一，如 "ent-042"
  canonical_name: string;       // 规范名，如 "克莱恩·莫雷蒂"
  type: "character" | "item" | "location" | "organization" | "concept";
  aliases: Alias[];
  first_seen: { volume: string; chapter: number };
  last_seen: { volume: string; chapter: number };
  evolution_log: EvolutionEntry[];
  description_vector: string;   // 200字以内特征描述，用于相似度匹配
  confidence: number;           // 0.0-1.0
  status: "confirmed" | "speculative" | "merged" | "deprecated";
}

interface Alias {
  name: string;
  introduced_at: { volume: string; chapter: number };
  context: string;              // 使用该称呼时的上下文简述
  type: "nickname" | "disguise" | "true_name_revealed" | "title";
}

interface EvolutionEntry {
  at_chapter: number;
  change_type: "identity_reveal" | "power_up" | "status_change" | "death";
  from_state: string;
  to_state: string;
  evidence_quote: string;       // 原文引用，用于溯源
}

interface PendingResolution {
  id: string;
  candidate_a: string;          // entity id
  candidate_b: string;          // entity id or raw_alias
  similarity_score: number;
  reason: string;               // LLM 给出的关联理由
  suggested_action: "merge" | "link" | "reject";
  scope: "volume" | "arc" | "book";  // 在哪一层级处理此决议
}
```

#### Outline Tree（大纲树）

分层存储，每一层都有独立的树结构，上层节点指向下层根节点。

```typescript
interface OutlineNode {
  id: string;
  level: "book" | "arc" | "volume" | "chapter" | "scene";
  title: string;
  summary: string;              // 该节点的摘要
  chapter_range: [number, number]; // 覆盖的章节范围
  children: OutlineNode[];
  entities_involved: string[];  // 涉及的 entity id 列表
  key_events: Event[];
  emotional_arc: string;        // 情绪弧线简述
  cliffhanger: string | null;   // 本章/卷结尾悬念
}

interface Event {
  id: string;
  type: "plot" | "reveal" | "combat" | "dialogue" | "travel";
  description: string;
  participants: string[];       // entity ids
  location: string | null;
  timeline_position: string | null;
  source_chapters: number[];
  importance: number;           // 1-10，由 LLM 评估
}
```

#### Micro-Batch Result（微批分析结果）

```typescript
interface MicroBatchResult {
  batch_id: string;             // 如 "v03-b05"
  volume_id: string;
  chapter_range: [number, number];
  
  // 原始提取（未归一化）
  raw_events: Event[];
  raw_entities: RawEntity[];
  raw_relations: RawRelation[];
  micro_outline: OutlineNode;   // 仅包含 scene 级节点
  
  // 与全局状态的交互
  registry_snapshot_version: number; // 分析时使用的 Registry 版本
  entity_proposals: EntityProposal[]; // 向全局 Registry 提议的新增/变更
  cross_references: CrossReference[];
}

interface RawEntity {
  local_id: string;             // 微批内临时 ID
  names: string[];              // 该微批中出现的所有称呼
  descriptions: string[];       // 每次出现的描述片段
  type_guess: string;
  confidence: number;
}

interface EntityProposal {
  action: "create" | "merge" | "update_evolution" | "add_alias";
  target_entity_id?: string;    // 对于 merge/update
  raw_entity: RawEntity;        // 支撑该提议的原始实体
  reason: string;
}
```

### 3.2 Artifact 存储策略

| Artifact 类型 | 大小估计 | 存储方式 | 生命周期 |
|--------------|----------|----------|----------|
| 章节原文 | ~10KB/章 | DB (DocumentNode) | 永久 |
| Micro-Batch Result | ~50KB/批 | 文件 `artifacts/{run_id}/micro/{batch_id}.json` | Pipeline 结束后归档 |
| Volume Merge Result | ~100KB/卷 | 文件 `artifacts/{run_id}/vol/{vol_id}.json` | Pipeline 结束后归档 |
| Entity Registry (每卷版本) | ~200KB | 文件 `artifacts/{run_id}/registry/v{N}.json` | 保留最新 3 个版本 |
| Book Outline | ~50KB | DB (PipelineArtifact) + 文件 | 永久 |
| Arc Merge Result | ~80KB/弧 | 文件 `artifacts/{run_id}/arc/{arc_id}.json` | Pipeline 结束后归档 |

---

## 4. DAG 拓扑设计

### 4.1 节点总览

```
Phase 0: Preparation
  [probe] → [partition] → [init_registry]

Phase 1: Micro-Batch Extraction (最大并行层)
  [micro_extract_v01_b01]  [micro_extract_v01_b02]  ...  [micro_extract_vNN_bMM]

Phase 2: Volume Merge (串行 Registry 传递层)
  [vol_01_merge] → [vol_02_merge] → [vol_03_merge] → ... → [vol_N_merge]
       ↓                                                    ↓
  (触发 arc merge)                                    (触发 arc merge)

Phase 3: Arc Merge (弧间并行层)
  [arc_01_merge]  [arc_02_merge]  ...  [arc_K_merge]

Phase 4: Book Convergence (全局汇聚层)
  [book_merge] → [cross_reference] → [consistency_check] → [quality_report]

Phase 5: Back-Propagation (可选精修层)
  [backprop_entities] → [backprop_outline] → [finalize]
```

### 4.2 节点详细定义

#### Phase 0: Preparation

##### node: `probe`

```yaml
id: probe
name: 作品探查
type: builtin
depends_on: []
handler: novel.dag.probe
inputs:
  edition_id: int
outputs:
  total_chapters: int
  total_volumes: int
  estimated_tokens: int
  chapter_metadata: [{chapter_id, title, word_count, volume_id}]
```

##### node: `partition`

```yaml
id: partition
name: 任务分片
type: builtin
depends_on: [probe]
handler: novel.dag.partition
inputs:
  chapter_metadata: from probe
  micro_batch_size: int = 3          # 每批章节数
  max_micro_batch_tokens: int = 12000 # 微批最大 token 数
outputs:
  micro_batches:
    - batch_id: str                   # "v{vol_idx}_b{batch_idx}"
      volume_id: str
      chapter_range: [int, int]
      estimated_tokens: int
  volume_groups:                      # 哪些 batch 属于哪一卷
    - volume_id: str
      batch_ids: [str]
  arc_groups:                         # 哪些卷属于哪一弧
    - arc_id: str
      volume_ids: [str]
```

**分片策略**：
- 默认每微批 3 章，但如果单章超长（>5000字）则减为 2 章
- 保证微批总字数控制在 9000-15000 字，适配 LLM 的有效处理窗口
- 卷边界严格对齐，不允许微批跨卷

##### node: `init_registry`

```yaml
id: init_registry
name: 初始化实体注册表
type: builtin
depends_on: [probe]
handler: novel.dag.init_registry
inputs:
  edition_id: int
  known_entities: list               # 可选：预加载已知角色/设定
outputs:
  entity_registry_v0: EntityRegistry  # 版本 0，可能包含已知角色
```

**预加载场景**：如果是系列续作，可以从上一部导入已知角色和世界观。

---

#### Phase 1: Micro-Batch Extraction

每个微批一个节点，**全部并行执行**。当前设计中最大的并行层。

##### node: `micro_extract_{batch_id}`

```yaml
id: "micro_extract_{batch_id}"
name: "微批分析: {batch_id}"
type: llm
depends_on: [init_registry, partition]
handler: novel.dag.micro_extract
inputs:
  batch_id: str
  chapters_text: str                  # 本微批的原文拼接
  registry_snapshot: EntityRegistry   # 当前最新版本（分析开始时快照）
  position_context:                   # 位置信息
    is_volume_start: bool
    is_volume_end: bool
    prev_batch_summary: str | null    # 前一微批的结尾事件摘要
outputs:
  micro_result: MicroBatchResult
```

**LLM Prompt 结构（Context Builder 组装）**：

```markdown
# 任务
分析以下网文章节，提取事件流、候选实体和细纲。

# 当前分析范围
卷: {volume_title} (第 {vol_idx}/{total_vols} 卷)
章节: 第 {start_ch} ~ {end_ch} 章
位置: {is_start ? "卷首" : is_end ? "卷尾" : "卷中"}

# 已知的全局实体 (从 Entity Registry 筛选)
{registry_context}  
<!-- 只包含：
  1. 高频核心实体（主角、主要配角）
  2. 最近章节新出现/状态变更的实体
  3. 与当前卷有历史关联的实体
  4. 最多 30 个实体，按 relevance_score 排序
-->

# 前文衔接 (上一微批的结尾)
{prev_batch_summary}

# 待分析原文
{chapters_text}

# 输出格式要求
请按以下 JSON 结构输出：
{
  "events": [...],
  "entities": [...],  // 所有新发现的称呼，即使疑似已有实体的别名也要列出
  "outline": {...},
  "relations": [...],
  "cross_references": [...]
}
```

**关键设计**：
- 微批分析**不做跨批实体归一化**，只产出原始实体和提议
- `cross_references` 字段用于显式标记疑似关联，如：
  `{"type": "identity_hint", "text": "此人似乎就是第三卷出现的小黑", "confidence": 0.7}`
- 如果 registry_snapshot 为空（第一卷第一批），则只提取新实体

---

#### Phase 2: Volume Merge（核心串行层）

这是整个 DAG 的**关键路径**。每卷合并必须按顺序执行，因为 Entity Registry 需要逐卷传递。

##### node: `vol_{volume_id}_merge`

```yaml
id: "vol_{volume_id}_merge"
name: "卷级合并: {volume_title}"
type: llm
depends_on:
  # 动态依赖：该卷所有 micro_extract 节点 + 上一卷 merge 节点
  # 第一卷只依赖 micro_extract
  dynamic: "all micro_extract in volume + previous vol_merge"
handler: novel.dag.volume_merge
inputs:
  volume_id: str
  micro_results: [MicroBatchResult]   # 该卷所有微批结果
  prev_registry: EntityRegistry       # 来自上一卷的 registry（v{N-1}）
  prev_volume_summary: str | null     # 上一卷的摘要
  book_outline_snapshot: OutlineNode | null  # 当前全书总纲（增量构建）
outputs:
  registry_delta: RegistryDelta       # 本卷带来的变更
  entity_registry_vN: EntityRegistry  # 更新后的完整 Registry（版本 N）
  volume_outline: OutlineNode         # 卷级大纲（chapter 级节点）
  volume_summary: str                 # ≤500 字摘要，用于传递给下一卷
  cross_volume_hints: [CrossVolumeHint]  // 需要跨卷确认的信息
  updated_book_outline: OutlineNode   # 增量更新的全书总纲
```

**依赖关系示例**（假设每卷 3 个微批）：

```
micro_v01_b01 ──┐
micro_v01_b02 ──┼→ vol_01_merge ──┐
micro_v01_b03 ──┘                 │
                                  ├→ vol_02_merge ──┐
micro_v02_b01 ──┐                 │                 │
micro_v02_b02 ──┼→ vol_02_merge ◄┘                 │
micro_v02_b03 ──┘                                   ├→ vol_03_merge
                                                    │
micro_v03_b01 ──┐                                   │
micro_v03_b02 ──┼→ vol_03_merge ◄───────────────────┘
micro_v03_b03 ──┘
```

**注意**：虽然 `vol_02_merge` 需要 `micro_v02_*`，但 `micro_v02_*` 本身不依赖 `vol_01_merge`。它们使用的是**分析开始时的 registry 快照**。这意味着：
- **Phase 1 所有微批可以真正并行**，不受卷顺序影响
- 卷级合并在微批完成后串行执行，负责**归一化**和**Registry 更新**
- 这种设计牺牲了一小部分精度（微批看不到前一卷的归一化结果），换取了巨大的并行度提升

**Volume Merge 的 LLM Prompt**：

```markdown
# 任务
对第 {volume_id} 卷进行实体归一化、大纲整合，并更新全局实体注册表。

# 输入数据
## 本卷微批原始结果 ({batch_count} 批)
{micro_results_summary}
<!-- 每个微批的结果已压缩为：关键事件(5条) + 候选实体列表 + 细纲摘要 -->

## 上一卷传递状态
- 上一卷摘要: {prev_volume_summary}
- 当前全局实体数: {registry.entity_count}
- 最近更新实体: {recently_updated_entities}

## 当前全书总纲（截至上一卷）
{book_outline_snapshot}

# 处理要求
## 1. 卷内实体归一化
判断以下候选实体是否为同一实体的不同称呼：
{candidate_entity_clusters}

## 2. 卷内→全局实体关联
将本卷实体与全局 Registry 比对，判断：
- 新实体 → 注册
- 已有实体的新别名 → 追加 alias
- 已有实体的状态变更 → 追加 evolution_log
- 疑似跨卷关联 → 生成 cross_volume_hint

## 3. 卷级大纲生成
将微批的 scene 级大纲整合为 chapter 级大纲，确保：
- 章节间衔接流畅
- 悬念和伏笔被记录
- 与上一卷的结尾衔接自然

## 4. 全书总纲增量更新
将本卷摘要合并到现有全书总纲中，保持总纲规模可控。

# 输出格式
{
  "registry_delta": {...},
  "volume_outline": {...},
  "volume_summary": "...",
  "cross_volume_hints": [...],
  "updated_book_outline": {...}
}
```

**Entity Registry 增量更新机制**：

```python
# 伪代码：Volume Merge 中的 Registry 更新
async def volume_merge(micro_results, prev_registry, ...):
    # Step 1: 卷内聚类（本地消歧）
    local_clusters = cluster_by_similarity(
        [r.raw_entities for r in micro_results]
    )
    
    # Step 2: 与全局 Registry 匹配
    for cluster in local_clusters:
        match = find_best_match(cluster, prev_registry)
        if match.score > 0.85:
            # 确认是已有实体
            registry.merge_cluster(match.entity_id, cluster)
        elif match.score > 0.6:
            # 疑似关联，生成 pending resolution
            registry.add_pending_resolution(match.entity_id, cluster)
        else:
            # 新实体
            registry.create_entity(cluster)
    
    # Step 3: 处理 evolution（如角色能力升级、身份揭示）
    for entity in registry.get_entities_from(micro_results):
        if detect_evolution(entity, micro_results):
            registry.add_evolution_log(entity.id, ...)
    
    return registry
```

---

#### Phase 3: Arc Merge（跨卷归一化层）

当连续 N 卷（默认 5 卷）的 `volume_merge` 完成后，触发 `arc_merge`。

##### node: `arc_{arc_id}_merge`

```yaml
id: "arc_{arc_id}_merge"
name: "弧级合并: {arc_title}"
type: llm
depends_on: [vol_{v1}_merge, vol_{v2}_merge, ..., vol_{v5}_merge]
handler: novel.dag.arc_merge
inputs:
  arc_id: str
  volume_results: [VolumeMergeResult]  # 该弧所有卷的合并结果
  arc_registry_snapshot: EntityRegistry # 弧开始时的 Registry（即弧首卷前一卷的版本）
outputs:
  arc_outline: OutlineNode             # 弧级大纲（volume 级节点）
  arc_entity_resolutions: [EntityResolution]  # 弧内跨卷实体归一化决议
  arc_summary: str                     # ≤800 字
  resolved_pending: [str]              # 已解决的 pending_resolution ids
```

**Arc Merge 的核心职责**：
1. **跨卷实体归一化**：处理 `cross_volume_hints`，确认或拒绝跨卷关联
2. **角色身份揭示链**：如 "小黑 → 神秘人 → 王大锤 → 最终身份" 的完整链路
3. **弧级大纲整合**：将卷级大纲收敛为更高层的故事弧节点
4. **清理 Pending Resolutions**：将 arc 内可以确认的决议标记为 resolved

**为什么需要 Arc 层？**
- Volume 层只能看到"上一卷"的 Registry，无法判断 5 卷前的关联
- Arc 层有 3-5 卷的完整上下文，足以处理中期揭示（如第 3 卷揭示第 1 卷伏笔）
- Arc 层并行执行，不阻塞其他弧的进度

---

#### Phase 4: Book Convergence（全书汇聚层）

##### node: `book_merge`

```yaml
id: book_merge
name: 全书总纲合并
type: llm
depends_on: [all arc_merge nodes]
handler: novel.dag.book_merge
inputs:
  arc_results: [ArcMergeResult]
  final_registry: EntityRegistry       # 最后一卷的 Registry
outputs:
  book_outline: OutlineNode            # 全书总纲树（arc → volume → chapter）
  book_timeline: Timeline
  book_worldview: WorldViewSummary
```

##### node: `cross_reference`

```yaml
id: cross_reference
name: 交叉引用建立
type: builtin
depends_on: [book_merge]
handler: novel.dag.cross_reference
inputs:
  book_outline: from book_merge
  final_registry: EntityRegistry
  all_micro_results: [MicroBatchResult]  # 从 artifacts 加载
outputs:
  evidence_links: [EvidenceLink]          # 关联分析结果到原文证据
```

##### node: `consistency_check`

```yaml
id: consistency_check
name: 一致性检查
type: llm
depends_on: [cross_reference]
handler: novel.dag.consistency_check
inputs:
  book_outline: from book_merge
  final_registry: EntityRegistry
  evidence_links: from cross_reference
outputs:
  consistency_report: ConsistencyReport
  issues: [ConsistencyIssue]
```

---

#### Phase 5: Back-Propagation（可选精修层）

如果 consistency_check 发现早期章节的分析有遗漏（如"第 1 卷的小黑应该被标记为未揭示身份的王大锤"），启动反写层。

##### node: `backprop_entities`

```yaml
id: backprop_entities
name: 实体信息反写
type: llm_batch
depends_on: [consistency_check]
handler: novel.dag.backprop_entities
inputs:
  consistency_issues: [ConsistencyIssue]
  affected_volumes: [str]              # 哪些卷需要反写
  original_micro_results: [MicroBatchResult]  # 原始微批结果
outputs:
  entity_patches: [EntityPatch]        # 对早期 Registry 版本的修正
```

**反写策略**：
- 不修改已完成的节点输出（保持 DAG 不可变性）
- 生成 `patch` 文件，由 `finalize` 节点合并到最终 Artifact
- 只处理高置信度问题（confidence > 0.8），低置信度问题标记为人工审核

##### node: `finalize`

```yaml
id: finalize
name: 结果定稿
type: builtin
depends_on: [backprop_entities, consistency_check]
handler: novel.dag.finalize
inputs:
  book_outline: from book_merge
  final_registry: from last volume_merge
  entity_patches: from backprop_entities
  consistency_report: from consistency_check
outputs:
  final_outline: OutlineNode           # 合并 patch 后的最终大纲
  final_registry: EntityRegistry       # 合并 patch 后的最终 Registry
  analysis_report: AnalysisReport
```

---

### 4.3 完整依赖图示例

以 **30 卷，每卷 40 章，共 1200 章** 的典型超长网文为例：

```
                                        ┌─────────────────────────────────────┐
                                        │          Phase 0: Prep              │
                                        │  [probe]→[partition]→[init_reg]    │
                                        └─────────────────┬───────────────────┘
                                                          │
                    ┌─────────────────────────────────────┼─────────────────────────────────────┐
                    │           Phase 1: Micro-Batch (360 批, 全部并行)                      │
                    │                                                                      │
                    │  [m_v01_b01] [m_v01_b02] ... [m_v01_b14]                             │
                    │  [m_v02_b01] [m_v02_b02] ... [m_v02_b14]                             │
                    │  ...                                                                 │
                    │  [m_v30_b01] [m_v30_b02] ... [m_v30_b14]                             │
                    └─────────────────────────────────────┬─────────────────────────────────────┘
                                                          │
                    ┌─────────────────────────────────────┼─────────────────────────────────────┐
                    │         Phase 2: Volume Merge (串行 Registry 传递)                    │
                    │                                                                      │
                    │  vol_01_merge ──→ vol_02_merge ──→ ... ──→ vol_30_merge              │
                    │       │                │                      │                      │
                    │       ↓                ↓                      ↓                      │
                    │   (触发弧合并)     (触发弧合并)           (触发弧合并)                 │
                    └─────────────────────────────────────┬─────────────────────────────────────┘
                                                          │
                    ┌─────────────────────────────────────┼─────────────────────────────────────┐
                    │         Phase 3: Arc Merge (6 弧, 弧间并行)                          │
                    │                                                                      │
                    │  arc_01(v01-05)  arc_02(v06-10)  ...  arc_06(v26-30)                 │
                    │       │                │                      │                      │
                    └───────────────────────┼───────────────────────────────────────────────┘
                                            │
                                            ↓
                    ┌─────────────────────────────────────────────┐
                    │     Phase 4: Book Convergence               │
                    │  [book_merge]→[cross_ref]→[consistency]    │
                    │                    │                        │
                    │                    ↓                        │
                    │     Phase 5: Back-Propagation (可选)       │
                    │  [backprop_entities]→[finalize]            │
                    └─────────────────────────────────────────────┘
```

**并发度分析**：

| 阶段 | 节点数 | 并行度 | 预估耗时 |
|------|--------|--------|----------|
| Phase 1 | 360 | 360（受并发限制，实际 5-10） | ~30 分钟（5 并发，每批 30 秒） |
| Phase 2 | 30 | 1（严格串行） | ~15 分钟（30 卷 × 30 秒） |
| Phase 3 | 6 | 6 | ~2 分钟 |
| Phase 4 | 3 | 1（ book_merge 串行） | ~2 分钟 |
| Phase 5 | 2 | 1-5 | ~5 分钟 |
| **总计** | | | **~1 小时** |

相比传统串行方案（1200 章 × 30 秒 = 10 小时）或简单并行方案（缺乏归一化），该 DAG 结构在 **1 小时** 内完成全书分析，同时保证跨卷一致性。

---

## 5. 上下文管理（Context Builder）

### 5.1 核心问题

每个 LLM 节点的输入上下文必须控制在有效窗口内（即使模型支持 200K token，有效处理长度通常只有 32K-64K）。Context Builder 负责**动态裁剪和优先级排序**。

### 5.2 Context Builder 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Context Builder                          │
│                                                             │
│  Input: 节点类型 + 可用素材 + 窗口限制                       │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ 优先级排序   │  │ 摘要生成     │  │ 相关度过滤           │ │
│  │ (Priority   │  │ (Summarizer)│  │ (Relevance Filter)  │ │
│  │  Queue)     │  │             │  │                     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                     │            │
│         └────────────────┼─────────────────────┘            │
│                          ▼                                  │
│                  ┌───────────────┐                          │
│                  │  窗口填充引擎  │                          │
│                  │ (Token Budget)│                          │
│                  └───────┬───────┘                          │
│                          ▼                                  │
│                   输出: 裁剪后的上下文                       │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 各节点上下文规则

#### Micro-Extract 上下文优先级

```
Token Budget: 32K (留 4K 给输出)

Priority 1: 原文 (必须保留)
  - 本微批的 3 章原文
  - 估计 9K-15K 字 ≈ 12K-20K tokens
  - 如果超长，压缩对话和场景描写

Priority 2: Entity Registry 摘要 (必须保留)
  - 核心实体（主角团）: 完整信息
  - 相关实体（与当前卷有历史关联）: 精简信息
  - 其他实体: 只留名称和 ID
  - 预算: 4K tokens

Priority 3: 前文衔接 (尽量保留)
  - 上一微批的结尾 500 字摘要
  - 预算: 1K tokens

Priority 4: 全局设定约束 (尽量保留)
  - 世界观硬性规则
  - 预算: 1K tokens

Fallback: 如果原文超长，将单章压缩为 1000 字摘要
```

#### Volume-Merge 上下文优先级

```
Token Budget: 32K

Priority 1: 本卷微批结果摘要
  - 每个微批产出的事件流（压缩为 5 条/批）
  - 候选实体聚类列表
  - 预算: 10K tokens

Priority 2: 前一卷摘要 + 当前全书总纲
  - 前一卷 volume_summary: 500 字
  - 当前 book_outline: 压缩为 arc 级节点 + 最近 2 卷 volume 级节点
  - 预算: 6K tokens

Priority 3: Entity Registry
  - 所有 "speculative" 和 "pending" 实体: 完整信息
  - 本卷涉及的核心实体: 完整信息
  - 其他实体: 列表形式（名称 + ID + 描述向量）
  - 预算: 10K tokens

Priority 4: 跨卷提示
  - 来自微批的 cross_volume_hints
  - 预算: 2K tokens
```

#### Arc-Merge 上下文优先级

```
Token Budget: 32K

Priority 1: 弧内卷摘要
  - 5 个 volume_summary，各 500 字
  - 预算: 3K tokens

Priority 2: 弧内 Registry 变化
  - 该弧范围内所有实体的 evolution_log
  - 所有 pending_resolutions（scope=arc 或 scope=book）
  - 预算: 12K tokens

Priority 3: 弧内大纲
  - 5 个 volume_outline 的 chapter 级摘要
  - 预算: 8K tokens

Priority 4: 跨弧关联
  - 前一弧的 arc_summary
  - 预算: 1K tokens
```

### 5.4 摘要生成策略

对于超长的输入素材，Context Builder 内置多级摘要：

```python
async def summarize_for_context(text: str, target_tokens: int) -> str:
    """
    多级摘要：先提取关键句，再 LLM 压缩
    """
    # Level 1: 基于规则提取（低成本）
    key_sentences = extract_key_sentences(text, top_k=20)
    
    # Level 2: 如果仍超长，用 LLM 压缩
    if estimate_tokens(key_sentences) > target_tokens:
        return await llm_summarize(key_sentences, target_tokens)
    
    return "\n".join(key_sentences)

async def extract_key_sentences(text: str, top_k: int) -> list[str]:
    """
    基于以下信号提取关键句：
    - 包含实体名称的句子
    - 对话引语（揭示关系/设定）
    - 动作描述（推动情节）
    - 场景转换句
    """
    sentences = segment_sentences(text)
    scored = [(s, score_sentence(s)) for s in sentences]
    scored.sort(key=lambda x: x[1], reverse=True)
    # 按原文顺序返回 top_k
    selected = scored[:top_k]
    selected.sort(key=lambda x: x[0].position)
    return [s.text for s, _ in selected]
```

---

## 6. 实体归一化策略（三层消歧）

### 6.1 第一层：微批内聚类（Intra-Batch Clustering）

在单个微批的原文中，通过**规则 + 轻量 LLM** 识别同一实体的不同称呼。

**规则信号**：
- 代词指代消解："他"/"她" 向前匹配最近的名词
- 同一自然段内的同位语："王大锤，也就是小黑"
- 引号内的称呼交替

**LLM 辅助**：
- 对于复杂指代（如 "那道灰雾中的身影"），用 LLM 判断指代对象

### 6.2 第二层：卷内归一化（Intra-Volume Resolution）

在 Volume Merge 节点中，将微批聚类结果与全局 Registry 比对。

**匹配算法**：

```python
async def resolve_volume_entities(
    local_clusters: list[EntityCluster],
    global_registry: EntityRegistry,
) -> list[EntityResolution]:
    resolutions = []
    
    for cluster in local_clusters:
        # 步骤 1: 名称精确匹配
        exact_match = registry.alias_index.get(cluster.primary_name)
        if exact_match:
            resolutions.append(Resolution(action="merge", target=exact_match))
            continue
        
        # 步骤 2: 描述向量语义匹配
        candidates = []
        for entity in registry.entities.values():
            score = semantic_similarity(
                cluster.description_vector,
                entity.description_vector
            )
            if score > 0.5:
                candidates.append((entity, score))
        
        # 步骤 3: LLM 消歧（仅对 Top-3 候选）
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            top3 = candidates[:3]
            
            llm_verdict = await llm_disambiguate(cluster, top3)
            # LLM 判断：是同一实体 / 可能是 / 不是
            
            if llm_verdict.is_same:
                resolutions.append(Resolution(
                    action="merge", 
                    target=llm_verdict.best_match.id,
                    confidence=llm_verdict.confidence
                ))
            elif llm_verdict.confidence > 0.6:
                resolutions.append(Resolution(
                    action="pending",
                    candidates=[c.id for c, _ in top3],
                    confidence=llm_verdict.confidence
                ))
            else:
                resolutions.append(Resolution(action="create"))
        else:
            resolutions.append(Resolution(action="create"))
    
    return resolutions
```

### 6.3 第三层：跨卷/跨弧归一化（Cross-Volume Resolution）

处理**身份揭示链**和**长期伏笔**。

**典型场景**：

```
Vol-03: "小黑" 出现，身份不明
  → Volume Merge: 注册为 speculative 实体

Vol-08: "神秘人" 出现，特征与 "小黑" 相似
  → Volume Merge: 生成 cross_volume_hint {"小黑", "神秘人", score: 0.72}
  → 标记为 pending，scope: arc

Vol-12 (Arc-03 Merge): 
  分析 Vol-10~12 发现 "神秘人" 真名 "王大锤"
  回溯 Vol-03 的 "小黑" 描述，高度相似
  → Arc Merge: 确认 "小黑 = 神秘人 = 王大锤"
  → 合并实体，更新 evolution_log
  → 生成 backprop 提示：Vol-03 的 "小黑" 应关联到 "王大锤"
```

**跨卷匹配的信号**：
1. **描述重叠**：外貌、能力、行为模式的关键词重叠度
2. **叙事位置**：同一角色通常在叙事结构中承担相似功能
3. **关系网络**：社交圈的重叠（如都跟同一组织有关）
4. **作者线索**：特征性描述词（如"总戴着那枚铜戒指"）

**LLM 消歧 Prompt（Arc Merge 中使用）**：

```markdown
请判断以下两组实体描述是否指向同一角色。

实体 A（来自第 3 卷）:
- 名称: 小黑
- 描述: 身材瘦小的少年，沉默寡言，跟在主角身边
- 首次出现: 第 87 章
- 关键事件: 在古墓中救下主角

实体 B（来自第 12 卷）:
- 名称: 王大锤
- 描述: 身材瘦小的青年，眼神深邃，真实身份是前朝皇子
- 首次出现: 第 356 章（以"神秘人"身份）
- 关键事件: 在皇城决战中暴露身份

跨卷关联提示:
- 第 8 卷的"神秘人"与小黑的描述相似度 0.72
- 两人都在追查"血玉"的下落
- 都有"左肩有旧伤"的细节

请回答:
1. 是否为同一人物？（是/否/不确定）
2. 如果是，身份揭示链是什么？（如：小黑→神秘人→王大锤）
3. 置信度（0-1）
4. 关键证据
```

---

## 7. 失败恢复与断点续传

### 7.1 Checkpoint 策略

```python
class DAGCheckpointManager:
    """
    在关键路径节点后自动保存 checkpoint
    """
    
    CHECKPOINT_INTERVALS = {
        "after_volume_merge": True,    # 每卷合并后必存
        "after_arc_merge": True,       # 每弧合并后必存
        "after_phase": True,           # 每阶段结束后必存
    }
    
    async def checkpoint(self, run_id: int, after_node: str, context: PipelineContext):
        """保存当前完整状态"""
        checkpoint = {
            "run_id": run_id,
            "completed_nodes": self._get_completed_nodes(run_id),
            "node_outputs": self._serialize_outputs(context),
            "entity_registry": context.artifacts.get("latest_registry"),
            "book_outline": context.artifacts.get("latest_outline"),
            "timestamp": datetime.utcnow().isoformat(),
        }
        path = f"data/checkpoints/novel_dag/{run_id}/{after_node}.json"
        await self._atomic_write(path, checkpoint)
```

### 7.2 失败场景与恢复

| 失败场景 | 影响范围 | 恢复策略 |
|----------|----------|----------|
| 单个 micro_extract 失败 | 仅该批 | 重试该批（最多 3 次），仍失败则标记为 `degraded` 继续 |
| Volume Merge 失败 | 该卷及之后所有卷 | 从该卷 checkpoint 恢复，重试 merge |
| Arc Merge 失败 | 仅该弧 | 重试该弧 merge，不影响其他弧 |
| Book Merge 失败 | 最终汇聚 | 重试 book_merge |
| 网络中断/服务重启 | 全局 | 从最后一个 volume checkpoint 恢复，已完成节点跳过 |

### 7.3 Degraded 模式

当某个 micro_extract 最终失败时，启用降级模式：

```python
async def degraded_micro_extract_fallback(batch_id, chapters_text):
    """
    降级策略：用轻量级规则提取替代 LLM 分析
    """
    return MicroBatchResult(
        events=rule_based_event_extraction(chapters_text),
        raw_entities=rule_based_entity_extraction(chapters_text),
        micro_outline=simple_outline_from_chapter_titles(chapters_text),
        is_degraded=True,
        degradation_reason="llm_max_retries_exceeded"
    )
```

降级批次的结果会在 Volume Merge 时特别标注，LLM 会被告知这部分数据置信度较低。

---

## 8. 执行示例：1000 章小说完整流程

### 8.1 输入

- **作品**：《诡秘之主》风格长篇小说
- **规模**：50 卷 × 20 章 = 1000 章，每章 3500 字，总计 350 万字
- **分片**：每微批 3 章，共 334 批；每弧 5 卷，共 10 弧

### 8.2 执行时序

```
T+0:00   [probe] 完成：1000 章，50 卷，350万字
T+0:01   [partition] 完成：334 微批，50 卷，10 弧
T+0:02   [init_registry] 完成：加载预置主角信息

T+0:02 ──T+0:35   Phase 1: Micro-Extract (334 批并行)
  - 并发度: 8
  - 每批平均耗时: 25 秒
  - 334/8 ≈ 42 轮调度
  - 实际耗时: ~35 分钟
  - 2 批降级（网络超时）

T+0:35 ──T+0:50   Phase 2: Volume Merge (50 卷串行)
  - 每卷平均耗时: 18 秒
  - 实际耗时: ~15 分钟
  - 第 7 卷 merge 失败 1 次，自动重试成功

T+0:50 ──T+0:53   Phase 3: Arc Merge (10 弧并行)
  - 每弧平均耗时: 20 秒
  - 并发度: 10
  - 实际耗时: ~3 分钟

T+0:53 ──T+0:56   Phase 4: Book Merge + Cross-Reference
  - book_merge: 25 秒
  - cross_reference: 10 秒
  - consistency_check: 15 秒

T+0:56 ──T+1:02   Phase 5: Back-Propagation (发现 3 处需反写)
  - 3 个早期卷需要 entity patch
  - backprop_entities: 4 分钟
  - finalize: 1 分钟

T+1:02   [finalize] 完成

总耗时: ~62 分钟
```

### 8.3 产出物

```yaml
final_outline:
  title: "诡秘之主"
  total_chapters: 1000
  total_volumes: 50
  arcs:
    - id: arc-01
      title: "廷根篇"
      volumes: [1-5]
      summary: "主角穿越后成为值夜者，逐渐发现世界真相..."
    - id: arc-02
      title: "贝克兰德篇"
      ...
  
  # 全书级节点
  key_events:
    - {chapter: 1, event: "主角穿越", importance: 10}
    - {chapter: 150, event: "发现灰雾真相", importance: 10}
    ...

final_registry:
  total_entities: 342
  characters:
    - id: ent-001
      canonical_name: "克莱恩·莫雷蒂"
      aliases: ["周明瑞", "愚者", "夏洛克·莫里亚蒂", "格尔曼·斯帕罗"]
      first_seen: {volume: 1, chapter: 1}
      evolution_log:
        - {at: 1, from: "普通人", to: "序列9·占卜家"}
        - {at: 150, from: "序列9", to: "序列8·小丑"}
        ...

analysis_report:
  coverage: 99.4%  # 998/1000 章成功分析
  degraded_batches: 2
  entity_confidence_distribution:
    confirmed: 287
    speculative: 45
    pending: 10
  cross_volume_resolutions: 34  # 成功识别的跨卷身份关联
  backprop_patches_applied: 3
  consistency_issues: 12  # 低优先级，建议人工复核
```

---

## 9. 与现有系统对接

### 9.1 复用组件

| 本设计组件 | 复用现有系统 | 扩展点 |
|-----------|-------------|--------|
| DAG 执行引擎 | `service/dag_executor.py` | 支持动态依赖生成（`dynamic_spawn`） |
| Pipeline 定义加载 | `service/dag_pipeline_loader.py` | 新增节点类型：`map_reduce`, `backprop` |
| LLM 批量调度 | `LLMBatchScheduler` | 增加 per-node semaphore 配置 |
| Artifact 存储 | `PipelineArtifact` ORM | 增加分层目录结构 |
| Checkpoint | `CheckpointManager` | 增加 Entity Registry 专用序列化 |
| 前端 DAG 画布 | `DAGCanvas` (site) | 增加分层折叠视图（Phase 可折叠） |
| SSE 实时推送 | `UnifiedAgent` WebSocket | 复用现有机制 |

### 9.2 新增组件

```
sail_server/
├── service/novel/
│   ├── dag/
│   │   ├── __init__.py
│   │   ├── context_builder.py      # 上下文组装引擎
│   │   ├── entity_registry.py      # 实体注册表管理
│   │   ├── partitioner.py          # 任务分片策略
│   │   ├── summarizer.py           # 多级摘要生成
│   │   └── backprop.py             # 反写通道
│   └── handlers/
│       ├── micro_extract.py        # 微批分析 handler
│       ├── volume_merge.py         # 卷合并 handler
│       ├── arc_merge.py            # 弧合并 handler
│       ├── book_merge.py           # 全书合并 handler
│       └── consistency_check.py    # 一致性检查 handler
├── infrastructure/orm/
│   └── entity_registry.py          # Entity Registry ORM (如果需要持久化中间版本)
└── data/pipelines/
    └── novel-long-outline.json     # 本 DAG 的 Pipeline 定义
```

### 9.3 Pipeline JSON 定义片段

```json
{
  "id": "novel-long-outline",
  "name": "超长网文大纲提取 DAG",
  "description": "分层递进式超长网文分析 Pipeline",
  "params_schema": {
    "edition_id": { "type": "integer", "required": true },
    "micro_batch_size": { "type": "integer", "default": 3 },
    "arc_volume_count": { "type": "integer", "default": 5 },
    "max_concurrency": { "type": "integer", "default": 8 },
    "enable_backprop": { "type": "boolean", "default": true }
  },
  "nodes": [
    {
      "id": "probe",
      "type": "builtin",
      "handler": "novel.dag.probe",
      "depends_on": []
    },
    {
      "id": "partition",
      "type": "builtin",
      "handler": "novel.dag.partition",
      "depends_on": ["probe"]
    },
    {
      "id": "init_registry",
      "type": "builtin",
      "handler": "novel.dag.init_registry",
      "depends_on": ["probe"]
    },
    {
      "id": "micro_extract",
      "type": "dynamic_map",
      "handler": "novel.dag.micro_extract",
      "depends_on": ["partition", "init_registry"],
      "dynamic_config": {
        "spawn_from": "partition.micro_batches",
        "max_concurrency": 8,
        "retry_count": 3,
        "degraded_fallback": true
      }
    },
    {
      "id": "volume_merge",
      "type": "dynamic_reduce",
      "handler": "novel.dag.volume_merge",
      "depends_on": ["micro_extract"],
      "dynamic_config": {
        "reduce_from": "micro_extract",
        "group_by": "volume_id",
        "sequential": true,
        "state_passing": "entity_registry"
      }
    },
    {
      "id": "arc_merge",
      "type": "dynamic_map",
      "handler": "novel.dag.arc_merge",
      "depends_on": ["volume_merge"],
      "dynamic_config": {
        "spawn_from": "partition.arc_groups",
        "max_concurrency": 10
      }
    },
    {
      "id": "book_merge",
      "type": "llm",
      "handler": "novel.dag.book_merge",
      "depends_on": ["arc_merge"]
    },
    {
      "id": "cross_reference",
      "type": "builtin",
      "handler": "novel.dag.cross_reference",
      "depends_on": ["book_merge"]
    },
    {
      "id": "consistency_check",
      "type": "llm",
      "handler": "novel.dag.consistency_check",
      "depends_on": ["cross_reference"]
    },
    {
      "id": "backprop_entities",
      "type": "llm_batch",
      "handler": "novel.dag.backprop_entities",
      "depends_on": ["consistency_check"],
      "condition": "params.enable_backprop and consistency_check.has_issues",
      "batch_config": {
        "source": "consistency_check.affected_batches",
        "max_concurrency": 5
      }
    },
    {
      "id": "finalize",
      "type": "builtin",
      "handler": "novel.dag.finalize",
      "depends_on": ["consistency_check", "backprop_entities"]
    }
  ]
}
```

---

## 10. 性能与成本估算

### 10.1 LLM 调用次数

以 1000 章 / 50 卷 / 334 微批 / 10 弧为例：

| 阶段 | 调用次数 | 平均输入 tokens | 平均输出 tokens |
|------|----------|----------------|----------------|
| Micro-Extract | 334 | 15K | 3K |
| Volume Merge | 50 | 20K | 5K |
| Arc Merge | 10 | 25K | 6K |
| Book Merge | 1 | 30K | 8K |
| Consistency Check | 1 | 25K | 4K |
| Back-Propagation | ~10 | 15K | 2K |
| **总计** | **~406 次** | | |

### 10.2 成本估算（以 moonshot kimi-k2.5 为例）

- Input: ~406 × 18K avg × ¥0.00001/token ≈ ¥73
- Output: ~406 × 3.5K avg × ¥0.00002/token ≈ ¥28
- **总计: ~¥101 / 部**（1000 章小说）

对比：
- 串行逐章分析（1000 次调用）：~¥250，耗时 8-10 小时
- 简单并行（无归一化）：~¥100，但跨卷一致性差
- **本方案：~¥100，1 小时，高一致性**

### 10.3 时间优化空间

| 优化策略 | 预期提升 |
|----------|----------|
| 提升并发度到 16 | Phase 1 从 35min → 20min |
| 使用更快的模型做 Micro-Extract | Phase 1 从 35min → 20min |
| 跳过 Arc Merge（小作品） | 省 3 分钟 |
| 关闭 Back-Propagation | 省 6 分钟 |
| **理论最优** | **~30 分钟** |

---

## 11. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM 幻觉导致错误归一化 | 中 | Volume Merge 只处理高置信度匹配，低置信度标记 pending 到 Arc/Book 层 |
| Registry 过大导致上下文溢出 | 中 | Registry 摘要时按相关度过滤，无关实体只保留 ID+名称 |
| 卷级串行成为瓶颈 | 低 | 每卷 merge 仅 18 秒，50 卷 15 分钟可接受；未来可探索并行 merge + 最终统一 |
| 反写层循环依赖 | 低 | 反写只生成 patch，不触发重新执行；patch 合并是确定性的 |
| 超长单章超出微批预算 | 低 | Partition 节点检测单章长度，动态调整 batch_size（2 章甚至 1 章） |
| 跨弧关联（Vol-01 和 Vol-50） | 低 | Book Merge 有全书视野；极端情况可人工介入标注 |

---

## 12. 附录

### 12.1 术语表

| 术语 | 含义 |
|------|------|
| Micro-Batch | 3-5 章组成的分析单元，Phase 1 的并行粒度 |
| Volume | 网文自然分卷，通常 20-100 章 |
| Arc | 3-5 卷组成的更高层故事弧 |
| Entity Registry | 全局实体注册表，存储所有规范化后的实体信息 |
| Back-Propagation | 后序分析结果修正前序产出的机制 |
| Context Builder | 动态组装 LLM 输入上下文的组件 |
| Cross-Volume Hint | 微批/卷级分析时标记的跨卷疑似关联 |
| Pending Resolution | 置信度不足的实体关联，延后到更高层级处理 |

### 12.2 待决策事项

- [ ] Arc 层是否必须？对于 <20 卷的作品是否可以跳过？
- [ ] Entity Registry 的向量相似度是否引入 embedding 模型（成本 vs 精度）？
- [ ] 是否支持增量分析（只分析新增章节，复用已有结果）？
- [ ] Human-in-the-Loop 介入点：在哪个节点后最适合人工审核 cross_volume_hints？

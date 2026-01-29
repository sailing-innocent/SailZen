# 文本内容管理器

文本不同于笔记，不需要频繁的修改，但是需要被频繁且灵活地引用，SailZen作为一个LLM辅助的内容管理器，后台需要非常庞大灵活的内容管理设计

- 数据来源：`data/books/webnovel` 目录下的中文与英文长篇小说原始文本。
- 目标：构建一个可统一存储、索引、溯源与勘误的文本知识底座，支撑后续的 LLM 抽取、推理与世界观构造。
- 范围：定义 PostgreSQL 表结构、关键约束、元数据与流程建议；暂不涉及具体实现代码。

## 1. 设计原则

- **多层级适配**：原始文本可能包含"卷/部/章/节/段/句"等任意组合，采用树形节点描述结构，避免强制固定两级。
- **强溯源**：所有实体、事件、关系、事实都必须能回溯到具体文本区间（段落/句子/字符范围）。
- **逐步演化**：允许多版本导入、LLM 反复抽取、人工校对与回滚；保留历史轨迹。
- **语义解耦**：实体、关系、事件等知识层与文本层分离。知识层只通过 span 绑定文本证据。
- **扩展与互操作**：尽量使用规范化结构（桥接表、枚举、JSONB 拓展字段），方便未来接入向量检索、知识图谱等模块。
- **数据作业透明化**：导入、抽取、校对都以"批次"形式登记，便于重跑、审核和追责。
- **世界观共享**：多个作品可能共用同一宇宙观或设定，需支持跨作品的实体合并与统计。

```
universe ──< work ──< edition ──< document_node ──< text_span
    │           │                      │                 │
    │           │                      │                 └─< annotation_item
    │           │                      │                         │
    │           │                      │                         ├─< entity_mention ──> entity ──< entity_alias
    │           │                      │                         └─< fact_record / narrative_event
    │           │
    │           └─< change_set ──< change_item
    │
    └─< universe_entity_link (可选跨作品实体对齐)
```


### 2.2 关键实体清单

- **作品维度**：`works`（作品）、`editions`（版本/译本）、`edition_files`（原始文件）、`edition_tags`。
- **文本结构**：`document_nodes`（树形节点）、`node_text_stats`、`text_spans`（字符区间）。
- **处理批次**：`ingest_jobs`、`processing_tasks`、`annotation_batches`、`annotation_items`。
- **知识层**：`entities`、`entity_aliases`、`entity_attributes`、`entity_mentions`、`entity_relations`、`relation_evidence`、`narrative_events`、`event_participants`、`fact_records`。
- **勘误与版本**：`edition_versions`、`change_sets`、`change_items`、`review_tasks`。

## 3. 表设计详情

> 所有 `UUID` 默认使用 `gen_random_uuid()`；需启用扩展 `CREATE EXTENSION IF NOT EXISTS pgcrypto;`。


### 3.1 世界观、作品与版本

```sql
CREATE TABLE universes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE universe_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    universe_id UUID NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,          -- entity | event | location
    target_id UUID NOT NULL,
    linkage_type TEXT DEFAULT 'canonical',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(universe_id, target_type, target_id)
);

CREATE TABLE works (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    original_title TEXT,
    author TEXT,
    language_primary TEXT NOT NULL,
    work_type TEXT DEFAULT 'web_novel',
    status TEXT DEFAULT 'ongoing', -- ongoing | completed | hiatus
    synopsis TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE universe_memberships (
    universe_id UUID NOT NULL REFERENCES universes(id) ON DELETE CASCADE,
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    membership_role TEXT DEFAULT 'primary', -- primary | side_story | cameo
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (universe_id, work_id)
);

CREATE TABLE work_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    language TEXT,
    alias_type TEXT DEFAULT 'title', -- title | tag | abbreviation
    is_primary BOOLEAN DEFAULT FALSE,
    UNIQUE(work_id, alias)
);

CREATE TABLE editions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    edition_name TEXT,
    language TEXT NOT NULL,
    source_format TEXT DEFAULT 'txt',
    canonical BOOLEAN DEFAULT FALSE,
    source_path TEXT,             -- 相对路径或原始 URL
    source_checksum TEXT,         -- SHA256 等
    ingest_version INTEGER DEFAULT 1,
    publication_year INTEGER,
    word_count INTEGER,
    description TEXT,
    status TEXT DEFAULT 'draft',  -- draft | active | archived
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(work_id, language, ingest_version)
);

CREATE TABLE edition_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    file_role TEXT DEFAULT 'source', -- source | cleaned | tokenized
    storage_uri TEXT NOT NULL,
    checksum TEXT,
    byte_length BIGINT,
    encoding TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE edition_tags (
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (edition_id, tag)
);
```

### 3.2 文本结构（树形节点 + 统计）

```sql
CREATE TABLE document_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES document_nodes(id) ON DELETE CASCADE,
    node_type TEXT NOT NULL,
        -- 枚举建议：volume/part/chapter/section/paragraph/sentence/title/extra
    sort_index INTEGER NOT NULL,
    depth SMALLINT NOT NULL,
    label TEXT,                   -- "第一章"等显示标签
    title TEXT,
    raw_text TEXT,                -- 仅在文本节点填充
    text_checksum TEXT,
    word_count INTEGER,
    char_count INTEGER,
    start_char INTEGER,           -- 在父节点中的起始偏移
    end_char INTEGER,
    path TEXT NOT NULL,           -- materialized path，如 `0001.0003`
    status TEXT DEFAULT 'active', -- active | deprecated | superseded
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (edition_id, path)
);

CREATE INDEX idx_document_nodes_parent ON document_nodes(parent_id, sort_index);
CREATE INDEX idx_document_nodes_type ON document_nodes(edition_id, node_type);

CREATE TABLE node_text_stats (
    node_id UUID PRIMARY KEY REFERENCES document_nodes(id) ON DELETE CASCADE,
    sentence_count INTEGER,
    paragraph_index INTEGER,
    embedding_vector VECTOR(1536), -- 可选：pgvector 扩展
    meta_data JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE text_spans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES document_nodes(id) ON DELETE CASCADE,
    span_type TEXT DEFAULT 'explicit', -- explicit | inferred | auto_sentence
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    text_snippet TEXT,
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(node_id, start_char, end_char)
);
```

> 说明：通过 `document_nodes` + `text_spans`，可以灵活表示大纲、段落、句子或跨段落的引用；`path` 字段便于快速检索树结构。

### 3.3 作业 / 批次管理

```sql
CREATE TABLE ingest_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    job_type TEXT DEFAULT 'initial_import',
    status TEXT DEFAULT 'pending', -- pending | running | completed | failed
    payload JSONB DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE TABLE processing_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    task_category TEXT NOT NULL,  -- segmentation | summarization | qa | etc.
    target_scope TEXT NOT NULL,   -- document | node | span | batch
    target_ids UUID[] DEFAULT '{}',
    llm_model TEXT,
    parameters JSONB DEFAULT '{}'::jsonb,
    status TEXT DEFAULT 'queued',
    scheduled_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE TABLE annotation_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    task_id UUID REFERENCES processing_tasks(id) ON DELETE SET NULL,
    batch_type TEXT NOT NULL,     -- entity_extraction | relation_extraction | manual_review
    source TEXT NOT NULL,         -- gpt-4.1 | reviewer@user | etc.
    status TEXT DEFAULT 'draft',
    confidence JSONB DEFAULT '{}'::jsonb,
    notes TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE annotation_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES annotation_batches(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,    -- node | span | entity | relation | event
    target_id UUID,               -- 可以为空（例如新实体）
    span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    payload JSONB NOT NULL,
    confidence NUMERIC(5,4),
    status TEXT DEFAULT 'pending', -- pending | approved | rejected
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(batch_id, target_type, target_id, span_id)
);
```

### 3.4 实体与属性

```sql
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    universe_id UUID REFERENCES universes(id) ON DELETE SET NULL,
    work_id UUID REFERENCES works(id) ON DELETE SET NULL,
    edition_id UUID REFERENCES editions(id) ON DELETE SET NULL,
    entity_type TEXT NOT NULL,     -- character | item | location | organization | concept
    canonical_name TEXT NOT NULL,
    description TEXT,
    origin_span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    scope TEXT DEFAULT 'edition',  -- edition | work | global
    status TEXT DEFAULT 'draft',   -- draft | verified | deprecated
    created_batch_id UUID REFERENCES annotation_batches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE entity_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    language TEXT,
    alias_type TEXT DEFAULT 'nickname',
    source_batch_id UUID REFERENCES annotation_batches(id) ON DELETE SET NULL,
    is_preferred BOOLEAN DEFAULT FALSE,
    UNIQUE(entity_id, alias)
);

CREATE TABLE entity_attributes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    attr_key TEXT NOT NULL,
    attr_value JSONB NOT NULL,
    source_span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    source_batch_id UUID REFERENCES annotation_batches(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'pending',
    UNIQUE(entity_id, attr_key, source_span_id)
);

CREATE TABLE entity_mentions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    span_id UUID NOT NULL REFERENCES text_spans(id) ON DELETE CASCADE,
    batch_id UUID NOT NULL REFERENCES annotation_batches(id) ON DELETE CASCADE,
    mention_type TEXT DEFAULT 'explicit',
    confidence NUMERIC(5,4),
    is_verified BOOLEAN DEFAULT FALSE,
    verified_by TEXT,
    verified_at TIMESTAMPTZ,
    UNIQUE(entity_id, span_id, batch_id)
);
```

### 3.5 关系、事件与事实

```sql
CREATE TABLE entity_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    universe_id UUID REFERENCES universes(id) ON DELETE CASCADE,
    work_id UUID REFERENCES works(id) ON DELETE CASCADE,
    edition_id UUID REFERENCES editions(id) ON DELETE CASCADE,
    source_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,      -- family | alliance | ownership | conflict | etc.
    direction TEXT DEFAULT 'directed',
    description TEXT,
    status TEXT DEFAULT 'draft',
    created_batch_id UUID REFERENCES annotation_batches(id) ON DELETE SET NULL
);

CREATE TABLE relation_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    relation_id UUID NOT NULL REFERENCES entity_relations(id) ON DELETE CASCADE,
    span_id UUID NOT NULL REFERENCES text_spans(id) ON DELETE CASCADE,
    batch_id UUID REFERENCES annotation_batches(id) ON DELETE SET NULL,
    confidence NUMERIC(5,4),
    notes TEXT,
    UNIQUE(relation_id, span_id)
);

CREATE TABLE narrative_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_id UUID REFERENCES works(id) ON DELETE CASCADE,
    edition_id UUID REFERENCES editions(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    event_type TEXT DEFAULT 'plot_point',
    summary TEXT,
    start_span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    end_span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    chronology_order NUMERIC(10,2),
    importance TEXT DEFAULT 'major',
    status TEXT DEFAULT 'draft',
    created_batch_id UUID REFERENCES annotation_batches(id) ON DELETE SET NULL,
    UNIQUE(edition_id, title, start_span_id)
);

CREATE TABLE event_participants (
    event_id UUID NOT NULL REFERENCES narrative_events(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'participant',
    contribution TEXT,
    span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    PRIMARY KEY (event_id, entity_id, role)
);

CREATE TABLE fact_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_id UUID REFERENCES works(id) ON DELETE CASCADE,
    edition_id UUID REFERENCES editions(id) ON DELETE CASCADE,
    span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    fact_type TEXT NOT NULL,        -- oath | prophecy | rule | timeline | item_property etc.
    subject_entity_id UUID REFERENCES entities(id) ON DELETE SET NULL,
    object_entity_id UUID REFERENCES entities(id) ON DELETE SET NULL,
    payload JSONB NOT NULL,
    batch_id UUID REFERENCES annotation_batches(id) ON DELETE SET NULL,
    confidence NUMERIC(5,4),
    status TEXT DEFAULT 'draft'
);
```

### 3.6 勘误与版本控制

```sql
CREATE TABLE edition_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    label TEXT,
    change_summary TEXT,
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(edition_id, version_number)
);

CREATE TABLE change_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id UUID REFERENCES editions(id) ON DELETE CASCADE,
    version_id UUID REFERENCES edition_versions(id) ON DELETE SET NULL,
    source TEXT NOT NULL,               -- manual | llm_auto | script
    reason TEXT,
    status TEXT DEFAULT 'pending',      -- pending | applied | rolled_back
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    applied_at TIMESTAMPTZ,
    rolled_back_at TIMESTAMPTZ
);

CREATE TABLE change_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    change_set_id UUID NOT NULL REFERENCES change_sets(id) ON DELETE CASCADE,
    target_table TEXT NOT NULL,
    target_id UUID,
    operation TEXT NOT NULL,           -- insert | update | delete
    column_name TEXT,
    old_value JSONB,
    new_value JSONB,
    span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    notes TEXT
);

CREATE TABLE review_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    change_set_id UUID NOT NULL REFERENCES change_sets(id) ON DELETE CASCADE,
    reviewer TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    decided_at TIMESTAMPTZ,
    decision TEXT,
    comments TEXT
);
```

### 3.7 文本聚合与统计快照

```sql
CREATE TABLE node_rollups (
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    node_type TEXT NOT NULL,
    depth SMALLINT NOT NULL,
    parent_node_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000'::uuid,
    total_nodes BIGINT NOT NULL,
    total_words BIGINT,
    total_chars BIGINT,
    first_node_id UUID,
    last_node_id UUID,
    min_sort_index INTEGER,
    max_sort_index INTEGER,
    refreshed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (edition_id, node_type, depth, parent_node_id)
);

CREATE TABLE span_rollups (
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    span_type TEXT NOT NULL,
    bucket TEXT NOT NULL,             -- 例如 chapter:0001、volume:0001
    total_spans BIGINT NOT NULL,
    total_words BIGINT,
    total_chars BIGINT,
    refreshed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (edition_id, span_type, bucket)
);
```

> `node_rollups` 与 `span_rollups` 由定时任务刷新，为超长文本提供 O(1) 级别的章节/卷统计能力；`parent_node_id` 默认的全零 UUID 表示对整本书或卷层级的聚合。

### 3.8 标签与交叉引用（可选）

```sql
CREATE TABLE tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace TEXT DEFAULT 'default',
    tag TEXT NOT NULL,
    description TEXT,
    UNIQUE(namespace, tag)
);

CREATE TABLE tag_links (
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,         -- work | edition | entity | event | node
    target_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tag_id, target_type, target_id)
);
```

---

## 4. 数据生命周期与流程

### 4.1 导入流程
1. 创建 `works` / `editions`，登记源文件于 `edition_files`。
2. 启动 `ingest_jobs`，解析原始文本，根据层级规则生成 `document_nodes` 树，并补齐 `path` 与 `sort_index`。
3. 自动切分段落/句子，生成 `text_spans`（至少段落级），写入 `node_text_stats`。
4. 生成初始 `edition_versions`（v1.0 原始导入）与对应的 `change_set` 记录。

### 4.2 LLM 抽取流程
1. 通过 `processing_tasks` 规划任务范围（如章节批次）。
2. 将 LLM 或规则的输出写入 `annotation_batches` / `annotation_items`。
3. 将通过审核的条目投影到知识层：
   - 新实体：写入 `entities`、`entity_aliases`、`entity_attributes`。
   - 关系：写入 `entity_relations` + `relation_evidence`。
   - 事件：写入 `narrative_events` + `event_participants`。
   - 概念事实：写入 `fact_records`。
4. 每批更新时生成 `change_sets`，关联到 `annotation_batch` 以便追溯。

### 4.3 勘误与回滚
1. 人工或脚本在 UI 中触发修改时，创建 `change_set`，将差异写入 `change_items`。
2. 提交审核：生成 `review_tasks`，由人工审核通过后执行。
3. 应用后更新相关 `edition_versions`，必要时更新 `status` 为 `verified`。
4. 回滚：记录 `rolled_back_at`，并生成新的 `change_set` 描述逆向操作。

### 4.4 新增小说扩展
- 新小说只需新增 `work` + `edition`，后续流程可复用。
- 若同一作品有多译本，可在 `editions` 内并行存在，`scope='work'` 的实体用于跨译本汇总。
- `tag_links` 可标注流派、世界观系列、采集来源等维度，方便全局检索。
- 如果存在共用世界观，新增 `universe` 记录并为相关 `work` 创建 `universe_memberships`，再通过 `universe_links` 将跨作品实体对齐。

---

## 5. 查询与应用示例

### 5.1 统计视图与物化视图
```sql
CREATE MATERIALIZED VIEW mv_edition_node_stats AS
SELECT
    dn.edition_id,
    dn.node_type,
    dn.depth,
    COUNT(*)                           AS node_count,
    SUM(dn.word_count)                 AS total_words,
    SUM(dn.char_count)                 AS total_chars,
    MIN(dn.sort_index)                 AS min_sort_index,
    MAX(dn.sort_index)                 AS max_sort_index,
    MAX(dn.updated_at)                 AS last_updated_at
FROM document_nodes dn
GROUP BY dn.edition_id, dn.node_type, dn.depth
WITH NO DATA;

CREATE MATERIALIZED VIEW mv_universe_entity_presence AS
SELECT
    u.id                               AS universe_id,
    e.entity_type,
    e.canonical_name,
    COUNT(DISTINCT e.work_id)          AS work_coverage,
    COUNT(DISTINCT em.span_id)         AS mention_spans,
    MAX(em.verified_at)                AS last_verified_at
FROM universes u
JOIN universe_links ul ON ul.universe_id = u.id AND ul.target_type = 'entity'
JOIN entities e ON e.id = ul.target_id
LEFT JOIN entity_mentions em ON em.entity_id = e.id
GROUP BY u.id, e.entity_type, e.canonical_name
WITH NO DATA;

CREATE VIEW vw_task_backlog AS
SELECT
    pt.edition_id,
    pt.task_category,
    pt.status,
    COUNT(*) AS task_count,
    MAX(pt.scheduled_at) AS last_scheduled
FROM processing_tasks pt
WHERE pt.status IN ('queued', 'running')
GROUP BY pt.edition_id, pt.task_category, pt.status;
```

> 建议在日常作业中使用 `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_edition_node_stats;` 等命令增量刷新，支持百万级章节快速检索。

### 5.2 获取章节树
```sql
SELECT path, node_type, title
FROM document_nodes
WHERE edition_id = :edition
ORDER BY path;
```

### 5.3 查询人物在文本中的所有提及
```sql
SELECT dn.path, ts.start_char, ts.end_char, ts.text_snippet
FROM entity_mentions em
JOIN text_spans ts ON em.span_id = ts.id
JOIN document_nodes dn ON ts.node_id = dn.id
WHERE em.entity_id = :entity
ORDER BY dn.path, ts.start_char;
```

### 5.4 追踪勘误历史
```sql
SELECT cs.id, cs.status, ci.target_table, ci.column_name, ci.old_value, ci.new_value
FROM change_sets cs
JOIN change_items ci ON cs.id = ci.change_set_id
WHERE cs.edition_id = :edition
ORDER BY cs.created_at DESC;
```

### 5.5 生成指定事件的参与者网络
```sql
SELECT ne.title, ep.role, e.canonical_name, ts.text_snippet
FROM narrative_events ne
JOIN event_participants ep ON ne.id = ep.event_id
LEFT JOIN entities e ON ep.entity_id = e.id
LEFT JOIN text_spans ts ON ep.span_id = ts.id
WHERE ne.id = :event_id;
```

---

## 6. 索引与性能建议

- **表分区策略**
  - `document_nodes` 建议按 `edition_id` 进行 `LIST` 分区，或对超长单本再按 `node_type` / `depth` 进行子分区：
    ```sql
    ALTER TABLE document_nodes PARTITION BY LIST (edition_id);
    CREATE TABLE document_nodes_part_2025 PARTITION OF document_nodes
        FOR VALUES IN ('6b44f716-...');
    ```
  - `text_spans` 可按 `edition_id` + `span_type` 进行 `LIST` / `HASH` 分区，支持并行刷新 `node_rollups`。

- **层级查询索引**
  - 将 `document_nodes.path` 改为 `ltree` 类型，配合 `CREATE INDEX idx_document_nodes_path_gist ON document_nodes USING GIST(path);` 以 O(log n) 获取子树。
  - 对连续编号字段（如 `sort_index`）构建 `BRIN` 索引，降低索引段数量：
    ```sql
    CREATE INDEX idx_document_nodes_brin ON document_nodes USING BRIN (edition_id, sort_index);
    ```

- **跨度与全文检索**
  - `text_spans`：`CREATE INDEX idx_text_spans_position ON text_spans (node_id, start_char);`
  - 若需全文搜索：
    ```sql
    ALTER TABLE text_spans ADD COLUMN ts_vector tsvector;
    CREATE INDEX idx_text_spans_fts ON text_spans USING GIN (ts_vector);
    ```
    并在导入/更新时维护 `ts_vector`。

- **实体唯一性与模糊匹配**
  - 使用部分唯一索引替代表内 `UNIQUE` 约束，分层保证同名冲突：
    ```sql
    CREATE UNIQUE INDEX uniq_entities_edition
        ON entities (canonical_name, entity_type, edition_id)
        WHERE edition_id IS NOT NULL;

    CREATE UNIQUE INDEX uniq_entities_work
        ON entities (canonical_name, entity_type, work_id)
        WHERE edition_id IS NULL AND work_id IS NOT NULL;

    CREATE UNIQUE INDEX uniq_entities_universe
        ON entities (canonical_name, entity_type, universe_id)
        WHERE edition_id IS NULL AND work_id IS NULL AND universe_id IS NOT NULL;
    ```
  - 模糊检索：`CREATE INDEX idx_entity_name_trgm ON entities USING GIN (canonical_name gin_trgm_ops);`
    同理为 `entity_aliases.alias` 建立 `GIN` + `pg_trgm` 索引。

- **关系与事件加速**
  - `entity_relations` 建立多组合索引以覆盖查询场景：
    ```sql
    CREATE INDEX idx_relations_source ON entity_relations (source_entity_id, relation_type);
    CREATE INDEX idx_relations_target ON entity_relations (target_entity_id, relation_type);
    CREATE UNIQUE INDEX uniq_relations_scope
        ON entity_relations (source_entity_id, target_entity_id, relation_type, COALESCE(edition_id, work_id, universe_id));
    ```
  - `event_participants`：`CREATE INDEX idx_event_participants_entity ON event_participants (entity_id, role);`

- **批次/作业监控**
  - 对 `processing_tasks`、`annotation_batches` 的 `status` 建立部分索引，提高待处理作业查询效率：
    ```sql
    CREATE INDEX idx_processing_tasks_queue
        ON processing_tasks (status, scheduled_at)
        WHERE status IN ('queued', 'running');
    ```

- **统计视图维护**
  - 为 `mv_edition_node_stats`、`mv_universe_entity_presence` 建立 `REFRESH MATERIALIZED VIEW CONCURRENTLY` 所需的 `UNIQUE INDEX`：
    ```sql
    CREATE UNIQUE INDEX mv_edition_node_stats_uq
        ON mv_edition_node_stats (edition_id, node_type, depth);

    CREATE UNIQUE INDEX mv_universe_entity_presence_uq
        ON mv_universe_entity_presence (universe_id, entity_type, canonical_name);
    ```
  - 周期性运行 `ANALYZE` 与自定义 `autovacuum` 阈值：对百万级插入的表（`text_spans`, `entity_mentions`）将 `autovacuum_vacuum_scale_factor` 调小到 `0.05` 以内。

- **IO 优化**
  - 大字段使用 `TOAST` 压缩，必要时对历史版本（归档的 `annotation_items`）使用 `pg_dump` + 外部对象存储。
  - 采用 `pg_prewarm` 预热 `node_rollups` 或热门 `document_nodes` 分区，加速重启后的首次访问。

---

## 7. 集成与扩展
- **向量检索**：`node_text_stats.embedding_vector` 搭配 `pgvector`，可直接与语义检索或 RAG 管道对接。
- **外部知识图**：通过 `universes + universe_links` 或 `entities.scope='global'` 实现跨作品实体同一化，必要时建立对外部 ID 的映射表。
- **时间线管理**：在 `narrative_events` 上增加 `timeline_bucket` 或衍生表构建全局时间轴。
- **多模态支持**：后续若出现插图、地图，可在 `edition_files` 增加 `file_role='image'` 并与节点关联。

---

## 8. 实施提示
- 初始化时执行：
  - `CREATE EXTENSION IF NOT EXISTS pgcrypto;`
  - 若使用向量：`CREATE EXTENSION IF NOT EXISTS vector;`
- 命名约定：表名复数、字段蛇形；所有时间字段使用 `TIMESTAMPTZ`。
- 推荐使用迁移工具（例如 `sqitch`/`golang-migrate`），按模块拆分迁移脚本。
- 为重要外键加 `ON DELETE CASCADE` 避免孤儿记录，但对审核数据谨慎使用。
- 测试数据可从 `data/books/webnovel` 择取三部不同风格小说，验证多层级结构与多语言兼容性。
- 针对百万级文本导入，优先使用 `COPY` + 分区临时表，再 `INSERT ... SELECT` 合并至主表，并根据批量大小调高 `maintenance_work_mem` 与 `checkpoint_timeout`。

---

## 9. 后续工作清单
- 衍生视图：
  - `vw_entity_latest_mentions`：聚合最近一次提及。
  - `vw_change_audit`：扁平化呈现 `change_sets` + `review_tasks`。
- 权限模型：按用户角色拆分可写表（如仅审稿人可修改 `status='verified'`）。
- API 规划：将 `document_nodes`/`text_spans`/`entities` 暴露为 REST/GraphQL 资源，支持 RAG 调用。
- 数据质量监控：对 `annotation_batches` 添加通过率、回退率统计字段。

---

## 10. 总结
本方案基于树形文本结构、可复用的 span 概念与批次化的知识生产流程，为多小说、多语言的数据整合提供统一底座。通过拆分实体/关系/事件表、规范化证据链接，并引入 `change_set` 与 `annotation_batch` 两条主线，可确保：
- **新增小说**：仅需新增 `work` 与 `edition`，导入流程即可复用。
- **溯源与审核**：任何知识条目都可回溯到具体字符区间及生成批次。
- **持续迭代**：批次化的作业与变更日志支持自动抽取与人工校对交替进行。
- **可扩展性**：预留 JSONB、向量与标签机制，便于后续知识图谱、RAG、可视化等模块落地。
- **共享世界观**：`universes` 及其关联表将跨作品实体对齐与统计提升为一等公民。
- **大规模性能**：分区、BRIN/GiST/GiN 索引与物化视图保障千万字规模下的查询与刷新效率。


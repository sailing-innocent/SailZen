# LLM驱动的世界观构造系统 PostgreSQL 数据库设计

## 1. 设计原则

- **多层级适配**：原始文本可能包含“卷/部/章/节/段/句”等任意组合，采用树形节点描述结构。
- **强溯源**：所有实体、事件、关系、事实都必须能回溯到具体文本区间（段落/句子/字符范围）。
- **逐步演化**：允许多版本导入、LLM 反复抽取、人工校对与回滚；保留历史轨迹。
- **语义解耦**：实体、关系、事件等知识层与文本层分离。知识层只通过 span 绑定文本证据。
- **扩展与互操作**：尽量使用规范化结构（桥接表、枚举、JSONB 拓展字段），方便未来接入向量检索、知识图谱等模块。
- **数据作业透明化**：导入、抽取、校对都以“批次”形式登记，便于重跑、审核和追责。
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

---

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
    label TEXT,                   -- “第一章”等显示标签
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



为了支持**从零开始的辅助创作**，我们需要将系统重心从“分析优先”转变为“创作优先”。这意味着世界观的构建和小说正文的撰写是一个并行的、相互促进的、可灵活迭代的过程。作者可能先构思核心设定，再动笔写正文；也可能在写作中迸发灵感，反过来丰富和修改世界观。

本文档旨在设计一套支持此创作模式的新功能和工作流，核心目标是：
- **世界观优先**：允许用户在没有正文的情况下，独立创建、管理和演化世界观元素（人物、地点、事件、设定等）。
- **灵活关联**：当正文被创作出来后，可以方便地将文中内容与已存在的世界观元素关联起来。
- **结构化创作**：支持对“情节”、“人物弧光”等抽象创作概念进行结构化管理。
- **智能重构**：在世界观发生重大变更时，能智能地提示作者正文中可能受影响的部分，辅助其进行高效重构。

### 1.2 设计哲学

- **知识与文本解耦**：世界观知识库（`Universe`/`Work` 级别）是第一公民，手稿 (`Edition` 级别) 是其在特定版本下的叙事性表达。两者可以独立演化，但系统会持续追踪它们之间的一致性。
- **蓝图与实例化**：一个 `Entity` 是一个抽象的“设计蓝图”（例如，角色“孙悟空”的设定集），而 `EntityMention` 则是该蓝图在文本中的一次“实例化引用”（例如，第一章中提到“那猴王”）。
- **迭代即版本**：所有的变更，无论是对世界观蓝图的修改还是对文本的编辑，都应被视为一次迭代。系统的 `ChangeSet` 机制将被扩展，以同时支持对知识库和文本的原子化版本控制。

- **`entities`, `entity_relations`, `narrative_events` 表**:
  - 当前这些表与 `edition_id` 强关联。需将其调整为主要关联 `work_id` 或 `universe_id`。
  - `edition_id` 字段应变为**可选**，用于表示该知识条目首次在哪个版本的手稿中被明确定义或提及。
  - `origin_span_id` (在 `entities` 表中) 也应变为**可选**。一个实体可以先被创建，后续再关联到文本。

### 2.2 结构化创作概念建模


#### 2.2.1 情节结构 (Plot Structure)

情节是事件的有序集合。我们可以利用现有的 `narrative_events` 表来构建复杂的叙事结构。
- **层级关系**：`narrative_events` 表中的 `parent_id` (需要添加，类似 `document_nodes`) 可以用来表示“幕 > 场景 > 关键时刻”这样的层级。
- **时序关系**：`chronology_order` 字段可以用来定义事件在故事时间线上的顺序。
- **因果/逻辑关系**：我们可以引入一个新的桥接表 `event_relations` 来表示事件之间的复杂关系（例如，“事件A是事件B的原因”，“事件C是事件D的转折点”）。

```sql
-- 可选的新表，用于增强情节建模
CREATE TABLE event_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_event_id UUID NOT NULL REFERENCES narrative_events(id) ON DELETE CASCADE,
    target_event_id UUID NOT NULL REFERENCES narrative_events(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL, -- e.g., 'causes', 'precedes', 'conflicts_with'
    work_id UUID REFERENCES works(id) ON DELETE CASCADE,
    description TEXT,
    UNIQUE(source_event_id, target_event_id, relation_type)
);
```

#### 2.2.2 人物弧光 (Character Arc)

人物弧光本质上是与特定人物相关的一系列关键事件的集合。
- 我们可以将其建模为一个新的实体类型或一个专门的表。一个更灵活的方式是引入“集合”或“分组”的概念。

```sql
-- 新表：用于组织任何类型的知识元素
CREATE TABLE knowledge_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_id UUID NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    collection_type TEXT NOT NULL, -- e.g., 'character_arc', 'plotline', 'theme'
    description TEXT,
    meta_data JSONB DEFAULT '{}'::jsonb, -- 可存储如主角ID等信息
    UNIQUE(work_id, collection_type, name)
);

CREATE TABLE collection_items (
    collection_id UUID NOT NULL REFERENCES knowledge_collections(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL, -- 'narrative_event', 'entity', 'relation'
    target_id UUID NOT NULL,
    sort_order INTEGER, -- 用于定义弧光中的事件顺序
    role_in_collection TEXT, -- e.g., 'inciting_incident', 'climax', 'resolution'
    PRIMARY KEY (collection_id, target_type, target_id)
);
```
这个通用模型不仅可以用来定义人物弧光，还可以用来组织“战争”或“爱情”等多条情节线 (`plotline`)。

#### 2.2.3 核心设定 (World Anvil / Lore)

世界观中的抽象设定，如魔法系统、物理规律、科技树等。
- **建模方式**：使用 `entities` 表，`entity_type` 设置为 `concept` 或 `lore_entry`。
- **内容存储**：设定的具体内容（如魔法规则）可以使用 `entity_attributes` 表以键值对形式结构化存储，或者在一个 `description` 字段中存放大段Markdown文本。

### 2.3 版本控制扩展

现有的 `change_sets` 和 `change_items` 机制非常适合跟踪变更。我们需要将其应用范围从“文本标注”扩展到“世界观编辑”。
- `change_items.target_table` 将不仅包含 `entity_mentions` 等，还会直接包含 `entities`, `narrative_events`, `knowledge_collections` 等核心知识表。
- 这意味着对一个角色设定的任何修改，都会像Git提交一样被记录下来，可以被审核、追溯和回滚。

---

## 3. 后端 API 扩展

为支持上述数据模型，需要新增和修改一系列API端点。所有新端点都应遵循 `BACKEND_DESIGN.md` 中定义的规范。

### 3.1 核心知识库 API (Work-level)

这些API直接在 `work` 层面操作，独立于任何 `edition`。

```
// 实体管理
POST   /api/v1/works/{work_id}/entities
GET    /api/v1/works/{work_id}/entities
GET    /api/v1/entities/{entity_id}
PUT    /api/v1/entities/{entity_id}
DELETE /api/v1/entities/{entity_id}

// 事件/情节管理
POST   /api/v1/works/{work_id}/events
GET    /api/v1/works/{work_id}/events

// 关系管理
POST   /api/v1/works/{work_id}/relations
GET    /api/v1/works/{work_id}/relations

// 集合/弧光管理
POST   /api/v1/works/{work_id}/collections
GET    /api/v1/works/{work_id}/collections
POST   /api/v1/collections/{collection_id}/items
```

### 3.2 文本与知识关联 API

这些API用于在写作过程中建立文本和知识库的连接。

```
// 在文本中创建提及 (Mention)
POST   /api/v1/editions/{edition_id}/mentions
Body: {
  "entity_id": "uuid",
  "node_id": "uuid",
  "start_char": 100,
  "end_char": 105,
  "text_snippet": "孙猴子"
}

// 从文本中提取并创建新实体
POST   /api/v1/editions/{edition_id}/extract-entity
Body: {
  "node_id": "uuid",
  "start_char": 200,
  "end_char": 203,
  "canonical_name": "金箍棒",
  "entity_type": "item"
}
```

### 3.3 智能与重构 API

```
// 获取实体在所有版本中的提及
GET    /api/v1/entities/{entity_id}/all-mentions

// 一致性检查
POST   /api/v1/works/{work_id}/consistency-check
Body: {
  "change_set_id": "uuid" // 提交一个变更集，分析其对现有知识和文本的影响
}
// 响应会包含可能存在冲突或不一致的文本节点和知识条目列表。

// LLM 创作辅助
POST   /api/v1/works/{work_id}/llm/brainstorm
Body: {
  "topic": "Suggest character names for a stoic warrior",
  "context": {...}
}

POST   /api/v1/works/{work_id}/llm/elaborate
Body: {
  "target_type": "entity",
  "target_id": "uuid",
  "instructions": "Flesh out the backstory for this character based on these key points..."
}
```

---

## 4. LLM 集成策略

LLM在创作流程中的角色将从“分析员”转变为“创作伙伴”。

- **创意生成 (Brainstorming)**：
  - **功能**：为人物、地点、情节、对话等提供创意点子。
  - **实现**：调用 LLM，提供主题和可选的上下文（如作品风格、已有设定）。
- **内容扩写 (Elaboration)**：
  - **功能**：根据用户提供的要点或大纲，扩写成详细的描述或章节段落。
  - **实现**：将用户的要点和相关的世界观知识（如人物设定）打包成上下文，喂给LLM。
- **一致性维护 (Consistency Keeping)**：
  - **功能**：当用户修改核心设定时，LLM 负责检查该变更是否与已有情节或设定冲突。
  - **实现**：当一个 `ChangeSet` 提交时，触发一个任务。该任务收集与变更相关的知识（如被修改实体的所有提及和参与的事件），然后让 LLM 判断是否存在逻辑矛盾。
- **风格模仿 (Style Mimicry)**：
  - **功能**：在续写或润色时，模仿作者在同一作品中已有的写作风格。
  - **实现**：在调用 LLM 时，通过 RAG (Retrieval-Augmented Generation) 动态检索作品中的代表性段落作为风格示例。

---

## 5. 总结

通过上述设计，SailZen 可以平滑地从一个纯粹的文本分析工具，演变为一个强大的、以世界观为核心的辅助创作平台。关键的转变在于：
1.  **数据层面**：将核心知识元素与具体文稿解耦，使其成为 `Work` 级别的资产。
2.  **功能层面**：引入对情节、人物弧光等抽象创作概念的结构化管理能力。
3.  **API 层面**：提供一套全新的、面向创作的API，用于独立管理世界观和处理重构任务。
4.  **LLM 应用层面**：将 LLM 的能力从信息提取扩展到创意生成、内容扩写和一致性维护。

这个设计复用了现有稳固的数据基础，并通过扩展使其能够支持更动态和复杂的创作工作流。

-- ============================================================================
-- Novel Analysis Tables Migration
-- @file create_novel_analysis_tables.sql
-- @brief Creates tables for novel outline analysis and character/setting management
-- @author sailing-innocent
-- @date 2025-02-01
-- ============================================================================

-- 确保启用 pg_trgm 扩展（用于模糊搜索）
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- 1. 大纲表 (outlines)
-- ============================================================================
CREATE TABLE IF NOT EXISTS outlines (
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

CREATE INDEX IF NOT EXISTS idx_outlines_edition ON outlines(edition_id);
CREATE INDEX IF NOT EXISTS idx_outlines_type ON outlines(outline_type);
CREATE INDEX IF NOT EXISTS idx_outlines_status ON outlines(status);

COMMENT ON TABLE outlines IS '大纲表 - 存储作品的各类大纲结构';
COMMENT ON COLUMN outlines.outline_type IS '大纲类型: main(主线), subplot(支线), character_arc(人物弧)';
COMMENT ON COLUMN outlines.status IS '状态: draft(草稿), analyzing(分析中), reviewed(已审核), finalized(已定稿)';
COMMENT ON COLUMN outlines.source IS '来源: manual(手动), ai_generated(AI生成), hybrid(混合)';

-- ============================================================================
-- 2. 大纲节点表 (outline_nodes)
-- ============================================================================
CREATE TABLE IF NOT EXISTS outline_nodes (
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

CREATE INDEX IF NOT EXISTS idx_outline_nodes_outline ON outline_nodes(outline_id);
CREATE INDEX IF NOT EXISTS idx_outline_nodes_parent ON outline_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_outline_nodes_path ON outline_nodes(outline_id, path);
CREATE INDEX IF NOT EXISTS idx_outline_nodes_sort ON outline_nodes(outline_id, sort_index);

COMMENT ON TABLE outline_nodes IS '大纲节点表 - 树形结构表示情节层级';
COMMENT ON COLUMN outline_nodes.node_type IS '节点类型: act(幕), arc(弧), beat(节拍), scene(场景), turning_point(转折点)';
COMMENT ON COLUMN outline_nodes.significance IS '重要程度: critical(关键), major(主要), normal(普通), minor(次要)';
COMMENT ON COLUMN outline_nodes.path IS '物化路径，如 "0001.0003"';

-- ============================================================================
-- 3. 大纲事件表 (outline_events)
-- ============================================================================
CREATE TABLE IF NOT EXISTS outline_events (
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

CREATE INDEX IF NOT EXISTS idx_outline_events_node ON outline_events(outline_node_id);
CREATE INDEX IF NOT EXISTS idx_outline_events_chrono ON outline_events(chronology_order);
CREATE INDEX IF NOT EXISTS idx_outline_events_type ON outline_events(event_type);

COMMENT ON TABLE outline_events IS '大纲事件表 - 记录情节中的关键事件';
COMMENT ON COLUMN outline_events.event_type IS '事件类型: plot(情节), conflict(冲突), revelation(揭示), resolution(解决), climax(高潮)';

-- ============================================================================
-- 4. 人物表 (characters)
-- ============================================================================
CREATE TABLE IF NOT EXISTS characters (
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

CREATE INDEX IF NOT EXISTS idx_characters_edition ON characters(edition_id);
CREATE INDEX IF NOT EXISTS idx_characters_role ON characters(role_type);
CREATE INDEX IF NOT EXISTS idx_characters_status ON characters(status);
CREATE INDEX IF NOT EXISTS idx_characters_name_trgm ON characters USING GIN (canonical_name gin_trgm_ops);

COMMENT ON TABLE characters IS '人物表 - 存储作品中的人物信息';
COMMENT ON COLUMN characters.role_type IS '角色类型: protagonist(主角), antagonist(反派), deuteragonist(二号主角), supporting(配角), minor(龙套), mentioned(提及)';
COMMENT ON COLUMN characters.importance_score IS '重要性评分 0-1，基于出场频率等计算';

-- ============================================================================
-- 5. 人物别名表 (character_aliases)
-- ============================================================================
CREATE TABLE IF NOT EXISTS character_aliases (
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

CREATE INDEX IF NOT EXISTS idx_character_aliases_char ON character_aliases(character_id);
CREATE INDEX IF NOT EXISTS idx_character_aliases_alias_trgm ON character_aliases USING GIN (alias gin_trgm_ops);

COMMENT ON TABLE character_aliases IS '人物别名表 - 存储人物的各种称呼';
COMMENT ON COLUMN character_aliases.alias_type IS '别名类型: nickname(昵称), title(头衔), formal_name(正式名), pen_name(笔名), code_name(代号)';

-- ============================================================================
-- 6. 人物属性表 (character_attributes)
-- ============================================================================
CREATE TABLE IF NOT EXISTS character_attributes (
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

CREATE INDEX IF NOT EXISTS idx_character_attrs_char ON character_attributes(character_id);
CREATE INDEX IF NOT EXISTS idx_character_attrs_category ON character_attributes(category);
CREATE INDEX IF NOT EXISTS idx_character_attrs_status ON character_attributes(status);

COMMENT ON TABLE character_attributes IS '人物属性表 - 存储人物的各类属性';
COMMENT ON COLUMN character_attributes.category IS '属性类别: basic(基础), appearance(外貌), personality(性格), ability(能力), background(背景), goal(目标)';

-- ============================================================================
-- 7. 人物弧线表 (character_arcs)
-- ============================================================================
CREATE TABLE IF NOT EXISTS character_arcs (
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

CREATE INDEX IF NOT EXISTS idx_character_arcs_char ON character_arcs(character_id);
CREATE INDEX IF NOT EXISTS idx_character_arcs_type ON character_arcs(arc_type);

COMMENT ON TABLE character_arcs IS '人物弧线表 - 记录人物的成长变化轨迹';
COMMENT ON COLUMN character_arcs.arc_type IS '弧线类型: growth(成长), fall(堕落), flat(平稳), transformation(转变), redemption(救赎)';

-- ============================================================================
-- 8. 人物关系表 (character_relations)
-- ============================================================================
CREATE TABLE IF NOT EXISTS character_relations (
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

CREATE INDEX IF NOT EXISTS idx_char_relations_edition ON character_relations(edition_id);
CREATE INDEX IF NOT EXISTS idx_char_relations_source ON character_relations(source_character_id);
CREATE INDEX IF NOT EXISTS idx_char_relations_target ON character_relations(target_character_id);
CREATE INDEX IF NOT EXISTS idx_char_relations_type ON character_relations(relation_type);

COMMENT ON TABLE character_relations IS '人物关系表 - 存储人物之间的关系';
COMMENT ON COLUMN character_relations.relation_type IS '关系类型: family(亲属), romance(恋爱), friendship(友谊), rivalry(竞争), mentor(师徒), alliance(同盟), enemy(敌对)';

-- ============================================================================
-- 9. 设定表 (novel_settings) - 使用 novel_settings 避免与已有 settings 表冲突
-- ============================================================================
CREATE TABLE IF NOT EXISTS novel_settings (
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

CREATE INDEX IF NOT EXISTS idx_novel_settings_edition ON novel_settings(edition_id);
CREATE INDEX IF NOT EXISTS idx_novel_settings_type ON novel_settings(setting_type);
CREATE INDEX IF NOT EXISTS idx_novel_settings_category ON novel_settings(category);
CREATE INDEX IF NOT EXISTS idx_novel_settings_status ON novel_settings(status);
CREATE INDEX IF NOT EXISTS idx_novel_settings_name_trgm ON novel_settings USING GIN (canonical_name gin_trgm_ops);

COMMENT ON TABLE novel_settings IS '设定表 - 存储世界观设定元素';
COMMENT ON COLUMN novel_settings.setting_type IS '设定类型: item(物品), location(地点), organization(组织), concept(概念), magic_system(力量体系), creature(生物), event_type(事件类型)';

-- ============================================================================
-- 10. 设定属性表 (setting_attributes)
-- ============================================================================
CREATE TABLE IF NOT EXISTS setting_attributes (
    id SERIAL PRIMARY KEY,
    setting_id INTEGER NOT NULL REFERENCES novel_settings(id) ON DELETE CASCADE,
    attr_key VARCHAR NOT NULL,
    attr_value JSONB NOT NULL,
    source VARCHAR DEFAULT 'manual',
    source_node_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,
    status VARCHAR DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(setting_id, attr_key)
);

CREATE INDEX IF NOT EXISTS idx_setting_attrs_setting ON setting_attributes(setting_id);

COMMENT ON TABLE setting_attributes IS '设定属性表 - 存储设定的详细属性';

-- ============================================================================
-- 11. 设定关系表 (setting_relations)
-- ============================================================================
CREATE TABLE IF NOT EXISTS setting_relations (
    id SERIAL PRIMARY KEY,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    source_setting_id INTEGER NOT NULL REFERENCES novel_settings(id) ON DELETE CASCADE,
    target_setting_id INTEGER NOT NULL REFERENCES novel_settings(id) ON DELETE CASCADE,
    relation_type VARCHAR NOT NULL,  -- contains | belongs_to | produces | requires | opposes
    description TEXT,
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_setting_relations_edition ON setting_relations(edition_id);
CREATE INDEX IF NOT EXISTS idx_setting_relations_source ON setting_relations(source_setting_id);
CREATE INDEX IF NOT EXISTS idx_setting_relations_target ON setting_relations(target_setting_id);

COMMENT ON TABLE setting_relations IS '设定关系表 - 存储设定之间的关系';
COMMENT ON COLUMN setting_relations.relation_type IS '关系类型: contains(包含), belongs_to(属于), produces(产出), requires(需要), opposes(对立)';

-- ============================================================================
-- 12. 人物-设定关联表 (character_setting_links)
-- ============================================================================
CREATE TABLE IF NOT EXISTS character_setting_links (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    setting_id INTEGER NOT NULL REFERENCES novel_settings(id) ON DELETE CASCADE,
    link_type VARCHAR NOT NULL,  -- owns | belongs_to | created | uses | guards
    description TEXT,
    start_node_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,
    end_node_id INTEGER REFERENCES document_nodes(id) ON DELETE SET NULL,
    meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(character_id, setting_id, link_type)
);

CREATE INDEX IF NOT EXISTS idx_char_setting_links_char ON character_setting_links(character_id);
CREATE INDEX IF NOT EXISTS idx_char_setting_links_setting ON character_setting_links(setting_id);

COMMENT ON TABLE character_setting_links IS '人物-设定关联表 - 记录人物与设定的关系';
COMMENT ON COLUMN character_setting_links.link_type IS '关联类型: owns(拥有), belongs_to(隶属), created(创造), uses(使用), guards(守护)';

-- ============================================================================
-- 13. 文本证据表 (text_evidence)
-- ============================================================================
CREATE TABLE IF NOT EXISTS text_evidence (
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

CREATE INDEX IF NOT EXISTS idx_text_evidence_edition ON text_evidence(edition_id);
CREATE INDEX IF NOT EXISTS idx_text_evidence_node ON text_evidence(node_id);
CREATE INDEX IF NOT EXISTS idx_text_evidence_target ON text_evidence(target_type, target_id);

COMMENT ON TABLE text_evidence IS '文本证据表 - 存储分析结果的原文依据';
COMMENT ON COLUMN text_evidence.target_type IS '目标类型: outline_node, character, character_attribute, setting, relation';
COMMENT ON COLUMN text_evidence.evidence_type IS '证据类型: explicit(明确陈述), implicit(隐含暗示), inferred(推断得出)';

-- ============================================================================
-- 14. 分析任务表 (analysis_tasks)
-- ============================================================================
CREATE TABLE IF NOT EXISTS analysis_tasks (
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

CREATE INDEX IF NOT EXISTS idx_analysis_tasks_edition ON analysis_tasks(edition_id);
CREATE INDEX IF NOT EXISTS idx_analysis_tasks_status ON analysis_tasks(status);
CREATE INDEX IF NOT EXISTS idx_analysis_tasks_type ON analysis_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_analysis_tasks_pending ON analysis_tasks(status, priority) WHERE status = 'pending';

COMMENT ON TABLE analysis_tasks IS '分析任务表 - 管理AI分析和人工标注任务';
COMMENT ON COLUMN analysis_tasks.task_type IS '任务类型: outline_extraction(大纲提取), character_detection(人物识别), setting_extraction(设定提取), relation_analysis(关系分析), attribute_extraction(属性提取)';
COMMENT ON COLUMN analysis_tasks.target_scope IS '目标范围: full(全书), range(范围), chapter(单章)';

-- ============================================================================
-- 15. 分析结果表 (analysis_results)
-- ============================================================================
CREATE TABLE IF NOT EXISTS analysis_results (
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

CREATE INDEX IF NOT EXISTS idx_analysis_results_task ON analysis_results(task_id);
CREATE INDEX IF NOT EXISTS idx_analysis_results_status ON analysis_results(review_status);
CREATE INDEX IF NOT EXISTS idx_analysis_results_type ON analysis_results(result_type);
CREATE INDEX IF NOT EXISTS idx_analysis_results_pending ON analysis_results(review_status) WHERE review_status = 'pending';

COMMENT ON TABLE analysis_results IS '分析结果表 - 存储待审核的分析结果';
COMMENT ON COLUMN analysis_results.review_status IS '审核状态: pending(待审核), approved(已批准), rejected(已拒绝), modified(已修改)';

-- ============================================================================
-- 更新触发器
-- ============================================================================

-- 自动更新 updated_at 字段的触发器函数（若 create_text_tables 已执行则已存在）
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为各表创建更新触发器
DROP TRIGGER IF EXISTS update_outlines_updated_at ON outlines;
CREATE TRIGGER update_outlines_updated_at
    BEFORE UPDATE ON outlines
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_outline_nodes_updated_at ON outline_nodes;
CREATE TRIGGER update_outline_nodes_updated_at
    BEFORE UPDATE ON outline_nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_characters_updated_at ON characters;
CREATE TRIGGER update_characters_updated_at
    BEFORE UPDATE ON characters
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_character_attributes_updated_at ON character_attributes;
CREATE TRIGGER update_character_attributes_updated_at
    BEFORE UPDATE ON character_attributes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_character_relations_updated_at ON character_relations;
CREATE TRIGGER update_character_relations_updated_at
    BEFORE UPDATE ON character_relations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_novel_settings_updated_at ON novel_settings;
CREATE TRIGGER update_novel_settings_updated_at
    BEFORE UPDATE ON novel_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

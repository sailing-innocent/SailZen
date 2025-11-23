-- Entity relations: Relationships between entities
CREATE TABLE entity_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    universe_id UUID REFERENCES universes(id) ON DELETE CASCADE,
    work_id UUID REFERENCES works(id) ON DELETE CASCADE,
    edition_id UUID REFERENCES editions(id) ON DELETE CASCADE,
    source_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL, -- family | alliance | ownership | conflict | etc.
    direction TEXT DEFAULT 'directed',
    description TEXT,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Relation evidence: Text spans supporting relationships
CREATE TABLE relation_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    relation_id UUID NOT NULL REFERENCES entity_relations(id) ON DELETE CASCADE,
    span_id UUID NOT NULL REFERENCES text_spans(id) ON DELETE CASCADE,
    confidence NUMERIC(5,4),
    notes TEXT,
    UNIQUE(relation_id, span_id)
);

-- Create indexes
CREATE INDEX idx_relations_source ON entity_relations(source_entity_id, relation_type);
CREATE INDEX idx_relations_target ON entity_relations(target_entity_id, relation_type);
CREATE INDEX idx_relation_evidence_relation ON relation_evidence(relation_id);
CREATE INDEX idx_relation_evidence_span ON relation_evidence(span_id);


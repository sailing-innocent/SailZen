-- Entities: Characters, locations, items, organizations, concepts
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    universe_id UUID REFERENCES universes(id) ON DELETE SET NULL,
    work_id UUID REFERENCES works(id) ON DELETE SET NULL,
    edition_id UUID REFERENCES editions(id) ON DELETE SET NULL,
    entity_type TEXT NOT NULL, -- character | item | location | organization | concept
    canonical_name TEXT NOT NULL,
    description TEXT,
    origin_span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    scope TEXT DEFAULT 'edition', -- edition | work | global
    status TEXT DEFAULT 'draft', -- draft | verified | deprecated
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Entity aliases: Alternative names for entities
CREATE TABLE entity_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    language TEXT,
    alias_type TEXT DEFAULT 'nickname',
    is_preferred BOOLEAN DEFAULT FALSE,
    UNIQUE(entity_id, alias)
);

-- Entity attributes: Key-value properties of entities
CREATE TABLE entity_attributes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    attr_key TEXT NOT NULL,
    attr_value JSONB NOT NULL,
    source_span_id UUID REFERENCES text_spans(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'pending',
    UNIQUE(entity_id, attr_key, source_span_id)
);

-- Entity mentions: References to entities in text
CREATE TABLE entity_mentions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    span_id UUID NOT NULL REFERENCES text_spans(id) ON DELETE CASCADE,
    mention_type TEXT DEFAULT 'explicit',
    confidence NUMERIC(5,4),
    is_verified BOOLEAN DEFAULT FALSE,
    verified_by TEXT,
    verified_at TIMESTAMPTZ,
    UNIQUE(entity_id, span_id)
);

-- Create indexes
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_name ON entities(canonical_name);
CREATE INDEX idx_entities_edition ON entities(edition_id);
CREATE INDEX idx_entities_work ON entities(work_id);
CREATE INDEX idx_entity_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX idx_entity_mentions_span ON entity_mentions(span_id);


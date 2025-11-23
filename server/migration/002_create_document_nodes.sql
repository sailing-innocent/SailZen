-- Document nodes: Tree structure for text organization
CREATE TABLE document_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_id UUID NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES document_nodes(id) ON DELETE CASCADE,
    node_type TEXT NOT NULL,
        -- volume/part/chapter/section/paragraph/sentence/title/extra
    sort_index INTEGER NOT NULL,
    depth SMALLINT NOT NULL,
    label TEXT,
    title TEXT,
    raw_text TEXT,
    text_checksum TEXT,
    word_count INTEGER,
    char_count INTEGER,
    start_char INTEGER,
    end_char INTEGER,
    path TEXT NOT NULL, -- materialized path like '0001.0003'
    status TEXT DEFAULT 'active', -- active | deprecated | superseded
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (edition_id, path)
);

-- Text spans: Character-level references within nodes
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

-- Create indexes for efficient queries
CREATE INDEX idx_document_nodes_edition ON document_nodes(edition_id);
CREATE INDEX idx_document_nodes_parent ON document_nodes(parent_id, sort_index);
CREATE INDEX idx_document_nodes_type ON document_nodes(edition_id, node_type);
CREATE INDEX idx_document_nodes_path ON document_nodes(edition_id, path);
CREATE INDEX idx_text_spans_node ON text_spans(node_id);
CREATE INDEX idx_text_spans_position ON text_spans(node_id, start_char);


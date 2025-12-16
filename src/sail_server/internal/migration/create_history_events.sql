-- Create history_events table
-- This table stores historical events with support for hierarchical structure and relationship tracking
-- Created: 2025-10-12

CREATE TABLE IF NOT EXISTS history_events (
    id SERIAL PRIMARY KEY,
    receive_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    title VARCHAR NOT NULL,
    description TEXT NOT NULL,
    rar_tags VARCHAR[] DEFAULT '{}',
    tags VARCHAR[] DEFAULT '{}',
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    related_events INTEGER[] DEFAULT '{}',
    parent_event INTEGER,
    details JSONB DEFAULT '{}'
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_history_events_parent ON history_events(parent_event);
CREATE INDEX IF NOT EXISTS idx_history_events_receive_time ON history_events(receive_time DESC);
CREATE INDEX IF NOT EXISTS idx_history_events_start_time ON history_events(start_time);
CREATE INDEX IF NOT EXISTS idx_history_events_end_time ON history_events(end_time);
CREATE INDEX IF NOT EXISTS idx_history_events_tags ON history_events USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_history_events_title ON history_events(title);

-- Add comments
COMMENT ON TABLE history_events IS '历史事件表，用于记录和组织历史事件';
COMMENT ON COLUMN history_events.id IS '主键ID';
COMMENT ON COLUMN history_events.receive_time IS '接收消息的时间，默认为创建时间';
COMMENT ON COLUMN history_events.title IS '事件标题（必填）';
COMMENT ON COLUMN history_events.description IS '事件描述（必填）';
COMMENT ON COLUMN history_events.rar_tags IS '手动标注的标签';
COMMENT ON COLUMN history_events.tags IS '机器处理后用于检索的标签';
COMMENT ON COLUMN history_events.start_time IS '估计的开始时间';
COMMENT ON COLUMN history_events.end_time IS '估计的结束时间';
COMMENT ON COLUMN history_events.related_events IS '相关事件的ID列表';
COMMENT ON COLUMN history_events.parent_event IS '父事件ID，用于构建事件层级结构';
COMMENT ON COLUMN history_events.details IS 'JSONB格式的详细信息，如相关人物、评论等';


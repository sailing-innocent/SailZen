-- Migration: 为 projects 表添加 timespan_id 列
-- Date: 2026-08-16
-- Author: sailing-innocent
-- Description: 关联项目到通用时间节点（TimeSpan），允许为空

ALTER TABLE projects ADD COLUMN IF NOT EXISTS timespan_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_projects_timespan_id ON projects(timespan_id);

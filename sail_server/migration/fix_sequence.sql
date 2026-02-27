-- 修复 unified_agent_tasks 表的序列
-- 如果表中有数据但序列当前值小于最大 ID，则需要修复

-- 检查表中最大 ID
SELECT MAX(id) FROM unified_agent_tasks;

-- 修复序列（如果需要）
-- 假设序列名为 unified_agent_tasks_id_seq
SELECT setval('unified_agent_tasks_id_seq', COALESCE((SELECT MAX(id) FROM unified_agent_tasks), 0) + 1, false);

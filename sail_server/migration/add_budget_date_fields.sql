-- 添加 budgets 表缺少的日期字段
-- 用于修复预算管理功能的表结构

-- 添加开始日期字段
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS start_date TIMESTAMP;

-- 添加结束日期字段
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS end_date TIMESTAMP;

-- 添加总金额字段（如果不存在）
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS total_amount VARCHAR(50) DEFAULT '0.0';

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_budgets_start_date ON budgets(start_date);
CREATE INDEX IF NOT EXISTS idx_budgets_end_date ON budgets(end_date);

-- 添加注释
COMMENT ON COLUMN budgets.start_date IS '预算开始日期';
COMMENT ON COLUMN budgets.end_date IS '预算结束日期';
COMMENT ON COLUMN budgets.total_amount IS '总预算金额（由子项汇总计算）';

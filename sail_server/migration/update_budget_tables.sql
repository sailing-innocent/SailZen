-- 预算管理系统 - 统一数据模型迁移脚本
-- 通用预算系统，支持所有业务场景

-- 1. 更新 budgets 表结构
-- 移除特化字段，使用通用结构
ALTER TABLE budgets DROP COLUMN IF EXISTS budget_type;
ALTER TABLE budgets DROP COLUMN IF EXISTS period_type;
ALTER TABLE budgets DROP COLUMN IF EXISTS category;

-- 确保必要字段存在
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS start_date TIMESTAMP;
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS end_date TIMESTAMP;
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS total_amount VARCHAR(50) DEFAULT '0.0';

-- 2. 更新 budget_items 表结构
-- 添加通用核心属性
ALTER TABLE budget_items ADD COLUMN IF NOT EXISTS direction INTEGER DEFAULT 0;    -- 0: 支出, 1: 收入
ALTER TABLE budget_items ADD COLUMN IF NOT EXISTS item_type INTEGER DEFAULT 0;     -- 0: 固定, 1: 周期性

-- 确保其他字段存在
ALTER TABLE budget_items ADD COLUMN IF NOT EXISTS is_refundable INTEGER DEFAULT 0;
ALTER TABLE budget_items ADD COLUMN IF NOT EXISTS refund_amount VARCHAR(50) DEFAULT '0.0';
ALTER TABLE budget_items ADD COLUMN IF NOT EXISTS period_count INTEGER DEFAULT 1;
ALTER TABLE budget_items ADD COLUMN IF NOT EXISTS current_period INTEGER DEFAULT 0;
ALTER TABLE budget_items ADD COLUMN IF NOT EXISTS status INTEGER DEFAULT 0;
ALTER TABLE budget_items ADD COLUMN IF NOT EXISTS due_date TIMESTAMP;

-- 3. 创建索引
CREATE INDEX IF NOT EXISTS idx_budget_items_budget_id ON budget_items(budget_id);
CREATE INDEX IF NOT EXISTS idx_budget_items_direction ON budget_items(direction);
CREATE INDEX IF NOT EXISTS idx_budget_items_item_type ON budget_items(item_type);
CREATE INDEX IF NOT EXISTS idx_budget_items_status ON budget_items(status);
CREATE INDEX IF NOT EXISTS idx_budgets_start_date ON budgets(start_date);
CREATE INDEX IF NOT EXISTS idx_budgets_end_date ON budgets(end_date);

-- 4. 添加注释
COMMENT ON COLUMN budget_items.direction IS '方向：0=支出, 1=收入';
COMMENT ON COLUMN budget_items.item_type IS '类型：0=固定金额, 1=周期性金额';
COMMENT ON COLUMN budget_items.amount IS '金额：固定型为总额，周期型为单期金额';
COMMENT ON COLUMN budget_items.period_count IS '期数：固定型为1，周期型为实际期数';
COMMENT ON COLUMN budget_items.is_refundable IS '是否可退还：0=否, 1=是';
COMMENT ON COLUMN budget_items.status IS '状态：0=待执行, 1=进行中, 2=已完成, 3=已退还';
COMMENT ON COLUMN budgets.total_amount IS '总金额：由子项汇总计算';

-- 预算管理系统扩展迁移脚本
-- 新增字段和表以支持：租房合同、购房合同、工资收入追踪

-- 1. 扩展 budgets 表，添加新字段
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS budget_type INTEGER DEFAULT 0;  -- 0: 支出, 1: 收入
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS period_type INTEGER DEFAULT 0;  -- 0: 一次性, 1: 月度, 2: 季度, 3: 年度
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS start_date TIMESTAMP;           -- 预算开始日期
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS end_date TIMESTAMP;             -- 预算结束日期
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS category VARCHAR(50);           -- 预算分类: rent, mortgage, salary, project

-- 2. 创建预算子项表
CREATE TABLE IF NOT EXISTS budget_items (
    id SERIAL PRIMARY KEY,
    budget_id INTEGER NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,           -- 子项名称：如"押金"、"月租"、"首付"、"利息"
    amount VARCHAR(50),                    -- 子项金额
    description TEXT,
    is_refundable INTEGER DEFAULT 0,       -- 是否可退还（0: 否, 1: 是）
    refund_amount VARCHAR(50) DEFAULT '0.0', -- 已退还金额
    status INTEGER DEFAULT 0,              -- 0: 待执行, 1: 进行中, 2: 已完成, 3: 已退还
    period_count INTEGER DEFAULT 1,        -- 期数（用于分期，如12期月租）
    current_period INTEGER DEFAULT 0,      -- 当前期数
    due_date TIMESTAMP,                    -- 到期日期
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. 创建索引
CREATE INDEX IF NOT EXISTS idx_budget_items_budget_id ON budget_items(budget_id);
CREATE INDEX IF NOT EXISTS idx_budgets_budget_type ON budgets(budget_type);
CREATE INDEX IF NOT EXISTS idx_budgets_category ON budgets(category);
CREATE INDEX IF NOT EXISTS idx_budgets_start_date ON budgets(start_date);
CREATE INDEX IF NOT EXISTS idx_budgets_end_date ON budgets(end_date);

-- 4. 添加注释
COMMENT ON COLUMN budgets.budget_type IS '预算类型：0=支出预算, 1=收入预算';
COMMENT ON COLUMN budgets.period_type IS '周期类型：0=一次性, 1=月度, 2=季度, 3=年度';
COMMENT ON COLUMN budgets.start_date IS '预算/合同开始日期';
COMMENT ON COLUMN budgets.end_date IS '预算/合同结束日期';
COMMENT ON COLUMN budgets.category IS '预算分类：rent=租房, mortgage=房贷, salary=工资, project=项目';

COMMENT ON TABLE budget_items IS '预算子项表，用于管理预算下的各个子项目';
COMMENT ON COLUMN budget_items.is_refundable IS '是否可退还：0=否, 1=是（如押金）';
COMMENT ON COLUMN budget_items.status IS '状态：0=待执行, 1=进行中, 2=已完成, 3=已退还';
COMMENT ON COLUMN budget_items.period_count IS '总期数（如12期月租）';
COMMENT ON COLUMN budget_items.current_period IS '当前已完成期数';

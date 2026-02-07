-- 添加预算方向字段
-- 用于区分收入预算和支出预算

-- 添加 direction 字段到 budgets 表
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS direction INTEGER DEFAULT 0;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_budgets_direction ON budgets(direction);

-- 添加注释
COMMENT ON COLUMN budgets.direction IS '预算方向：0=支出(EXPENSE), 1=收入(INCOME)';

-- 更新现有数据：根据预算标签判断方向
-- 工资、收入相关标签设为收入
UPDATE budgets 
SET direction = 1 
WHERE tags LIKE '%salary%' 
   OR tags LIKE '%income%' 
   OR tags LIKE '%工资%'
   OR tags LIKE '%收入%'
   OR name LIKE '%工资%'
   OR name LIKE '%收入%';

-- 其他默认为支出 (direction = 0)

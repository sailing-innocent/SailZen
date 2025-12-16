-- 步骤 1: 添加临时列
ALTER TABLE transactions ADD COLUMN htime_new TIMESTAMP;

-- 步骤 2: 将 Integer 时间戳转换为 TIMESTAMP 并填充新列
-- 如果是 Unix 时间戳（秒）
UPDATE transactions SET htime_new = to_timestamp(htime);

-- 如果是毫秒时间戳，使用以下语句替代上面的 UPDATE：
-- UPDATE transactions SET htime_new = to_timestamp(htime / 1000);

-- 步骤 3: 删除旧列
ALTER TABLE transactions DROP COLUMN htime;

-- 步骤 4: 重命名新列
ALTER TABLE transactions RENAME COLUMN htime_new TO htime;

-- 步骤 5: （可选）为新的 htime 列设置默认值
ALTER TABLE transactions ALTER COLUMN htime SET DEFAULT CURRENT_TIMESTAMP;
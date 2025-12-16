-- 将 weights 表的 htime 字段从 Integer 转换为 TIMESTAMP
-- 假设 Integer 存储的是 Unix 时间戳（秒）

-- 步骤 1: 添加临时列
ALTER TABLE weights ADD COLUMN htime_new TIMESTAMP;

-- 步骤 2: 将 Integer 时间戳转换为 TIMESTAMP 并填充新列
-- 如果是 Unix 时间戳（秒）
UPDATE weights SET htime_new = to_timestamp(htime);

-- 如果是毫秒时间戳，使用以下语句替代上面的 UPDATE：
-- UPDATE weights SET htime_new = to_timestamp(htime / 1000);

-- 步骤 3: 删除旧列
ALTER TABLE weights DROP COLUMN htime;

-- 步骤 4: 重命名新列
ALTER TABLE weights RENAME COLUMN htime_new TO htime;

-- 步骤 5: （可选）为新的 htime 列设置默认值
ALTER TABLE weights ALTER COLUMN htime SET DEFAULT CURRENT_TIMESTAMP;
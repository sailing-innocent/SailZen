-- 健康管理模块升级迁移
-- 创建时间: 2026-11-20
-- 说明: 为 Android 健康首页扩展运动结构化字段、用药、饮食、营养目标、作息目标

-- 1. 扩展 exercises 表：结构化运动字段
ALTER TABLE exercises
    ADD COLUMN IF NOT EXISTS exercise_type VARCHAR DEFAULT '',
    ADD COLUMN IF NOT EXISTS duration_minutes INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS calories INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS completed BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'health';

-- 2. 用药/保健品记录表
CREATE TABLE IF NOT EXISTS medications (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    dosage VARCHAR DEFAULT '',
    frequency VARCHAR DEFAULT 'daily',
    schedule_times JSONB DEFAULT '[]'::jsonb,
    htime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    planned_date DATE,
    taken BOOLEAN DEFAULT FALSE,
    taken_at TIMESTAMP NULL,
    note VARCHAR DEFAULT '',
    is_supplement BOOLEAN DEFAULT FALSE
);

-- 3. 饮食记录表
CREATE TABLE IF NOT EXISTS diet_logs (
    id SERIAL PRIMARY KEY,
    meal_type VARCHAR DEFAULT 'snack',
    htime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description VARCHAR DEFAULT '',
    photo_path VARCHAR NULL,
    calories FLOAT NULL,
    carbs FLOAT NULL,
    sugar FLOAT NULL,
    protein FLOAT NULL,
    fat FLOAT NULL,
    fiber FLOAT NULL,
    sodium FLOAT NULL,
    micronutrients JSONB DEFAULT '{}'::jsonb
);

-- 4. 每日营养目标表
CREATE TABLE IF NOT EXISTS nutrition_goals (
    id SERIAL PRIMARY KEY,
    date DATE UNIQUE,
    calories FLOAT NULL,
    carbs FLOAT NULL,
    sugar FLOAT NULL,
    protein FLOAT NULL,
    fat FLOAT NULL,
    fiber FLOAT NULL,
    sodium FLOAT NULL,
    micronutrients JSONB DEFAULT '{}'::jsonb
);

-- 5. 作息目标表
CREATE TABLE IF NOT EXISTS sleep_schedule_goals (
    id SERIAL PRIMARY KEY,
    date DATE UNIQUE,
    bed_time VARCHAR DEFAULT '23:00',
    wake_time VARCHAR DEFAULT '07:00',
    target_hours FLOAT DEFAULT 8.0
);

-- 6. 为 DietLog / Medication 常用查询建索引
CREATE INDEX IF NOT EXISTS idx_diet_logs_htime ON diet_logs(htime);
CREATE INDEX IF NOT EXISTS idx_diet_logs_meal_type ON diet_logs(meal_type);
CREATE INDEX IF NOT EXISTS idx_medications_planned_date ON medications(planned_date);
CREATE INDEX IF NOT EXISTS idx_medications_taken ON medications(taken);

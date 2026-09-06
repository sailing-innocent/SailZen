-- -*- coding: utf-8 -*-
-- @file 20260906_add_rhythm_is_default.sql
-- @brief rhythm_energy_profiles 补 is_default 列 + 修复错误实现的 mtime 触发器
-- @author sailing-innocent
-- @date 2026-09-06
-- @version 1.1
-- ---------------------------------

-- 背景：
-- 1) ORM 新增 RhythmEnergyProfile.is_default（Boolean, default=True, nullable=False）。
--    create_all 不会给已存在的表补列，因此需要本迁移。
--    存量数据回填规则：name = 'default' 的行视为未校准默认画像（is_default = true），
--    其余行（历史自定义画像）为 false。
-- 2) 历史遗留：生产 PG 库存在 5 个 trg_rhythm_*_mtime 触发器，统一调用
--    update_rhythm_mtime()（NEW.mtime = CURRENT_TIMESTAMP）。其余 4 张表均有
--    mtime 列，唯独 rhythm_energy_profiles 以 ORM 为口径使用 updated_at 列
--    （无 mtime），导致该表上任意 UPDATE 直接报错：
--      psycopg.errors.UndefinedColumn: 记录"new"没有字段"mtime"
--    且会连带阻断本迁移的回填 UPDATE。此处将其重建为指向 updated_at 的专用触发器。
--
-- 本脚本全部语句幂等，随每次启动反复执行均为安全空操作。

-- ---------------------------------------------------------------------------
-- 1. 修复错误实现的 mtime 触发器
-- ---------------------------------------------------------------------------

-- 删除本表上仍指向共用 update_rhythm_mtime() 的触发器（即错误实现）
DO $$
DECLARE
    t RECORD;
BEGIN
    FOR t IN
        SELECT tgname
        FROM pg_trigger
        WHERE tgrelid = 'rhythm_energy_profiles'::regclass
          AND NOT tgisinternal
          AND tgfoid = 'update_rhythm_mtime'::regproc
    LOOP
        -- 注意：脚本经 psycopg 执行，全文件禁止出现百分号占位符，故用 quote_ident 拼接而非 format 函数
        EXECUTE 'DROP TRIGGER ' || quote_ident(t.tgname) || ' ON rhythm_energy_profiles';
    END LOOP;
END $$;

-- 专用触发器函数：本表时间戳列为 updated_at（以 ORM metadata 为唯一口径）
CREATE OR REPLACE FUNCTION update_rhythm_energy_profile_mtime()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 重建触发器（仅在不存在时创建）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgrelid = 'rhythm_energy_profiles'::regclass
          AND NOT tgisinternal
          AND tgname = 'trg_rhythm_energy_profiles_mtime'
    ) THEN
        CREATE TRIGGER trg_rhythm_energy_profiles_mtime
        BEFORE UPDATE ON rhythm_energy_profiles
        FOR EACH ROW EXECUTE FUNCTION update_rhythm_energy_profile_mtime();
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 2. 补 is_default 列 + 回填存量数据
-- ---------------------------------------------------------------------------

-- 幂等加列（PG 9.6+ 支持 ADD COLUMN IF NOT EXISTS）
ALTER TABLE rhythm_energy_profiles
    ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT true;

-- 回填存量数据（仅 touch 需要变更的行，可反复执行）
UPDATE rhythm_energy_profiles
   SET is_default = (name = 'default')
 WHERE is_default IS DISTINCT FROM (name = 'default');

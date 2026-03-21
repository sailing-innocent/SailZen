import { openDatabaseSync, type SQLiteDatabase } from 'expo-sqlite';

const DB_NAME = 'sailzen.db';

// SQL statements to create tables (must be executed one at a time)
const CREATE_TABLES_SQL = [
  `CREATE TABLE IF NOT EXISTS weight_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    value REAL NOT NULL,
    record_time INTEGER NOT NULL,
    sync_status TEXT NOT NULL DEFAULT 'pending',
    server_id INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS exercise_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    duration INTEGER NOT NULL,
    calories INTEGER NOT NULL,
    record_time INTEGER NOT NULL,
    sync_status TEXT NOT NULL DEFAULT 'pending',
    server_id INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS weight_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_weight REAL NOT NULL,
    target_date INTEGER NOT NULL,
    start_weight REAL NOT NULL,
    start_date INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    sync_status TEXT NOT NULL DEFAULT 'pending',
    server_id INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS sync_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    last_sync_time INTEGER,
    pending_count INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL
  )`,
  `CREATE INDEX IF NOT EXISTS idx_weight_records_record_time ON weight_records(record_time)`,
  `CREATE INDEX IF NOT EXISTS idx_exercise_records_record_time ON exercise_records(record_time)`,
  `CREATE INDEX IF NOT EXISTS idx_weight_plans_is_active ON weight_plans(is_active)`,
];

/**
 * Initialize database tables
 */
export async function initializeTables(): Promise<void> {
  const db = openDatabaseSync(DB_NAME);
  
  try {
    for (const sql of CREATE_TABLES_SQL) {
      db.execSync(sql);
    }
    console.log('[DB] Tables initialized successfully');
  } catch (error) {
    console.error('[DB] Failed to initialize tables:', error);
    throw error;
  }
}

/**
 * Check if database is initialized
 */
export async function isDatabaseInitialized(): Promise<boolean> {
  try {
    const db = openDatabaseSync(DB_NAME);
    // Try to query sqlite_master to check if tables exist
    const result = db.execSync("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='sync_metadata'");
    return true;
  } catch (error) {
    return false;
  }
}

/**
 * Delete database file (useful for debugging/reset)
 */
export async function deleteDatabase(): Promise<void> {
  try {
    const db = openDatabaseSync(DB_NAME);
    db.closeSync();
    
    // On mobile, we need to clear the app's data to delete the database
    console.log('[DB] Database closed. Clear app data to reset.');
  } catch (error) {
    console.error('[DB] Failed to close database:', error);
  }
}

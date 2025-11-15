// SyncDatabase 会同步用户的本地修改并与后端交互的接口
import * as fs from 'fs'
import * as path from 'path'
import Database from 'better-sqlite3';

export interface Edition {
    id: string;
    work_id: string;
    title: string;
    version: string;
    local_path: string;
    last_pulled_at?: string;
    last_pushed_at?: string;
    remote_updated_at?: string;
    sync_enabled: boolean;
}

export interface NodeRecord {
    id: string;
    edition_id: string;
    file_path: string;
    title: string;
    node_type: string;
    parent_id: string | null;
    order_index: number;
    remote_updated_at?: string;
    sync_status: 'synced' | 'modified' | 'conflict' | 'pending';
    content_hash?: string;
};

export class SyncDatabase {
    private db: Database.Database;
    private dbPath: string;
    constructor(dbPath: string) {
        this.dbPath = dbPath;
        this.db = new Database(dbPath);
        this.db.pragma('foreign_keys = ON'); // Enable foreign keys constraint
        this.db.progma('journal_mode = WAL'); // set journal mode to WAL for better concurrency
    }
    // Run Migrations
    migrate(): void {
        try {
            const migrationsDir = path.join(__dirname, 'migrations');

            // Read and execute migration file
        } catch(error) {
            throw new Error(`Migration failed: ${error instanceof  Error ? error.message : String(error)}`);
        }
    }
    /**
     * Fallback schema creation
     */
};
import { sqliteTable, integer, real, text } from 'drizzle-orm/sqlite-core';

export const weightRecords = sqliteTable('weight_records', {
  id: integer('id').primaryKey(),
  value: real('value').notNull(),
  recordTime: integer('record_time', { mode: 'timestamp' }).notNull(),
  syncStatus: text('sync_status', { enum: ['synced', 'pending', 'error'] })
    .notNull()
    .default('pending'),
  serverId: integer('server_id'),
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
  updatedAt: integer('updated_at', { mode: 'timestamp' }).notNull(),
});

export const exerciseRecords = sqliteTable('exercise_records', {
  id: integer('id').primaryKey(),
  type: text('type', {
    enum: ['running', 'swimming', 'cycling', 'fitness', 'yoga', 'other'],
  }).notNull(),
  duration: integer('duration').notNull(), // in minutes
  calories: integer('calories').notNull(),
  recordTime: integer('record_time', { mode: 'timestamp' }).notNull(),
  syncStatus: text('sync_status', { enum: ['synced', 'pending', 'error'] })
    .notNull()
    .default('pending'),
  serverId: integer('server_id'),
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
  updatedAt: integer('updated_at', { mode: 'timestamp' }).notNull(),
});

export const weightPlans = sqliteTable('weight_plans', {
  id: integer('id').primaryKey(),
  targetWeight: real('target_weight').notNull(),
  targetDate: integer('target_date', { mode: 'timestamp' }).notNull(),
  startWeight: real('start_weight').notNull(),
  startDate: integer('start_date', { mode: 'timestamp' }).notNull(),
  isActive: integer('is_active', { mode: 'boolean' }).notNull().default(true),
  syncStatus: text('sync_status', { enum: ['synced', 'pending', 'error'] })
    .notNull()
    .default('pending'),
  serverId: integer('server_id'),
  createdAt: integer('created_at', { mode: 'timestamp' }).notNull(),
  updatedAt: integer('updated_at', { mode: 'timestamp' }).notNull(),
});

export const syncMetadata = sqliteTable('sync_metadata', {
  id: integer('id').primaryKey(),
  lastSyncTime: integer('last_sync_time', { mode: 'timestamp' }),
  pendingCount: integer('pending_count').notNull().default(0),
  updatedAt: integer('updated_at', { mode: 'timestamp' }).notNull(),
});

export type WeightRecord = typeof weightRecords.$inferSelect;
export type NewWeightRecord = typeof weightRecords.$inferInsert;

export type ExerciseRecord = typeof exerciseRecords.$inferSelect;
export type NewExerciseRecord = typeof exerciseRecords.$inferInsert;

export type WeightPlan = typeof weightPlans.$inferSelect;
export type NewWeightPlan = typeof weightPlans.$inferInsert;

export type SyncMetadata = typeof syncMetadata.$inferSelect;
export type NewSyncMetadata = typeof syncMetadata.$inferInsert;

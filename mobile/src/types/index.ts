export type WeightRecord = {
  id: number;
  value: number;
  recordTime: Date;
  syncStatus: 'synced' | 'pending' | 'error';
  serverId?: number;
  createdAt: Date;
  updatedAt: Date;
};

export type WeightRecordCreate = Omit<
  WeightRecord,
  'id' | 'serverId' | 'createdAt' | 'updatedAt' | 'syncStatus'
>;

export type ExerciseType = 'running' | 'swimming' | 'cycling' | 'fitness' | 'yoga' | 'other';

export type ExerciseRecord = {
  id: number;
  type: ExerciseType;
  duration: number; // in minutes
  calories: number;
  recordTime: Date;
  syncStatus: 'synced' | 'pending' | 'error';
  serverId?: number;
  createdAt: Date;
  updatedAt: Date;
};

export type ExerciseRecordCreate = Omit<
  ExerciseRecord,
  'id' | 'serverId' | 'createdAt' | 'updatedAt' | 'syncStatus'
>;

export type WeightPlan = {
  id: number;
  targetWeight: number;
  targetDate: Date;
  startWeight: number;
  startDate: Date;
  isActive: boolean;
  syncStatus: 'synced' | 'pending' | 'error';
  serverId?: number;
  createdAt: Date;
  updatedAt: Date;
};

export type WeightPlanCreate = Omit<
  WeightPlan,
  'id' | 'serverId' | 'createdAt' | 'updatedAt' | 'syncStatus' | 'isActive'
> & { isActive?: boolean };

export type SyncStatus = 'synced' | 'pending' | 'error';

export type SyncMetadata = {
  id: number;
  lastSyncTime?: Date;
  pendingCount: number;
  updatedAt: Date;
};

// API Types matching backend DTOs
export type WeightResponse = {
  id: number;
  value: number;
  record_time: number; // timestamp
};

export type WeightCreateRequest = {
  value: number;
  record_time: number;
};

export type ExerciseResponse = {
  id: number;
  type: string;
  duration: number;
  calories: number;
  record_time: number;
};

export type ExerciseCreateRequest = {
  type: string;
  duration: number;
  calories: number;
  record_time: number;
};

export type WeightPlanResponse = {
  id: number;
  target_weight: number;
  target_date: number;
  start_weight: number;
  start_date: number;
};

export type WeightPlanCreateRequest = {
  target_weight: number;
  target_date: number;
  start_weight: number;
};

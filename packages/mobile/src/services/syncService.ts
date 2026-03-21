import { db } from '../db';
import { weightRecords, exerciseRecords, weightPlans, syncMetadata } from '../db/schema';
import { eq } from 'drizzle-orm';
import { apiClient } from '../api/client';
import { useSyncStore } from '../stores/syncStore';

export interface SyncResult {
  success: boolean;
  uploaded: {
    weights: number;
    exercises: number;
    plans: number;
  };
  downloaded: {
    weights: number;
    exercises: number;
    plans: number;
  };
  errors: string[];
}

/**
 * Service for handling data synchronization between local SQLite and backend API
 */
class SyncService {
  /**
   * Sync all pending records to server and download new records
   */
  async syncAll(onProgress?: (progress: number) => void): Promise<SyncResult> {
    const result: SyncResult = {
      success: true,
      uploaded: { weights: 0, exercises: 0, plans: 0 },
      downloaded: { weights: 0, exercises: 0, plans: 0 },
      errors: [],
    };

    const { setSyncing, setLastSyncTime, setSyncError, setPendingCount } = useSyncStore.getState();
    
    try {
      setSyncing(true);
      setSyncError(null);
      
      // Phase 1: Upload pending records
      console.log('[Sync] Phase 1: Uploading pending records...');
      await this.uploadPendingRecords(result, onProgress);
      
      // Phase 2: Download records from server
      console.log('[Sync] Phase 2: Downloading records from server...');
      await this.downloadFromServer(result, onProgress);

      // Update sync metadata
      await this.updateSyncMetadata();
      
      const pendingCount = await this.getPendingCount();
      setPendingCount(pendingCount);
      setLastSyncTime(new Date());
      
      console.log('[Sync] Sync completed:', result);
      return result;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '同步失败';
      console.error('[Sync] Sync failed:', error);
      setSyncError(errorMessage);
      result.success = false;
      result.errors.push(errorMessage);
      return result;
    } finally {
      setSyncing(false);
      onProgress?.(100);
    }
  }

  /**
   * Upload pending records to server
   */
  private async uploadPendingRecords(result: SyncResult, onProgress?: (progress: number) => void): Promise<void> {
    const pendingWeights = await db.select().from(weightRecords).where(eq(weightRecords.syncStatus, 'pending'));
    const pendingExercises = await db.select().from(exerciseRecords).where(eq(exerciseRecords.syncStatus, 'pending'));
    const pendingPlans = await db.select().from(weightPlans).where(eq(weightPlans.syncStatus, 'pending'));
    
    const totalPending = pendingWeights.length + pendingExercises.length + pendingPlans.length;
    let processed = 0;

    if (totalPending === 0) {
      console.log('[Sync] No pending records to upload');
      return;
    }

    console.log(`[Sync] Uploading ${totalPending} pending records...`);

    for (const record of pendingWeights) {
      try {
        const response = await apiClient.createWeight({
          value: record.value,
          record_time: record.recordTime.getTime(),
        });

        await db.update(weightRecords)
          .set({
            syncStatus: 'synced',
            serverId: response.id,
            updatedAt: new Date(),
          })
          .where(eq(weightRecords.id, record.id));

        result.uploaded.weights++;
        processed++;
        onProgress?.(Math.round((processed / totalPending) * 50));
      } catch (error) {
        console.error('[Sync] Failed to upload weight record:', error);
        result.errors.push(`Weight record ${record.id}: ${error instanceof Error ? error.message : 'Unknown error'}`);
        await db.update(weightRecords)
          .set({ syncStatus: 'error' })
          .where(eq(weightRecords.id, record.id));
      }
    }

    for (const record of pendingExercises) {
      try {
        const response = await apiClient.createExercise({
          type: record.type,
          duration: record.duration,
          calories: record.calories,
          record_time: record.recordTime.getTime(),
        });

        await db.update(exerciseRecords)
          .set({
            syncStatus: 'synced',
            serverId: response.id,
            updatedAt: new Date(),
          })
          .where(eq(exerciseRecords.id, record.id));

        result.uploaded.exercises++;
        processed++;
        onProgress?.(Math.round((processed / totalPending) * 50));
      } catch (error) {
        console.error('[Sync] Failed to upload exercise record:', error);
        result.errors.push(`Exercise record ${record.id}: ${error instanceof Error ? error.message : 'Unknown error'}`);
        await db.update(exerciseRecords)
          .set({ syncStatus: 'error' })
          .where(eq(exerciseRecords.id, record.id));
      }
    }

    for (const record of pendingPlans) {
      try {
        const response = await apiClient.createWeightPlan({
          target_weight: record.targetWeight,
          target_date: record.targetDate.getTime(),
          start_weight: record.startWeight,
        });

        await db.update(weightPlans)
          .set({
            syncStatus: 'synced',
            serverId: response.id,
            updatedAt: new Date(),
          })
          .where(eq(weightPlans.id, record.id));

        result.uploaded.plans++;
        processed++;
        onProgress?.(Math.round((processed / totalPending) * 50));
      } catch (error) {
        console.error('[Sync] Failed to upload weight plan:', error);
        result.errors.push(`Weight plan ${record.id}: ${error instanceof Error ? error.message : 'Unknown error'}`);
        await db.update(weightPlans)
          .set({ syncStatus: 'error' })
          .where(eq(weightPlans.id, record.id));
      }
    }
  }

  /**
   * Download records from server and merge with local data
   */
  private async downloadFromServer(result: SyncResult, onProgress?: (progress: number) => void): Promise<void> {
    try {
      console.log('[Sync] Downloading weight records...');
      const serverWeights = await apiClient.getWeightList({ limit: 1000 });
      
      for (const serverWeight of serverWeights) {
        try {
          const localWeight = await db.select()
            .from(weightRecords)
            .where(eq(weightRecords.serverId, serverWeight.id))
            .limit(1);

          if (localWeight.length === 0) {
            await db.insert(weightRecords).values({
              value: serverWeight.value,
              recordTime: new Date(serverWeight.record_time),
              syncStatus: 'synced',
              serverId: serverWeight.id,
              createdAt: new Date(serverWeight.created_at),
              updatedAt: new Date(serverWeight.updated_at),
            });
            result.downloaded.weights++;
          } else {
            const serverTime = new Date(serverWeight.updated_at).getTime();
            const localTime = localWeight[0].updatedAt.getTime();
            
            if (serverTime > localTime) {
              await db.update(weightRecords)
                .set({
                  value: serverWeight.value,
                  recordTime: new Date(serverWeight.record_time),
                  syncStatus: 'synced',
                  updatedAt: new Date(serverWeight.updated_at),
                })
                .where(eq(weightRecords.id, localWeight[0].id));
            }
          }
        } catch (error) {
          console.error(`[Sync] Failed to process weight record ${serverWeight.id}:`, error);
        }
      }

      console.log('[Sync] Downloading exercise records...');
      const serverExercises = await apiClient.getExerciseList({ limit: 1000 });
      
      for (const serverExercise of serverExercises) {
        try {
          const localExercise = await db.select()
            .from(exerciseRecords)
            .where(eq(exerciseRecords.serverId, serverExercise.id))
            .limit(1);

          if (localExercise.length === 0) {
            await db.insert(exerciseRecords).values({
              type: serverExercise.type,
              duration: serverExercise.duration,
              calories: serverExercise.calories,
              recordTime: new Date(serverExercise.record_time),
              syncStatus: 'synced',
              serverId: serverExercise.id,
              createdAt: new Date(serverExercise.created_at),
              updatedAt: new Date(serverExercise.updated_at),
            });
            result.downloaded.exercises++;
          } else {
            const serverTime = new Date(serverExercise.updated_at).getTime();
            const localTime = localExercise[0].updatedAt.getTime();
            
            if (serverTime > localTime) {
              await db.update(exerciseRecords)
                .set({
                  type: serverExercise.type,
                  duration: serverExercise.duration,
                  calories: serverExercise.calories,
                  recordTime: new Date(serverExercise.record_time),
                  syncStatus: 'synced',
                  updatedAt: new Date(serverExercise.updated_at),
                })
                .where(eq(exerciseRecords.id, localExercise[0].id));
            }
          }
        } catch (error) {
          console.error(`[Sync] Failed to process exercise record ${serverExercise.id}:`, error);
        }
      }

      console.log('[Sync] Downloading weight plan...');
      try {
        const serverPlan = await apiClient.getWeightPlan();
        if (serverPlan) {
          const localPlan = await db.select()
            .from(weightPlans)
            .where(eq(weightPlans.serverId, serverPlan.id))
            .limit(1);

          if (localPlan.length === 0) {
            await db.insert(weightPlans).values({
              targetWeight: serverPlan.target_weight,
              targetDate: new Date(serverPlan.target_date),
              startWeight: serverPlan.start_weight,
              startDate: new Date(serverPlan.start_date),
              isActive: true,
              syncStatus: 'synced',
              serverId: serverPlan.id,
              createdAt: new Date(serverPlan.created_at),
              updatedAt: new Date(serverPlan.updated_at),
            });
            result.downloaded.plans++;
          } else {
            const serverTime = new Date(serverPlan.updated_at).getTime();
            const localTime = localPlan[0].updatedAt.getTime();
            
            if (serverTime > localTime) {
              await db.update(weightPlans)
                .set({
                  targetWeight: serverPlan.target_weight,
                  targetDate: new Date(serverPlan.target_date),
                  startWeight: serverPlan.start_weight,
                  startDate: new Date(serverPlan.start_date),
                  syncStatus: 'synced',
                  updatedAt: new Date(serverPlan.updated_at),
                })
                .where(eq(weightPlans.id, localPlan[0].id));
            }
          }
        }
      } catch (error) {
        console.log('[Sync] No weight plan on server or error fetching:', error);
      }

      onProgress?.(75);
    } catch (error) {
      console.error('[Sync] Download failed:', error);
      throw error;
    }
  }

  private async updateSyncMetadata(): Promise<void> {
    const pendingCount = await this.getPendingCount();
    
    const metadata = await db.select().from(syncMetadata).limit(1);
    if (metadata.length === 0) {
      await db.insert(syncMetadata).values({
        lastSyncTime: new Date(),
        pendingCount,
        updatedAt: new Date(),
      });
    } else {
      await db.update(syncMetadata)
        .set({
          lastSyncTime: new Date(),
          pendingCount,
          updatedAt: new Date(),
        })
        .where(eq(syncMetadata.id, metadata[0].id));
    }
  }

  async getPendingCount(): Promise<number> {
    try {
      const pendingWeights = await db.$count(weightRecords, eq(weightRecords.syncStatus, 'pending'));
      const pendingExercises = await db.$count(exerciseRecords, eq(exerciseRecords.syncStatus, 'pending'));
      const pendingPlans = await db.$count(weightPlans, eq(weightPlans.syncStatus, 'pending'));
      
      return pendingWeights + pendingExercises + pendingPlans;
    } catch (error) {
      console.warn('[SyncService] Database not ready yet:', error);
      return 0;
    }
  }

  async hasPendingChanges(): Promise<boolean> {
    const count = await this.getPendingCount();
    return count > 0;
  }

  async checkApiConnection(): Promise<boolean> {
    return await apiClient.healthCheck();
  }
}

export const syncService = new SyncService();

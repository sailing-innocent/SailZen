import { useCallback } from 'react';
import { db } from '../db';
import { weightRecords, exerciseRecords, weightPlans, syncMetadata } from '../db/schema';
import { eq, and } from 'drizzle-orm';
import { apiClient } from '../api/client';
import { useSyncStore } from '../stores/syncStore';

/**
 * Service for handling data synchronization between local SQLite and backend API
 */
class SyncService {
  /**
   * Sync all pending records to server and download new records
   */
  async syncAll(onProgress?: (progress: number) => void): Promise<void> {
    const { setSyncing, setLastSyncTime, setSyncError, setPendingCount } = useSyncStore.getState();
    
    try {
      setSyncing(true);
      setSyncError(null);
      
      let totalOperations = 0;
      let completedOperations = 0;

      // Count pending records
      const pendingWeights = await db.select().from(weightRecords).where(eq(weightRecords.syncStatus, 'pending'));
      const pendingExercises = await db.select().from(exerciseRecords).where(eq(exerciseRecords.syncStatus, 'pending'));
      const pendingPlans = await db.select().from(weightPlans).where(eq(weightPlans.syncStatus, 'pending'));
      
      totalOperations = pendingWeights.length + pendingExercises.length + pendingPlans.length + 3; // +3 for download operations

      // Upload pending weight records
      for (const record of pendingWeights) {
        try {
          const response = await apiClient.createWeight({
            value: record.value,
            record_time: record.recordTime.getTime(),
          });

          // Update local record with server ID and synced status
          await db.update(weightRecords)
            .set({
              syncStatus: 'synced',
              serverId: response.id,
              updatedAt: new Date(),
            })
            .where(eq(weightRecords.id, record.id));

          completedOperations++;
          onProgress?.(Math.round((completedOperations / totalOperations) * 100));
        } catch (error) {
          console.error('Failed to sync weight record:', error);
          await db.update(weightRecords)
            .set({ syncStatus: 'error' })
            .where(eq(weightRecords.id, record.id));
        }
      }

      // Upload pending exercise records
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

          completedOperations++;
          onProgress?.(Math.round((completedOperations / totalOperations) * 100));
        } catch (error) {
          console.error('Failed to sync exercise record:', error);
          await db.update(exerciseRecords)
            .set({ syncStatus: 'error' })
            .where(eq(exerciseRecords.id, record.id));
        }
      }

      // Upload pending weight plans
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

          completedOperations++;
          onProgress?.(Math.round((completedOperations / totalOperations) * 100));
        } catch (error) {
          console.error('Failed to sync weight plan:', error);
          await db.update(weightPlans)
            .set({ syncStatus: 'error' })
            .where(eq(weightPlans.id, record.id));
        }
      }

      // Download records from server (last-write-wins strategy)
      await this.downloadFromServer();
      completedOperations += 3;
      onProgress?.(100);

      // Update sync metadata
      await this.updateSyncMetadata();
      
      setLastSyncTime(new Date());
      setPendingCount(await this.getPendingCount());
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '同步失败';
      setSyncError(errorMessage);
      throw error;
    } finally {
      setSyncing(false);
    }
  }

  /**
   * Download records from server
   */
  private async downloadFromServer(): Promise<void> {
    // Get last sync time
    const metadata = await db.select().from(syncMetadata).limit(1);
    const lastSync = metadata[0]?.lastSyncTime;

    // Fetch weights from server
    try {
      const serverWeights = await apiClient.getWeightList({ limit: 1000 });
      for (const serverWeight of serverWeights) {
        const localWeight = await db.select()
          .from(weightRecords)
          .where(eq(weightRecords.serverId, serverWeight.id))
          .limit(1);

        if (localWeight.length === 0) {
          // New record from server - insert locally
          await db.insert(weightRecords).values({
            value: serverWeight.value,
            recordTime: new Date(serverWeight.record_time),
            syncStatus: 'synced',
            serverId: serverWeight.id,
            createdAt: new Date(serverWeight.created_at),
            updatedAt: new Date(serverWeight.updated_at),
          });
        } else {
          // Existing record - check if server is newer (last-write-wins)
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
      }
    } catch (error) {
      console.error('Failed to download weights:', error);
    }

    // Fetch exercises from server
    try {
      const serverExercises = await apiClient.getExerciseList({ limit: 1000 });
      for (const serverExercise of serverExercises) {
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
      }
    } catch (error) {
      console.error('Failed to download exercises:', error);
    }
  }

  /**
   * Update sync metadata
   */
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

  /**
   * Get count of pending records
   */
  async getPendingCount(): Promise<number> {
    const pendingWeights = await db.$count(weightRecords, eq(weightRecords.syncStatus, 'pending'));
    const pendingExercises = await db.$count(exerciseRecords, eq(exerciseRecords.syncStatus, 'pending'));
    const pendingPlans = await db.$count(weightPlans, eq(weightPlans.syncStatus, 'pending'));
    
    return pendingWeights + pendingExercises + pendingPlans;
  }

  /**
   * Check if there are pending changes
   */
  async hasPendingChanges(): Promise<boolean> {
    const count = await this.getPendingCount();
    return count > 0;
  }
}

export const syncService = new SyncService();

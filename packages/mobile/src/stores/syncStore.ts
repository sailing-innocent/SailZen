import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo from '@react-native-community/netinfo';
import { db, syncMetadata, weightRecords, exerciseRecords, weightPlans } from '../db';
import { eq } from 'drizzle-orm';
import { apiClient } from '../api/client';
import { useWeightStore } from './weightStore';
import { useExerciseStore } from './exerciseStore';
import { useWeightPlanStore } from './weightPlanStore';

interface SyncState {
  lastSyncTime: Date | null;
  pendingCount: number;
  isSyncing: boolean;
  isOnline: boolean;
  error: string | null;
  // Actions
  sync: () => Promise<void>;
  updatePendingCount: () => Promise<void>;
  checkNetworkStatus: () => Promise<void>;
  clearError: () => void;
  // Setters for external services
  setSyncing: (isSyncing: boolean) => void;
  setLastSyncTime: (time: Date) => void;
  setSyncError: (error: string | null) => void;
  setPendingCount: (count: number) => void;
}

export const useSyncStore = create<SyncState>()(
  persist(
    (set, get) => ({
      lastSyncTime: null,
      pendingCount: 0,
      isSyncing: false,
      isOnline: true,
      error: null,

      setSyncing: (isSyncing) => set({ isSyncing }),
      setLastSyncTime: (lastSyncTime) => set({ lastSyncTime }),
      setSyncError: (error) => set({ error }),
      setPendingCount: (pendingCount) => set({ pendingCount }),

      sync: async () => {
        if (get().isSyncing) return;

        set({ isSyncing: true, error: null });

        try {
          // Check network
          const netInfo = await NetInfo.fetch();
          if (!netInfo.isConnected) {
            set({ isSyncing: false, isOnline: false });
            return;
          }

          // Get pending records from all stores
          const weightPending = useWeightStore.getState().getPendingRecords();
          const exercisePending = useExerciseStore.getState().getPendingRecords();
          const planPending = useWeightPlanStore.getState().getPendingPlans();

          // Upload weight records
          for (const record of weightPending) {
            try {
              const response = await apiClient.createWeight({
                value: record.value,
                record_time: record.recordTime.getTime(),
              });

              if (response) {
                await db
                  .update(weightRecords)
                  .set({
                    syncStatus: 'synced',
                    serverId: response.id,
                  })
                  .where(eq(weightRecords.id, record.id));
              }
            } catch (error) {
              console.error('Failed to sync weight record:', error);
            }
          }

          // Upload exercise records
          for (const record of exercisePending) {
            try {
              const response = await apiClient.createExercise({
                type: record.type,
                duration: record.duration,
                calories: record.calories,
                record_time: record.recordTime.getTime(),
              });

              if (response) {
                await db
                  .update(exerciseRecords)
                  .set({
                    syncStatus: 'synced',
                    serverId: response.id,
                  })
                  .where(eq(exerciseRecords.id, record.id));
              }
            } catch (error) {
              console.error('Failed to sync exercise record:', error);
            }
          }

          // Upload weight plans
          for (const plan of planPending) {
            try {
              const response = await apiClient.createWeightPlan({
                target_weight: plan.targetWeight,
                target_date: plan.targetDate.getTime(),
                start_weight: plan.startWeight,
              });

              if (response) {
                await db
                  .update(weightPlans)
                  .set({
                    syncStatus: 'synced',
                    serverId: response.id,
                  })
                  .where(eq(weightPlans.id, plan.id));
              }
            } catch (error) {
              console.error('Failed to sync weight plan:', error);
            }
          }

          // Download server records
          await get().downloadFromServer();

          // Update sync metadata
          const now = new Date();
          await db
            .insert(syncMetadata)
            .values({
              lastSyncTime: now,
              pendingCount: 0,
              updatedAt: now,
            })
            .onConflictDoUpdate({
              target: syncMetadata.id,
              set: {
                lastSyncTime: now,
                pendingCount: 0,
                updatedAt: now,
              },
            });

          // Refresh all stores
          await useWeightStore.getState().fetchRecords();
          await useExerciseStore.getState().fetchRecords();
          await useWeightPlanStore.getState().fetchPlans();

          set({
            lastSyncTime: now,
            pendingCount: 0,
            isSyncing: false,
            isOnline: true,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Sync failed',
            isSyncing: false,
          });
        }
      },

      downloadFromServer: async () => {
        try {
          // Download weight records
          const weightList = await apiClient.getWeightList({ limit: 100 });
          // TODO: Merge with local records, handle conflicts

          // Download exercise records
          const exerciseList = await apiClient.getExerciseList({ limit: 100 });
          // TODO: Merge with local records

          // Download weight plan
          const plan = await apiClient.getWeightPlan();
          // TODO: Update local plan if different
        } catch (error) {
          console.error('Failed to download from server:', error);
        }
      },

      updatePendingCount: async () => {
        try {
          const weightPending = useWeightStore.getState().getPendingRecords().length;
          const exercisePending = useExerciseStore.getState().getPendingRecords().length;
          const planPending = useWeightPlanStore.getState().getPendingPlans().length;

          const total = weightPending + exercisePending + planPending;

          await db
            .insert(syncMetadata)
            .values({
              pendingCount: total,
              updatedAt: new Date(),
            })
            .onConflictDoUpdate({
              target: syncMetadata.id,
              set: {
                pendingCount: total,
                updatedAt: new Date(),
              },
            });

          set({ pendingCount: total });
        } catch (error) {
          console.error('Failed to update pending count:', error);
        }
      },

      checkNetworkStatus: async () => {
        const netInfo = await NetInfo.fetch();
        set({ isOnline: netInfo.isConnected ?? false });
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'sync-storage',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({
        lastSyncTime: state.lastSyncTime,
        pendingCount: state.pendingCount,
      }),
    }
  )
);

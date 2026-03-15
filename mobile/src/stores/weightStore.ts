import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  WeightRecord,
  WeightRecordCreate,
  SyncStatus,
} from '../types';
import { db, weightRecords } from '../db';
import { eq, desc, sql } from 'drizzle-orm';

interface WeightState {
  records: WeightRecord[];
  isLoading: boolean;
  error: string | null;
  // Actions
  fetchRecords: (limit?: number) => Promise<void>;
  addRecord: (data: WeightRecordCreate) => Promise<void>;
  updateRecord: (id: number, data: Partial<WeightRecordCreate>) => Promise<void>;
  deleteRecord: (id: number) => Promise<void>;
  getPendingRecords: () => WeightRecord[];
  clearError: () => void;
}

export const useWeightStore = create<WeightState>()(
  persist(
    (set, get) => ({
      records: [],
      isLoading: false,
      error: null,

      fetchRecords: async (limit = 50) => {
        set({ isLoading: true, error: null });
        try {
          const results = await db
            .select()
            .from(weightRecords)
            .orderBy(desc(weightRecords.recordTime))
            .limit(limit);

          const formattedRecords: WeightRecord[] = results.map((r) => ({
            ...r,
            recordTime: new Date(r.recordTime),
            createdAt: new Date(r.createdAt),
            updatedAt: new Date(r.updatedAt),
            syncStatus: r.syncStatus as SyncStatus,
          }));

          set({ records: formattedRecords, isLoading: false });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to fetch records',
            isLoading: false,
          });
        }
      },

      addRecord: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const now = new Date();
          const [result] = await db
            .insert(weightRecords)
            .values({
              value: data.value,
              recordTime: data.recordTime,
              syncStatus: 'pending',
              createdAt: now,
              updatedAt: now,
            })
            .returning();

          const newRecord: WeightRecord = {
            ...result,
            recordTime: new Date(result.recordTime),
            createdAt: new Date(result.createdAt),
            updatedAt: new Date(result.updatedAt),
            syncStatus: result.syncStatus as SyncStatus,
          };

          set((state) => ({
            records: [newRecord, ...state.records],
            isLoading: false,
          }));
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to add record',
            isLoading: false,
          });
        }
      },

      updateRecord: async (id, data) => {
        set({ isLoading: true, error: null });
        try {
          const now = new Date();
          const [result] = await db
            .update(weightRecords)
            .set({
              ...(data.value !== undefined && { value: data.value }),
              ...(data.recordTime !== undefined && { recordTime: data.recordTime }),
              syncStatus: 'pending',
              updatedAt: now,
            })
            .where(eq(weightRecords.id, id))
            .returning();

          const updatedRecord: WeightRecord = {
            ...result,
            recordTime: new Date(result.recordTime),
            createdAt: new Date(result.createdAt),
            updatedAt: new Date(result.updatedAt),
            syncStatus: result.syncStatus as SyncStatus,
          };

          set((state) => ({
            records: state.records.map((r) => (r.id === id ? updatedRecord : r)),
            isLoading: false,
          }));
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to update record',
            isLoading: false,
          });
        }
      },

      deleteRecord: async (id) => {
        set({ isLoading: true, error: null });
        try {
          await db.delete(weightRecords).where(eq(weightRecords.id, id));

          set((state) => ({
            records: state.records.filter((r) => r.id !== id),
            isLoading: false,
          }));
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to delete record',
            isLoading: false,
          });
        }
      },

      getPendingRecords: () => {
        return get().records.filter((r) => r.syncStatus === 'pending');
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'weight-storage',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({ records: state.records }),
    }
  )
);

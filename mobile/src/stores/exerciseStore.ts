import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { ExerciseRecord, ExerciseRecordCreate, SyncStatus } from '../types';
import { db, exerciseRecords } from '../db';
import { eq, desc } from 'drizzle-orm';

interface ExerciseState {
  records: ExerciseRecord[];
  isLoading: boolean;
  error: string | null;
  // Actions
  fetchRecords: (limit?: number) => Promise<void>;
  addRecord: (data: ExerciseRecordCreate) => Promise<void>;
  updateRecord: (id: number, data: Partial<ExerciseRecordCreate>) => Promise<void>;
  deleteRecord: (id: number) => Promise<void>;
  getPendingRecords: () => ExerciseRecord[];
  clearError: () => void;
}

export const useExerciseStore = create<ExerciseState>()(
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
            .from(exerciseRecords)
            .orderBy(desc(exerciseRecords.recordTime))
            .limit(limit);

          const formattedRecords: ExerciseRecord[] = results.map((r) => ({
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
            .insert(exerciseRecords)
            .values({
              type: data.type,
              duration: data.duration,
              calories: data.calories,
              recordTime: data.recordTime,
              syncStatus: 'pending',
              createdAt: now,
              updatedAt: now,
            })
            .returning();

          const newRecord: ExerciseRecord = {
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
            .update(exerciseRecords)
            .set({
              ...(data.type !== undefined && { type: data.type }),
              ...(data.duration !== undefined && { duration: data.duration }),
              ...(data.calories !== undefined && { calories: data.calories }),
              ...(data.recordTime !== undefined && { recordTime: data.recordTime }),
              syncStatus: 'pending',
              updatedAt: now,
            })
            .where(eq(exerciseRecords.id, id))
            .returning();

          const updatedRecord: ExerciseRecord = {
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
          await db.delete(exerciseRecords).where(eq(exerciseRecords.id, id));

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
      name: 'exercise-storage',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({ records: state.records }),
    }
  )
);

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { WeightPlan, WeightPlanCreate, SyncStatus } from '../types';
import { db, weightPlans } from '../db';
import { eq, desc } from 'drizzle-orm';

interface WeightPlanState {
  plans: WeightPlan[];
  activePlan: WeightPlan | null;
  isLoading: boolean;
  error: string | null;
  // Actions
  fetchPlans: () => Promise<void>;
  addPlan: (data: WeightPlanCreate) => Promise<void>;
  updatePlan: (id: number, data: Partial<WeightPlanCreate>) => Promise<void>;
  deletePlan: (id: number) => Promise<void>;
  setActivePlan: (id: number | null) => Promise<void>;
  getActivePlan: () => WeightPlan | null;
  getPendingPlans: () => WeightPlan[];
  clearError: () => void;
}

export const useWeightPlanStore = create<WeightPlanState>()(
  persist(
    (set, get) => ({
      plans: [],
      activePlan: null,
      isLoading: false,
      error: null,

      fetchPlans: async () => {
        set({ isLoading: true, error: null });
        try {
          const results = await db
            .select()
            .from(weightPlans)
            .orderBy(desc(weightPlans.createdAt));

          const formattedPlans: WeightPlan[] = results.map((p) => ({
            ...p,
            targetDate: new Date(p.targetDate),
            startDate: new Date(p.startDate),
            createdAt: new Date(p.createdAt),
            updatedAt: new Date(p.updatedAt),
            syncStatus: p.syncStatus as SyncStatus,
          }));

          const activePlan = formattedPlans.find((p) => p.isActive) || null;

          set({ plans: formattedPlans, activePlan, isLoading: false });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to fetch plans',
            isLoading: false,
          });
        }
      },

      addPlan: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const now = new Date();
          
          // Deactivate existing active plan
          await db
            .update(weightPlans)
            .set({ isActive: false })
            .where(eq(weightPlans.isActive, true));

          const [result] = await db
            .insert(weightPlans)
            .values({
              targetWeight: data.targetWeight,
              targetDate: data.targetDate,
              startWeight: data.startWeight,
              startDate: data.startDate,
              isActive: data.isActive ?? true,
              syncStatus: 'pending',
              createdAt: now,
              updatedAt: now,
            })
            .returning();

          const newPlan: WeightPlan = {
            ...result,
            targetDate: new Date(result.targetDate),
            startDate: new Date(result.startDate),
            createdAt: new Date(result.createdAt),
            updatedAt: new Date(result.updatedAt),
            syncStatus: result.syncStatus as SyncStatus,
          };

          set((state) => ({
            plans: [newPlan, ...state.plans.map((p) => ({ ...p, isActive: false }))],
            activePlan: newPlan,
            isLoading: false,
          }));
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to add plan',
            isLoading: false,
          });
        }
      },

      updatePlan: async (id, data) => {
        set({ isLoading: true, error: null });
        try {
          const now = new Date();
          const [result] = await db
            .update(weightPlans)
            .set({
              ...(data.targetWeight !== undefined && { targetWeight: data.targetWeight }),
              ...(data.targetDate !== undefined && { targetDate: data.targetDate }),
              ...(data.startWeight !== undefined && { startWeight: data.startWeight }),
              ...(data.startDate !== undefined && { startDate: data.startDate }),
              ...(data.isActive !== undefined && { isActive: data.isActive }),
              syncStatus: 'pending',
              updatedAt: now,
            })
            .where(eq(weightPlans.id, id))
            .returning();

          const updatedPlan: WeightPlan = {
            ...result,
            targetDate: new Date(result.targetDate),
            startDate: new Date(result.startDate),
            createdAt: new Date(result.createdAt),
            updatedAt: new Date(result.updatedAt),
            syncStatus: result.syncStatus as SyncStatus,
          };

          set((state) => ({
            plans: state.plans.map((p) => (p.id === id ? updatedPlan : p)),
            activePlan: updatedPlan.isActive ? updatedPlan : state.activePlan,
            isLoading: false,
          }));
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to update plan',
            isLoading: false,
          });
        }
      },

      deletePlan: async (id) => {
        set({ isLoading: true, error: null });
        try {
          await db.delete(weightPlans).where(eq(weightPlans.id, id));

          set((state) => {
            const newPlans = state.plans.filter((p) => p.id !== id);
            const newActivePlan = newPlans.find((p) => p.isActive) || null;
            return {
              plans: newPlans,
              activePlan: newActivePlan,
              isLoading: false,
            };
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to delete plan',
            isLoading: false,
          });
        }
      },

      setActivePlan: async (id) => {
        if (id === null) return;

        set({ isLoading: true, error: null });
        try {
          // Deactivate all plans
          await db.update(weightPlans).set({ isActive: false });

          // Activate selected plan
          const [result] = await db
            .update(weightPlans)
            .set({ isActive: true })
            .where(eq(weightPlans.id, id))
            .returning();

          if (result) {
            const updatedPlan: WeightPlan = {
              ...result,
              targetDate: new Date(result.targetDate),
              startDate: new Date(result.startDate),
              createdAt: new Date(result.createdAt),
              updatedAt: new Date(result.updatedAt),
              syncStatus: result.syncStatus as SyncStatus,
            };

            set((state) => ({
              plans: state.plans.map((p) =>
                p.id === id ? updatedPlan : { ...p, isActive: false }
              ),
              activePlan: updatedPlan,
              isLoading: false,
            }));
          }
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to set active plan',
            isLoading: false,
          });
        }
      },

      getActivePlan: () => {
        return get().plans.find((p) => p.isActive) || null;
      },

      getPendingPlans: () => {
        return get().plans.filter((p) => p.syncStatus === 'pending');
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'weight-plan-storage',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({ plans: state.plans, activePlan: state.activePlan }),
    }
  )
);

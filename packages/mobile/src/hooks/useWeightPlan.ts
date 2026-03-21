import { useCallback, useState } from 'react';
import { db } from '../db';
import { weightPlans, type WeightPlan, type NewWeightPlan } from '../db/schema';
import { desc, eq, and } from 'drizzle-orm';
import { useDatabase } from './useDatabase';

interface WeightPlanProgress {
  progressPercent: number;
  expectedWeight: number;
  remainingDays: number;
  status: 'ahead' | 'on_track' | 'behind';
}

interface UseWeightPlanReturn {
  plans: WeightPlan[];
  activePlan: WeightPlan | null;
  isLoading: boolean;
  error: string | null;
  fetchPlans: () => Promise<void>;
  createPlan: (targetWeight: number, targetDate: Date, startWeight?: number) => Promise<WeightPlan>;
  updatePlan: (id: number, updates: Partial<Omit<NewWeightPlan, 'id' | 'createdAt'>>) => Promise<WeightPlan>;
  deletePlan: (id: number) => Promise<void>;
  setActivePlan: (id: number) => Promise<void>;
  calculateProgress: (currentWeight: number) => WeightPlanProgress | null;
  refresh: () => Promise<void>;
}

/**
 * Hook for weight plan operations
 */
export function useWeightPlan(): UseWeightPlanReturn {
  const [plans, setPlans] = useState<WeightPlan[]>([]);
  const [activePlan, setActivePlanState] = useState<WeightPlan | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { executeQuery } = useDatabase();

  const fetchPlans = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const results = await executeQuery(() =>
        db.select().from(weightPlans).orderBy(desc(weightPlans.createdAt))
      );
      setPlans(results);
      setActivePlanState(results.find(p => p.isActive) || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch plans');
    } finally {
      setIsLoading(false);
    }
  }, [executeQuery]);

  const createPlan = useCallback(async (
    targetWeight: number,
    targetDate: Date,
    startWeight?: number
  ): Promise<WeightPlan> => {
    const now = new Date();
    
    // Deactivate any existing active plans
    await executeQuery(async () => {
      await db.update(weightPlans)
        .set({ isActive: false, updatedAt: now })
        .where(eq(weightPlans.isActive, true));
    });

    const newPlan: NewWeightPlan = {
      targetWeight,
      targetDate,
      startWeight: startWeight ?? targetWeight, // If not provided, use target as baseline
      startDate: now,
      isActive: true,
      syncStatus: 'pending',
      createdAt: now,
      updatedAt: now,
    };

    const result = await executeQuery(async () => {
      const inserted = await db.insert(weightPlans).values(newPlan).returning();
      return inserted[0];
    });

    await fetchPlans();
    return result;
  }, [executeQuery, fetchPlans]);

  const updatePlan = useCallback(async (
    id: number,
    updates: Partial<Omit<NewWeightPlan, 'id' | 'createdAt'>>
  ): Promise<WeightPlan> => {
    const updateData: Partial<NewWeightPlan> = {
      ...updates,
      updatedAt: new Date(),
      syncStatus: 'pending',
    };

    const result = await executeQuery(async () => {
      const updated = await db.update(weightPlans).set(updateData).where(eq(weightPlans.id, id)).returning();
      if (!updated[0]) throw new Error('Weight plan not found');
      return updated[0];
    });

    await fetchPlans();
    return result;
  }, [executeQuery, fetchPlans]);

  const deletePlan = useCallback(async (id: number): Promise<void> => {
    await executeQuery(async () => {
      await db.delete(weightPlans).where(eq(weightPlans.id, id));
    });
    await fetchPlans();
  }, [executeQuery, fetchPlans]);

  const setActivePlan = useCallback(async (id: number): Promise<void> => {
    const now = new Date();
    
    await executeQuery(async () => {
      // Deactivate all plans
      await db.update(weightPlans)
        .set({ isActive: false, updatedAt: now })
        .where(eq(weightPlans.isActive, true));
      
      // Activate selected plan
      await db.update(weightPlans)
        .set({ isActive: true, updatedAt: now, syncStatus: 'pending' })
        .where(eq(weightPlans.id, id));
    });

    await fetchPlans();
  }, [executeQuery, fetchPlans]);

  const calculateProgress = useCallback((currentWeight: number): WeightPlanProgress | null => {
    if (!activePlan) return null;

    const now = new Date();
    const totalDays = Math.ceil((activePlan.targetDate.getTime() - activePlan.startDate.getTime()) / (1000 * 60 * 60 * 24));
    const elapsedDays = Math.ceil((now.getTime() - activePlan.startDate.getTime()) / (1000 * 60 * 60 * 24));
    const remainingDays = Math.max(0, totalDays - elapsedDays);

    // Calculate expected weight based on linear progression
    const weightChange = activePlan.targetWeight - activePlan.startWeight;
    const progressRatio = Math.min(elapsedDays / totalDays, 1);
    const expectedWeight = activePlan.startWeight + (weightChange * progressRatio);

    // Calculate actual progress
    const actualChange = currentWeight - activePlan.startWeight;
    const expectedChange = expectedWeight - activePlan.startWeight;
    const progressPercent = expectedChange !== 0 
      ? Math.round((actualChange / expectedChange) * 100)
      : 0;

    // Determine status
    const deviation = currentWeight - expectedWeight;
    let status: 'ahead' | 'on_track' | 'behind';
    
    if (weightChange < 0) {
      // Weight loss goal
      status = deviation < -0.5 ? 'ahead' : deviation > 0.5 ? 'behind' : 'on_track';
    } else {
      // Weight gain goal
      status = deviation > 0.5 ? 'ahead' : deviation < -0.5 ? 'behind' : 'on_track';
    }

    return {
      progressPercent,
      expectedWeight: Number(expectedWeight.toFixed(2)),
      remainingDays,
      status,
    };
  }, [activePlan]);

  const refresh = useCallback(async () => {
    await fetchPlans();
  }, [fetchPlans]);

  return {
    plans,
    activePlan,
    isLoading,
    error,
    fetchPlans,
    createPlan,
    updatePlan,
    deletePlan,
    setActivePlan,
    calculateProgress,
    refresh,
  };
}

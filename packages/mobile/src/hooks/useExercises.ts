import { useCallback, useState } from 'react';
import { db } from '../db';
import { exerciseRecords, type ExerciseRecord, type NewExerciseRecord, type ExerciseType } from '../db/schema';
import { desc, eq, and, gte, lte } from 'drizzle-orm';
import { useDatabase } from './useDatabase';

// MET values for calorie calculation
const MET_VALUES: Record<ExerciseType, number> = {
  running: 10,
  swimming: 8,
  cycling: 7,
  fitness: 6,
  yoga: 3,
  other: 4,
};

interface UseExercisesReturn {
  exercises: ExerciseRecord[];
  isLoading: boolean;
  error: string | null;
  fetchExercises: (params?: { limit?: number; offset?: number; startDate?: Date; endDate?: Date }) => Promise<void>;
  addExercise: (type: ExerciseType, duration: number, calories?: number, recordTime?: Date) => Promise<ExerciseRecord>;
  updateExercise: (id: number, updates: Partial<Omit<NewExerciseRecord, 'id' | 'createdAt'>>) => Promise<ExerciseRecord>;
  deleteExercise: (id: number) => Promise<void>;
  calculateCalories: (type: ExerciseType, duration: number) => number;
  getStatistics: (days?: number) => Promise<{ totalDuration: number; totalCalories: number; count: number } | null>;
  refresh: () => Promise<void>;
}

/**
 * Calculate estimated calories based on MET value and duration
 * Formula: Calories = MET × 3.5 × weight(kg) × duration(min) / 200
 * Using average weight of 70kg
 */
function calculateCaloriesByMET(type: ExerciseType, duration: number): number {
  const met = MET_VALUES[type] || 4;
  const avgWeight = 70; // kg
  const calories = (met * 3.5 * avgWeight * duration) / 200;
  return Math.round(calories);
}

/**
 * Hook for exercise record operations
 */
export function useExercises(): UseExercisesReturn {
  const [exercises, setExercises] = useState<ExerciseRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { executeQuery } = useDatabase();

  const fetchExercises = useCallback(async (params?: { limit?: number; offset?: number; startDate?: Date; endDate?: Date }) => {
    setIsLoading(true);
    setError(null);

    try {
      let query = db.select().from(exerciseRecords);

      if (params?.startDate) {
        query = query.where(gte(exerciseRecords.recordTime, params.startDate));
      }
      if (params?.endDate) {
        query = query.where(lte(exerciseRecords.recordTime, params.endDate));
      }

      query = query.orderBy(desc(exerciseRecords.recordTime));

      if (params?.limit) {
        query = query.limit(params.limit);
      }
      if (params?.offset) {
        query = query.offset(params.offset);
      }

      const results = await executeQuery(() => query);
      setExercises(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch exercises');
    } finally {
      setIsLoading(false);
    }
  }, [executeQuery]);

  const addExercise = useCallback(async (
    type: ExerciseType,
    duration: number,
    calories?: number,
    recordTime?: Date
  ): Promise<ExerciseRecord> => {
    const now = new Date();
    const calculatedCalories = calories ?? calculateCaloriesByMET(type, duration);

    const newRecord: NewExerciseRecord = {
      type,
      duration,
      calories: calculatedCalories,
      recordTime: recordTime || now,
      syncStatus: 'pending',
      createdAt: now,
      updatedAt: now,
    };

    const result = await executeQuery(async () => {
      const inserted = await db.insert(exerciseRecords).values(newRecord).returning();
      return inserted[0];
    });

    await fetchExercises();
    return result;
  }, [executeQuery, fetchExercises]);

  const updateExercise = useCallback(async (
    id: number,
    updates: Partial<Omit<NewExerciseRecord, 'id' | 'createdAt'>>
  ): Promise<ExerciseRecord> => {
    const updateData: Partial<NewExerciseRecord> = {
      ...updates,
      updatedAt: new Date(),
      syncStatus: 'pending',
    };

    // Recalculate calories if type or duration changed
    if ((updates.type || updates.duration) && !updates.calories) {
      const existing = await executeQuery(() =>
        db.select().from(exerciseRecords).where(eq(exerciseRecords.id, id)).limit(1)
      );
      if (existing[0]) {
        const newType = updates.type || existing[0].type;
        const newDuration = updates.duration || existing[0].duration;
        updateData.calories = calculateCaloriesByMET(newType, newDuration);
      }
    }

    const result = await executeQuery(async () => {
      const updated = await db.update(exerciseRecords).set(updateData).where(eq(exerciseRecords.id, id)).returning();
      if (!updated[0]) throw new Error('Exercise record not found');
      return updated[0];
    });

    await fetchExercises();
    return result;
  }, [executeQuery, fetchExercises]);

  const deleteExercise = useCallback(async (id: number): Promise<void> => {
    await executeQuery(async () => {
      await db.delete(exerciseRecords).where(eq(exerciseRecords.id, id));
    });
    await fetchExercises();
  }, [executeQuery, fetchExercises]);

  const calculateCalories = useCallback((type: ExerciseType, duration: number): number => {
    return calculateCaloriesByMET(type, duration);
  }, []);

  const getStatistics = useCallback(async (days?: number): Promise<{ totalDuration: number; totalCalories: number; count: number } | null> => {
    try {
      let query = db.select().from(exerciseRecords);
      
      if (days) {
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - days);
        query = query.where(gte(exerciseRecords.recordTime, cutoffDate));
      }

      const results = await executeQuery(() => query);
      
      if (results.length === 0) return null;

      return {
        totalDuration: results.reduce((sum, r) => sum + r.duration, 0),
        totalCalories: results.reduce((sum, r) => sum + r.calories, 0),
        count: results.length,
      };
    } catch (err) {
      return null;
    }
  }, [executeQuery]);

  const refresh = useCallback(async () => {
    await fetchExercises();
  }, [fetchExercises]);

  return {
    exercises,
    isLoading,
    error,
    fetchExercises,
    addExercise,
    updateExercise,
    deleteExercise,
    calculateCalories,
    getStatistics,
    refresh,
  };
}

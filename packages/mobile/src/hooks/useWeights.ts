import { useCallback, useState } from 'react';
import { db } from '../db';
import { weightRecords, type WeightRecord, type NewWeightRecord } from '../db/schema';
import { desc, asc, eq, and, gte, lte, sql } from 'drizzle-orm';
import { useDatabase } from './useDatabase';

interface UseWeightsReturn {
  weights: WeightRecord[];
  isLoading: boolean;
  error: string | null;
  fetchWeights: (params?: { limit?: number; offset?: number; startDate?: Date; endDate?: Date }) => Promise<void>;
  addWeight: (value: number, recordTime?: Date) => Promise<WeightRecord>;
  updateWeight: (id: number, value: number, recordTime?: Date) => Promise<WeightRecord>;
  deleteWeight: (id: number) => Promise<void>;
  getStatistics: (days?: number) => Promise<{ avg: number; min: number; max: number; count: number } | null>;
  refresh: () => Promise<void>;
}

/**
 * Hook for weight record operations
 */
export function useWeights(): UseWeightsReturn {
  const [weights, setWeights] = useState<WeightRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { executeQuery } = useDatabase();

  const fetchWeights = useCallback(async (params?: { limit?: number; offset?: number; startDate?: Date; endDate?: Date }) => {
    setIsLoading(true);
    setError(null);

    try {
      let query = db.select().from(weightRecords);

      if (params?.startDate) {
        query = query.where(gte(weightRecords.recordTime, params.startDate));
      }
      if (params?.endDate) {
        query = query.where(lte(weightRecords.recordTime, params.endDate));
      }

      query = query.orderBy(desc(weightRecords.recordTime));

      if (params?.limit) {
        query = query.limit(params.limit);
      }
      if (params?.offset) {
        query = query.offset(params.offset);
      }

      const results = await executeQuery(() => query);
      setWeights(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch weights');
    } finally {
      setIsLoading(false);
    }
  }, [executeQuery]);

  const addWeight = useCallback(async (value: number, recordTime?: Date): Promise<WeightRecord> => {
    const now = new Date();
    const newRecord: NewWeightRecord = {
      value,
      recordTime: recordTime || now,
      syncStatus: 'pending',
      createdAt: now,
      updatedAt: now,
    };

    const result = await executeQuery(async () => {
      const inserted = await db.insert(weightRecords).values(newRecord).returning();
      return inserted[0];
    });

    // Refresh the list
    await fetchWeights();
    return result;
  }, [executeQuery, fetchWeights]);

  const updateWeight = useCallback(async (id: number, value: number, recordTime?: Date): Promise<WeightRecord> => {
    const updates: Partial<NewWeightRecord> = {
      value,
      updatedAt: new Date(),
      syncStatus: 'pending',
    };

    if (recordTime) {
      updates.recordTime = recordTime;
    }

    const result = await executeQuery(async () => {
      const updated = await db.update(weightRecords).set(updates).where(eq(weightRecords.id, id)).returning();
      if (!updated[0]) throw new Error('Weight record not found');
      return updated[0];
    });

    await fetchWeights();
    return result;
  }, [executeQuery, fetchWeights]);

  const deleteWeight = useCallback(async (id: number): Promise<void> => {
    await executeQuery(async () => {
      await db.delete(weightRecords).where(eq(weightRecords.id, id));
    });
    await fetchWeights();
  }, [executeQuery, fetchWeights]);

  const getStatistics = useCallback(async (days?: number): Promise<{ avg: number; min: number; max: number; count: number } | null> => {
    try {
      let query = db.select().from(weightRecords);
      
      if (days) {
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - days);
        query = query.where(gte(weightRecords.recordTime, cutoffDate));
      }

      const results = await executeQuery(() => query);
      
      if (results.length === 0) return null;

      const values = results.map(r => r.value);
      return {
        avg: Number((values.reduce((a, b) => a + b, 0) / values.length).toFixed(2)),
        min: Math.min(...values),
        max: Math.max(...values),
        count: values.length,
      };
    } catch (err) {
      return null;
    }
  }, [executeQuery]);

  const refresh = useCallback(async () => {
    await fetchWeights();
  }, [fetchWeights]);

  return {
    weights,
    isLoading,
    error,
    fetchWeights,
    addWeight,
    updateWeight,
    deleteWeight,
    getStatistics,
    refresh,
  };
}

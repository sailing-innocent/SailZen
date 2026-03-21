import { useState, useEffect, useCallback } from 'react';
import { db } from '../db';
import * as schema from '../db/schema';

interface MigrationStatus {
  isReady: boolean;
  isMigrating: boolean;
  error: string | null;
}

/**
 * Hook for managing database migrations and initialization
 */
export function useMigrations(): MigrationStatus {
  const [status, setStatus] = useState<MigrationStatus>({
    isReady: false,
    isMigrating: true,
    error: null,
  });

  useEffect(() => {
    const initializeDatabase = async () => {
      try {
        setStatus((prev) => ({ ...prev, isMigrating: true, error: null }));

        // Create tables if they don't exist
        // Note: Drizzle ORM with expo-sqlite handles table creation automatically
        // when we insert data, but we can also use drizzle-kit for migrations
        
        // For now, we'll verify database connection by querying
        await db.select().from(schema.syncMetadata).limit(1);

        setStatus({
          isReady: true,
          isMigrating: false,
          error: null,
        });
      } catch (error) {
        console.error('Database initialization error:', error);
        setStatus({
          isReady: false,
          isMigrating: false,
          error: error instanceof Error ? error.message : 'Unknown database error',
        });
      }
    };

    initializeDatabase();
  }, []);

  return status;
}

/**
 * Hook for accessing database instance with error handling
 */
export function useDatabase() {
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Verify database is accessible
    const checkDatabase = async () => {
      try {
        await db.select().from(schema.syncMetadata).limit(1);
        setIsReady(true);
        setError(null);
      } catch (err) {
        setIsReady(false);
        setError(err instanceof Error ? err.message : 'Database not ready');
      }
    };

    checkDatabase();
  }, []);

  const executeQuery = useCallback(
    async <T,>(queryFn: () => Promise<T>): Promise<T> => {
      if (!isReady) {
        throw new Error('Database is not ready');
      }
      return queryFn();
    },
    [isReady]
  );

  return {
    db,
    isReady,
    error,
    executeQuery,
  };
}

/**
 * Debug hook for inspecting database contents (development only)
 */
export function useDatabaseDebug() {
  const getTableCounts = useCallback(async () => {
    if (!__DEV__) return null;

    try {
      const weightCount = await db.$count(schema.weightRecords);
      const exerciseCount = await db.$count(schema.exerciseRecords);
      const planCount = await db.$count(schema.weightPlans);
      const metadata = await db.select().from(schema.syncMetadata).limit(1);

      return {
        weightRecords: weightCount,
        exerciseRecords: exerciseCount,
        weightPlans: planCount,
        syncMetadata: metadata[0] || null,
      };
    } catch (error) {
      console.error('Debug query error:', error);
      return null;
    }
  }, []);

  const dumpTable = useCallback(async (tableName: 'weightRecords' | 'exerciseRecords' | 'weightPlans') => {
    if (!__DEV__) return null;

    try {
      let data;
      switch (tableName) {
        case 'weightRecords':
          data = await db.select().from(schema.weightRecords).limit(50);
          break;
        case 'exerciseRecords':
          data = await db.select().from(schema.exerciseRecords).limit(50);
          break;
        case 'weightPlans':
          data = await db.select().from(schema.weightPlans).limit(50);
          break;
      }
      return data;
    } catch (error) {
      console.error('Debug dump error:', error);
      return null;
    }
  }, []);

  return {
    getTableCounts,
    dumpTable,
    isEnabled: __DEV__,
  };
}

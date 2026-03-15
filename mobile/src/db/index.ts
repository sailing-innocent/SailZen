import { drizzle } from 'drizzle-orm/expo-sqlite';
import { openDatabaseSync } from 'expo-sqlite';
import * as schema from './schema';

const expoDb = openDatabaseSync('sailzen.db');

export const db = drizzle(expoDb, { schema });

export * from './schema';

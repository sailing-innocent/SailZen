/**
 * @file cache.ts
 * @brief Data caching utility with TTL support
 * @description Provides a simple in-memory cache with time-to-live and size limits
 */

interface CacheEntry<T> {
  data: T
  timestamp: number
  expiresAt: number
}

interface CacheOptions {
  /** Time-to-live in milliseconds (default: 5 minutes) */
  ttl?: number
  /** Maximum number of entries (default: 100) */
  maxSize?: number
  /** Storage key prefix for localStorage persistence */
  storageKey?: string
}

/**
 * DataCache - A generic caching utility with TTL support
 * 
 * Features:
 * - Time-based expiration (TTL)
 * - Size-limited cache with LRU eviction
 * - Optional localStorage persistence
 * - Stale-while-revalidate support
 */
export class DataCache<T> {
  private cache: Map<string, CacheEntry<T>> = new Map()
  private readonly ttl: number
  private readonly maxSize: number
  private readonly storageKey?: string

  constructor(options: CacheOptions = {}) {
    this.ttl = options.ttl ?? 5 * 60 * 1000 // 5 minutes default
    this.maxSize = options.maxSize ?? 100
    this.storageKey = options.storageKey

    // Load from localStorage if available
    if (this.storageKey && typeof window !== 'undefined') {
      this.loadFromStorage()
    }
  }

  /**
   * Get a cached value by key
   * @returns The cached value or undefined if not found/expired
   */
  get(key: string): T | undefined {
    const entry = this.cache.get(key)
    
    if (!entry) {
      return undefined
    }

    // Check if expired
    if (Date.now() > entry.expiresAt) {
      this.cache.delete(key)
      return undefined
    }

    // Move to end for LRU (delete and re-add)
    this.cache.delete(key)
    this.cache.set(key, entry)

    return entry.data
  }

  /**
   * Get a cached value, returning stale data if available even if expired
   * @returns { data, isStale } or undefined if not found at all
   */
  getWithStale(key: string): { data: T; isStale: boolean } | undefined {
    const entry = this.cache.get(key)
    
    if (!entry) {
      return undefined
    }

    const isStale = Date.now() > entry.expiresAt

    // Move to end for LRU
    this.cache.delete(key)
    this.cache.set(key, entry)

    return { data: entry.data, isStale }
  }

  /**
   * Set a value in the cache
   */
  set(key: string, data: T, customTtl?: number): void {
    // Evict oldest entries if at capacity
    while (this.cache.size >= this.maxSize) {
      const oldestKey = this.cache.keys().next().value
      if (oldestKey) {
        this.cache.delete(oldestKey)
      }
    }

    const now = Date.now()
    const entry: CacheEntry<T> = {
      data,
      timestamp: now,
      expiresAt: now + (customTtl ?? this.ttl),
    }

    this.cache.set(key, entry)

    // Persist to localStorage if configured
    if (this.storageKey) {
      this.saveToStorage()
    }
  }

  /**
   * Check if a key exists and is not expired
   */
  has(key: string): boolean {
    return this.get(key) !== undefined
  }

  /**
   * Remove a specific entry
   */
  delete(key: string): boolean {
    const result = this.cache.delete(key)
    if (this.storageKey) {
      this.saveToStorage()
    }
    return result
  }

  /**
   * Clear all entries
   */
  clear(): void {
    this.cache.clear()
    if (this.storageKey && typeof window !== 'undefined') {
      try {
        localStorage.removeItem(this.storageKey)
      } catch (e) {
        // Ignore localStorage errors
      }
    }
  }

  /**
   * Get cache statistics
   */
  getStats(): { size: number; maxSize: number; ttl: number } {
    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      ttl: this.ttl,
    }
  }

  /**
   * Invalidate entries matching a pattern
   */
  invalidatePattern(pattern: RegExp): number {
    let count = 0
    for (const key of this.cache.keys()) {
      if (pattern.test(key)) {
        this.cache.delete(key)
        count++
      }
    }
    if (count > 0 && this.storageKey) {
      this.saveToStorage()
    }
    return count
  }

  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem(this.storageKey!)
      if (stored) {
        const entries: Array<[string, CacheEntry<T>]> = JSON.parse(stored)
        const now = Date.now()
        
        // Only load non-expired entries
        for (const [key, entry] of entries) {
          if (entry.expiresAt > now) {
            this.cache.set(key, entry)
          }
        }
      }
    } catch (e) {
      // Ignore localStorage errors
      console.warn('Failed to load cache from localStorage:', e)
    }
  }

  private saveToStorage(): void {
    try {
      const entries = Array.from(this.cache.entries())
      localStorage.setItem(this.storageKey!, JSON.stringify(entries))
    } catch (e) {
      // Ignore localStorage errors (quota exceeded, etc.)
      console.warn('Failed to save cache to localStorage:', e)
    }
  }
}

/**
 * Create a cache key from an object
 */
export function createCacheKey(prefix: string, params: Record<string, unknown>): string {
  const sortedParams = Object.keys(params)
    .sort()
    .map(key => `${key}=${JSON.stringify(params[key])}`)
    .join('&')
  return `${prefix}:${sortedParams}`
}

/**
 * Singleton caches for different data types
 */
export const transactionCache = new DataCache<unknown>({
  ttl: 2 * 60 * 1000, // 2 minutes for transactions
  maxSize: 50,
})

export const statsCache = new DataCache<unknown>({
  ttl: 5 * 60 * 1000, // 5 minutes for statistics
  maxSize: 200,
  storageKey: 'sailzen_stats_cache',
})

export const accountCache = new DataCache<unknown>({
  ttl: 10 * 60 * 1000, // 10 minutes for accounts (less frequently changed)
  maxSize: 50,
})

/**
 * useCachedData - Hook for cached data fetching
 * 
 * @param cacheKey - Unique key for this data
 * @param fetcher - Function to fetch fresh data
 * @param options - Cache options
 */
export async function fetchWithCache<T>(
  cache: DataCache<T>,
  key: string,
  fetcher: () => Promise<T>,
  options: { forceRefresh?: boolean; staleWhileRevalidate?: boolean } = {}
): Promise<T> {
  const { forceRefresh = false, staleWhileRevalidate = false } = options

  // Check cache first (unless forcing refresh)
  if (!forceRefresh) {
    if (staleWhileRevalidate) {
      const cached = cache.getWithStale(key)
      if (cached) {
        if (cached.isStale) {
          // Return stale data immediately, but trigger background refresh
          fetcher().then(data => cache.set(key, data)).catch(() => {})
        }
        return cached.data
      }
    } else {
      const cached = cache.get(key)
      if (cached !== undefined) {
        return cached
      }
    }
  }

  // Fetch fresh data
  const data = await fetcher()
  cache.set(key, data)
  return data
}

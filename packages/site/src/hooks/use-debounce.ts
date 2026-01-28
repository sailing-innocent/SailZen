import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * useDebouncedValue - 返回防抖后的值
 * 
 * @param value 原始值
 * @param delay 防抖延迟（毫秒）
 * @returns 防抖后的值
 */
export function useDebouncedValue<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(timer)
    }
  }, [value, delay])

  return debouncedValue
}

/**
 * useDebouncedCallback - 返回防抖后的回调函数
 * 
 * @param callback 原始回调
 * @param delay 防抖延迟（毫秒）
 * @returns 防抖后的回调
 */
export function useDebouncedCallback<T extends (...args: any[]) => any>(
  callback: T,
  delay: number = 300
): T {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const callbackRef = useRef(callback)

  // 更新 callback ref
  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  const debouncedCallback = useCallback(
    (...args: Parameters<T>) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }

      timeoutRef.current = setTimeout(() => {
        callbackRef.current(...args)
      }, delay)
    },
    [delay]
  ) as T

  // 清理
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  return debouncedCallback
}

/**
 * useDebounce - 返回防抖后的值和立即更新函数
 * 
 * 适用于需要同时显示即时值和使用防抖值进行计算的场景
 * 
 * @param initialValue 初始值
 * @param delay 防抖延迟（毫秒）
 */
export function useDebounce<T>(initialValue: T, delay: number = 300) {
  const [value, setValue] = useState<T>(initialValue)
  const [debouncedValue, setDebouncedValue] = useState<T>(initialValue)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(timer)
    }
  }, [value, delay])

  return {
    value,
    debouncedValue,
    setValue,
  }
}

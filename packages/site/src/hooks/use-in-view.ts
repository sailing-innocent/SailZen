import { useState, useEffect, useRef, type RefObject } from 'react'

interface UseInViewOptions {
  /**
   * 触发一次后是否保持可见状态（不再隐藏）
   * 适用于懒加载场景，加载后不需要再卸载
   */
  triggerOnce?: boolean
  
  /**
   * 根元素的 margin，用于提前触发
   * 例如 '200px' 表示在元素进入视口前 200px 就触发
   */
  rootMargin?: string
  
  /**
   * 触发阈值，0-1 之间
   * 0 表示元素刚进入视口就触发，1 表示完全可见才触发
   */
  threshold?: number | number[]
}

interface UseInViewReturn {
  ref: RefObject<HTMLDivElement>
  inView: boolean
}

/**
 * useInView - 检测元素是否在视口中
 * 
 * 使用 IntersectionObserver API 实现高性能的可见性检测
 */
export function useInView(options: UseInViewOptions = {}): UseInViewReturn {
  const {
    triggerOnce = false,
    rootMargin = '0px',
    threshold = 0,
  } = options

  const ref = useRef<HTMLDivElement>(null)
  const [inView, setInView] = useState(false)
  
  // 用于 triggerOnce 模式，记录是否已经触发过
  const hasTriggered = useRef(false)

  useEffect(() => {
    const element = ref.current
    if (!element) return

    // 如果已经触发过且是 triggerOnce 模式，不需要再观察
    if (hasTriggered.current && triggerOnce) return

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0]
        if (entry.isIntersecting) {
          setInView(true)
          hasTriggered.current = true
          
          // triggerOnce 模式下，触发后停止观察
          if (triggerOnce) {
            observer.disconnect()
          }
        } else if (!triggerOnce) {
          // 非 triggerOnce 模式下，离开视口时设为 false
          setInView(false)
        }
      },
      {
        rootMargin,
        threshold,
      }
    )

    observer.observe(element)

    return () => {
      observer.disconnect()
    }
  }, [rootMargin, threshold, triggerOnce])

  return { ref, inView }
}

export default useInView

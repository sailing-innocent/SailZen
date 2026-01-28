import React from 'react'
import { useInView } from '@/hooks/use-in-view'
import { Skeleton } from '@/components/ui/skeleton'

interface LazyChartProps {
  /**
   * 图表内容，只在可见时渲染
   */
  children: React.ReactNode
  
  /**
   * 图表容器高度，用于占位和骨架屏
   */
  height?: number | string
  
  /**
   * 图表容器宽度
   */
  width?: number | string
  
  /**
   * 提前触发的距离（像素）
   * 用于在图表进入视口前提前加载
   */
  preloadOffset?: number
  
  /**
   * 额外的 className
   */
  className?: string
  
  /**
   * 骨架屏显示的文字
   */
  loadingText?: string
}

/**
 * LazyChart - 懒加载图表容器
 * 
 * 使用 IntersectionObserver 检测可见性，只在图表进入视口时才渲染。
 * 这对于页面底部的统计图表特别有用，可以显著提升初始加载性能。
 * 
 * 特性：
 * - 使用骨架屏作为占位
 * - 支持提前预加载（通过 preloadOffset）
 * - 一旦加载后不会卸载（triggerOnce）
 */
export function LazyChart({
  children,
  height = 300,
  width = '100%',
  preloadOffset = 200,
  className = '',
  loadingText = '图表加载中...',
}: LazyChartProps) {
  const { ref, inView } = useInView({
    triggerOnce: true,
    rootMargin: `${preloadOffset}px`,
  })

  const containerStyle: React.CSSProperties = {
    height: typeof height === 'number' ? `${height}px` : height,
    width: typeof width === 'number' ? `${width}px` : width,
  }

  return (
    <div ref={ref} className={className} style={containerStyle}>
      {inView ? (
        children
      ) : (
        <div className="flex flex-col items-center justify-center h-full w-full">
          <Skeleton className="w-full h-full rounded-lg" />
          <div className="absolute text-muted-foreground text-sm">
            {loadingText}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * LazySection - 懒加载区域容器
 * 
 * 更通用的懒加载容器，适用于任何需要延迟加载的内容
 */
export function LazySection({
  children,
  fallback,
  preloadOffset = 100,
  className = '',
}: {
  children: React.ReactNode
  fallback?: React.ReactNode
  preloadOffset?: number
  className?: string
}) {
  const { ref, inView } = useInView({
    triggerOnce: true,
    rootMargin: `${preloadOffset}px`,
  })

  return (
    <div ref={ref} className={className}>
      {inView ? children : (fallback || <Skeleton className="w-full h-32" />)}
    </div>
  )
}

export default LazyChart

import React from 'react'
import { useIsMobile } from '@/hooks/use-mobile'

interface ResponsiveGridProps {
  children: React.ReactNode
  mobileCols?: number
  desktopCols?: number
  gap?: string
  className?: string
}

/**
 * ResponsiveGrid - 响应式网格组件
 * 
 * 根据设备类型自动切换网格列数。
 * 移动端默认单列布局，桌面端默认三列布局。
 * 
 * @example
 * <ResponsiveGrid mobileCols={1} desktopCols={3} gap="4">
 *   <Card>...</Card>
 *   <Card>...</Card>
 *   <Card>...</Card>
 * </ResponsiveGrid>
 */
export const ResponsiveGrid: React.FC<ResponsiveGridProps> = ({
  children,
  mobileCols = 1,
  desktopCols = 3,
  gap = '4',
  className = ''
}) => {
  const isMobile = useIsMobile()
  const cols = isMobile ? mobileCols : desktopCols
  
  return (
    <div 
      className={`grid gap-${gap} ${className}`}
      style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
    >
      {children}
    </div>
  )
}

export default ResponsiveGrid

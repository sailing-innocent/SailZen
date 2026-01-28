import React from 'react'
import { useIsMobile } from '@/hooks/use-mobile'

interface ResponsiveContainerProps {
  children: React.ReactNode
  mobileClass?: string
  desktopClass?: string
  className?: string
}

/**
 * ResponsiveContainer - 响应式容器组件
 * 
 * 根据设备类型自动切换移动端和桌面端样式类。
 * 减少在每个组件中重复编写 isMobile 判断逻辑。
 * 
 * @example
 * <ResponsiveContainer mobileClass="flex-col gap-2" desktopClass="flex-row gap-6">
 *   <Card>...</Card>
 *   <Card>...</Card>
 * </ResponsiveContainer>
 */
export const ResponsiveContainer: React.FC<ResponsiveContainerProps> = ({
  children,
  mobileClass = 'flex-col',
  desktopClass = 'flex-row',
  className = ''
}) => {
  const isMobile = useIsMobile()
  
  return (
    <div className={`flex gap-4 ${isMobile ? mobileClass : desktopClass} ${className}`}>
      {children}
    </div>
  )
}

export default ResponsiveContainer

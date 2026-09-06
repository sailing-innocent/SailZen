import React from 'react'
import { useIsMobile } from '@/hooks/use-mobile'
import { ChartContainer, type ChartConfig } from '@/components/ui/chart'

interface ResponsiveChartContainerProps {
  children: React.ReactNode
  mobileHeight?: string
  desktopHeight?: string
  config: ChartConfig
  className?: string
}

/**
 * ResponsiveChartContainer - 响应式图表容器组件
 * 
 * 根据设备类型自动切换图表高度。
 * 移动端默认 200px 高度，桌面端默认 300px 高度。
 * 
 * @example
 * <ResponsiveChartContainer config={chartConfig} mobileHeight="180px" desktopHeight="280px">
 *   <LineChart data={data}>...</LineChart>
 * </ResponsiveChartContainer>
 */
export const ResponsiveChartContainer: React.FC<ResponsiveChartContainerProps> = ({
  children,
  mobileHeight = '200px',
  desktopHeight = '300px',
  config,
  className = ''
}) => {
  const isMobile = useIsMobile()
  
  return (
    <ChartContainer 
      config={config} 
      className={`w-full ${className}`}
      style={{ height: isMobile ? mobileHeight : desktopHeight }}
    >
      {children}
    </ChartContainer>
  )
}

export default ResponsiveChartContainer

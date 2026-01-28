import React from 'react'
import { useIsMobile } from '@/hooks/use-mobile'

interface ResponsiveTextProps {
  children: React.ReactNode
  mobileSize?: 'xs' | 'sm' | 'base' | 'lg' | 'xl' | '2xl'
  desktopSize?: 'xs' | 'sm' | 'base' | 'lg' | 'xl' | '2xl' | '3xl'
  as?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'p' | 'span' | 'div'
  className?: string
}

const sizeClasses: Record<string, string> = {
  'xs': 'text-xs',
  'sm': 'text-sm',
  'base': 'text-base',
  'lg': 'text-lg',
  'xl': 'text-xl',
  '2xl': 'text-2xl',
  '3xl': 'text-3xl',
}

/**
 * ResponsiveText - 响应式文本组件
 * 
 * 根据设备类型自动切换文字大小。
 * 
 * @example
 * <ResponsiveText as="h1" mobileSize="lg" desktopSize="2xl" className="font-bold">
 *   页面标题
 * </ResponsiveText>
 */
export const ResponsiveText: React.FC<ResponsiveTextProps> = ({
  children,
  mobileSize = 'base',
  desktopSize = 'lg',
  as: Component = 'span',
  className = ''
}) => {
  const isMobile = useIsMobile()
  const sizeClass = isMobile ? sizeClasses[mobileSize] : sizeClasses[desktopSize]
  
  return (
    <Component className={`${sizeClass} ${className}`}>
      {children}
    </Component>
  )
}

export default ResponsiveText

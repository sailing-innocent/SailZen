import React from 'react'
import Pagebar from '@components/pagebar'
import MobileNav from '@components/mobile_nav'
import { useIsMobile } from '@/hooks/use-mobile'

const PageLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const isMobile = useIsMobile()

  if (isMobile) {
    return <MobileNav>{children}</MobileNav>
  }

  return (
    <div className="flex flex-row gap-6 min-h-screen">
      {/* 桌面端侧边栏 */}
      <div className="w-16 md:w-32 lg:w-64 h-full">
        <Pagebar />
      </div>
      {/* 主内容区域 */}
      <div className="flex flex-col gap-6 w-full">{children}</div>
    </div>
  )
}

export default PageLayout

import React from 'react'
import { PAGE_ROUTES } from '@/config/basic'
import {
  SidebarProvider,
  SidebarHeader,
  SidebarContent,
  SidebarFooter,
  SidebarMenu,
  SidebarMenuButton,
  SidebarGroup,
  SidebarGroupContent,
} from '@/components/ui/sidebar'
import { Link } from 'react-router-dom'
import { useIsMobile } from '@/hooks/use-mobile'

const Pagebar: React.FC = () => {
  const isMobile = useIsMobile()

  // 在移动端隐藏侧边栏
  if (isMobile) {
    return null
  }

  return (
    <>
      <SidebarProvider>
        <SidebarHeader title="SailSite" />
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {PAGE_ROUTES.map((route) => (
                  <SidebarMenuButton key={route.name} asChild>
                    <Link key={route.name} to={route.path}>
                      {route.name}
                    </Link>
                  </SidebarMenuButton>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter />
      </SidebarProvider>
    </>
  )
}

export default Pagebar

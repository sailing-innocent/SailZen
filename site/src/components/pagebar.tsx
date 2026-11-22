import React from 'react'
import { MAIN_ROUTES, SYSTEM_ROUTES, type PageRoute } from '@/config/basic'
import {
  SidebarProvider,
  SidebarHeader,
  SidebarContent,
  SidebarFooter,
  SidebarMenu,
  SidebarMenuButton,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarSeparator,
} from '@/components/ui/sidebar'
import { Link, useLocation } from 'react-router-dom'
import { useIsMobile } from '@/hooks/use-mobile'

const renderNavItem = (route: PageRoute, currentPath: string) => {
  const Icon = route.icon
  const isActive = currentPath === route.path || (route.path === '/main' && currentPath === '/')
  return (
    <SidebarMenuButton key={route.name} asChild isActive={isActive} tooltip={route.label}>
      <Link to={route.path} className="flex items-center gap-2">
        <Icon className="h-4 w-4 shrink-0" />
        <span className="truncate">{route.label || route.name}</span>
      </Link>
    </SidebarMenuButton>
  )
}

const Pagebar: React.FC = () => {
  const isMobile = useIsMobile()
  const location = useLocation()

  // 在移动端隐藏侧边栏
  if (isMobile) {
    return null
  }

  return (
    <SidebarProvider className="flex-col sticky top-0 h-svh min-h-svh border-r bg-sidebar/50">
      <SidebarHeader className="px-3 pt-4 pb-2">
        <Link to="/main" className="flex items-center gap-2 px-1 font-semibold tracking-tight text-base">
          <span>SailZen</span>
        </Link>
      </SidebarHeader>
      <SidebarContent className="flex-1">
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {MAIN_ROUTES.map((route) => renderNavItem(route, location.pathname))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      {SYSTEM_ROUTES.length > 0 && (
        <SidebarFooter className="pt-0 pb-3">
          <SidebarSeparator className="mb-1" />
          <SidebarGroup className="p-0">
            <SidebarGroupLabel className="text-[11px] uppercase tracking-wider text-muted-foreground/80">
              Observability
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {SYSTEM_ROUTES.map((route) => renderNavItem(route, location.pathname))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarFooter>
      )}
    </SidebarProvider>
  )
}

export default Pagebar

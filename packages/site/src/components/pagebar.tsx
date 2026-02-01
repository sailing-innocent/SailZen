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
import { Link, useLocation } from 'react-router-dom'
import { useIsMobile } from '@/hooks/use-mobile'
import {
  Home,
  Wallet,
  Heart,
  FolderKanban,
  FileText,
  Type,
  Package,
} from 'lucide-react'

// 图标映射
const iconMap: Record<string, React.ReactNode> = {
  Home: <Home className="h-4 w-4" />,
  Wallet: <Wallet className="h-4 w-4" />,
  Heart: <Heart className="h-4 w-4" />,
  FolderKanban: <FolderKanban className="h-4 w-4" />,
  FileText: <FileText className="h-4 w-4" />,
  Type: <Type className="h-4 w-4" />,
  Package: <Package className="h-4 w-4" />,
}

const Pagebar: React.FC = () => {
  const isMobile = useIsMobile()
  const location = useLocation()

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
                  <SidebarMenuButton
                    key={route.name}
                    asChild
                    isActive={location.pathname === route.path}
                  >
                    <Link to={route.path} className="flex items-center gap-2">
                      {route.icon && iconMap[route.icon]}
                      <span>{route.label || route.name}</span>
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

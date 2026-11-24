import React from 'react'
import { useIsMobile } from '@/hooks/use-mobile'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Menu } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { MAIN_ROUTES, SYSTEM_ROUTES, type PageRoute } from '@/config/basic'
import { GlobalInboxDrawerButton, UserProfileDialogButton } from '@components/user/UserInboxPanel'

interface MobileNavProps {
  children: React.ReactNode
}

const MobileNav: React.FC<MobileNavProps> = ({ children }) => {
  const isMobile = useIsMobile()
  const location = useLocation()
  const [open, setOpen] = React.useState(false)

  if (!isMobile) {
    return <>{children}</>
  }

  const renderLink = (route: PageRoute) => {
    const Icon = route.icon
    const isActive =
      location.pathname === route.path || (route.path === '/main' && location.pathname === '/')
    return (
      <Link
        key={route.path}
        to={route.path}
        className={`flex items-center gap-3 w-full p-3 text-left rounded-md transition-colors ${
          isActive ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
        }`}
        onClick={() => setOpen(false)}
      >
        <Icon className="h-5 w-5 shrink-0" />
        <span>{route.label || route.name}</span>
      </Link>
    )
  }

  return (
    <div className="w-full">
      {/* 移动端顶部导航栏 */}
      <div className="flex items-center justify-between p-4 bg-white border-b">
        <div className="text-lg font-semibold">SailZen</div>
        <div className="flex items-center gap-1">
          <GlobalInboxDrawerButton compact />
          <UserProfileDialogButton compact />
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
          <SheetContent side="right" className="w-72 flex flex-col">
            <SheetHeader>
              <SheetTitle>导航菜单</SheetTitle>
            </SheetHeader>
            <div className="mt-4 flex-1 overflow-y-auto space-y-1.5">
              {MAIN_ROUTES.map(renderLink)}
            </div>
            {SYSTEM_ROUTES.length > 0 && (
              <div className="pt-3 mt-3 border-t space-y-1.5">
                <div className="px-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Observability
                </div>
                {SYSTEM_ROUTES.map(renderLink)}
              </div>
            )}
          </SheetContent>
        </Sheet>
        </div>
      </div>

      {/* 主内容区域 - 添加溢出控制防止图表超出屏幕 */}
      <div className="p-4 overflow-x-hidden max-w-full">
        <div className="flex flex-col gap-4 w-full max-w-full">{children}</div>
      </div>
    </div>
  )
}

export default MobileNav

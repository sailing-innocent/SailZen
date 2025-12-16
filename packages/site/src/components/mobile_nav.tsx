import React from 'react'
import { useIsMobile } from '@/hooks/use-mobile'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Menu } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { PAGE_ROUTES } from '@/config/basic'

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

  return (
    <div className="w-full">
      {/* 移动端顶部导航栏 */}
      <div className="flex items-center justify-between p-4 bg-white border-b">
        <div className="text-lg font-semibold">SailSite</div>
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon">
              <Menu className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-72">
            <SheetHeader>
              <SheetTitle>导航菜单</SheetTitle>
            </SheetHeader>
            <div className="mt-6 space-y-4">
              {PAGE_ROUTES.map((route) => (
                <Link
                  key={route.path}
                  to={route.path}
                  className={`block w-full p-3 text-left rounded-md transition-colors ${
                    location.pathname === route.path ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
                  }`}
                  onClick={() => setOpen(false)}
                >
                  {route.name}
                </Link>
              ))}
            </div>
          </SheetContent>
        </Sheet>
      </div>

      {/* 主内容区域 */}
      <div className="p-4">{children}</div>
    </div>
  )
}

export default MobileNav

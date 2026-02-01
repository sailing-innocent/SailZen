import React from 'react'
import { useIsMobile } from '@/hooks/use-mobile'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import {
  Menu,
  Home,
  Wallet,
  Heart,
  FolderKanban,
  FileText,
  Type,
  Package,
} from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { PAGE_ROUTES } from '@/config/basic'

// 图标映射
const iconMap: Record<string, React.ReactNode> = {
  Home: <Home className="h-5 w-5" />,
  Wallet: <Wallet className="h-5 w-5" />,
  Heart: <Heart className="h-5 w-5" />,
  FolderKanban: <FolderKanban className="h-5 w-5" />,
  FileText: <FileText className="h-5 w-5" />,
  Type: <Type className="h-5 w-5" />,
  Package: <Package className="h-5 w-5" />,
}

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
            <div className="mt-6 space-y-2">
              {PAGE_ROUTES.map((route) => (
                <Link
                  key={route.path}
                  to={route.path}
                  className={`flex items-center gap-3 w-full p-3 text-left rounded-md transition-colors ${
                    location.pathname === route.path ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
                  }`}
                  onClick={() => setOpen(false)}
                >
                  {route.icon && iconMap[route.icon]}
                  <span>{route.label || route.name}</span>
                </Link>
              ))}
            </div>
          </SheetContent>
        </Sheet>
      </div>

      {/* 主内容区域 - 添加溢出控制防止图表超出屏幕 */}
      <div className="p-4 overflow-x-hidden max-w-full">
        <div className="flex flex-col gap-4 w-full max-w-full">{children}</div>
      </div>
    </div>
  )
}

export default MobileNav

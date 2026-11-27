import React from 'react'
import {
  Activity,
  BookOpen,
  Compass,
  HardDrive,
  Heart,
  Home,
  Library,
  MessageCircle,
  Package,
  RefreshCw,
  Wallet,
  type LucideIcon,
} from 'lucide-react'

export type NavSection = 'main' | 'system'

/**
 * 页面路由配置 — 唯一配置源（路由 + 侧边栏 + 移动端抽屉共享）
 *
 * `icon` 直接约束为 `LucideIcon` 组件引用，编译期即可确保新增页面不会遗漏图标，
 * 避免 pagebar / mobile_nav 各自维护易漏配的字符串 iconMap。
 */
export interface PageRoute {
  name: string
  path: string
  label: string
  icon: LucideIcon
  section?: NavSection
  component: React.LazyExoticComponent<React.FC>
}

export const PAGE_ROUTES: PageRoute[] = [
  { name: 'Main', path: '/main', label: '首页', icon: Home, section: 'main', component: React.lazy(() => import('@pages/main')) },
  { name: 'Money', path: '/money', label: '财务', icon: Wallet, section: 'main', component: React.lazy(() => import('@pages/money')) },
  { name: 'Health', path: '/health', label: '健康', icon: Heart, section: 'main', component: React.lazy(() => import('@pages/health')) },
  { name: 'Tick', path: '/tick', label: '教练', icon: MessageCircle, section: 'main', component: React.lazy(() => import('@pages/tick')) },
  { name: 'Rhythm', path: '/rhythm', label: '节奏', icon: RefreshCw, section: 'main', component: React.lazy(() => import('@pages/rhythm')) },
  { name: 'Text', path: '/text', label: '阅读库', icon: Library, section: 'main', component: React.lazy(() => import('@pages/text')) },
  { name: 'Topics', path: '/topics', label: '专题', icon: Compass, section: 'main', component: React.lazy(() => import('@pages/topics')) },
  { name: 'Necessity', path: '/necessity', label: '物资', icon: Package, section: 'main', component: React.lazy(() => import('@pages/necessity')) },
  { name: 'FileStorage', path: '/file-storage', label: '文件存储', icon: HardDrive, section: 'main', component: React.lazy(() => import('@pages/file_storage')) },
  { name: 'Blog', path: '/blog', label: '博客', icon: BookOpen, section: 'main', component: React.lazy(() => import('@pages/blog')) },
  // 底部系统可观测与调试专区
  { name: 'TraceDebug', path: '/trace-debug', label: 'Trace Debug', icon: Activity, section: 'system', component: React.lazy(() => import('@pages/trace_debug')) },
]

export const MAIN_ROUTES: PageRoute[] = PAGE_ROUTES.filter((r) => (r.section ?? 'main') === 'main')
export const SYSTEM_ROUTES: PageRoute[] = PAGE_ROUTES.filter((r) => r.section === 'system')

export const getPageComponent = (path: string): React.LazyExoticComponent<React.FC> | undefined => {
  return PAGE_ROUTES.find((route) => route.path === path)?.component
}

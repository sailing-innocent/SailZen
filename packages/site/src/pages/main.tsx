import React from 'react'
import PageLayout from '@components/page_layout'
import ReminderTodoList from '@components/reminder_todo_list'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useServerStore } from '@lib/store/'
import { useIsMobile } from '@/hooks/use-mobile'
import {
  Wallet,
  Heart,
  FolderKanban,
  Activity,
} from 'lucide-react'

const MainPage = () => {
  const serverHealth = useServerStore((state) => state.serverHealth)
  const isMobile = useIsMobile()

  // Format current date
  const formatDate = () => {
    return new Date().toLocaleDateString('zh-CN', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  return (
    <PageLayout>
      <div className={`space-y-6 ${isMobile ? 'p-4' : 'p-6'}`}>
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className={`font-bold ${isMobile ? 'text-xl' : 'text-2xl'}`}>
              欢迎回来
            </h1>
            <p className="text-muted-foreground text-sm">
              {formatDate()}
            </p>
          </div>
          <Badge variant={serverHealth ? 'default' : 'destructive'}>
            <Activity className="h-3 w-3 mr-1" />
            {serverHealth ? '服务正常' : '服务异常'}
          </Badge>
        </div>

        {/* Main Content Grid */}
        <div className={`grid gap-6 ${isMobile ? 'grid-cols-1' : 'md:grid-cols-3'}`}>
          {/* TODO List - takes 2 columns on desktop */}
          <div className={isMobile ? '' : 'md:col-span-2'}>
            <ReminderTodoList
              title="待办任务"
              showFilters={true}
            />
          </div>

          {/* Sidebar - quick access and overview */}
          <div className="space-y-4">
            {/* Quick Access */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">快捷入口</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-3 gap-2">
                <QuickAccessCard
                  icon={<Wallet className="h-5 w-5" />}
                  label="财务"
                  href="/money"
                  color="text-green-600"
                />
                <QuickAccessCard
                  icon={<Heart className="h-5 w-5" />}
                  label="健康"
                  href="/health"
                  color="text-red-500"
                />
                <QuickAccessCard
                  icon={<FolderKanban className="h-5 w-5" />}
                  label="项目"
                  href="/project"
                  color="text-blue-600"
                />
              </CardContent>
            </Card>

            {/* Tips Card */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">使用提示</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="text-sm text-muted-foreground space-y-2">
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    <span>点击任务左侧复选框可快速完成任务</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    <span>红色边框表示任务紧急或已逾期</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    <span>点击延期可推迟任务截止日期</span>
                  </li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}

interface QuickAccessCardProps {
  icon: React.ReactNode
  label: string
  href: string
  color?: string
}

const QuickAccessCard: React.FC<QuickAccessCardProps> = ({
  icon,
  label,
  href,
  color = 'text-primary',
}) => {
  return (
    <a
      href={href}
      className="flex flex-col items-center justify-center p-3 rounded-lg border hover:bg-accent transition-colors"
    >
      <span className={color}>{icon}</span>
      <span className="mt-1 text-xs">{label}</span>
    </a>
  )
}

export default MainPage

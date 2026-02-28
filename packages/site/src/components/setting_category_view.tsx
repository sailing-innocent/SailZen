/**
 * @file setting_category_view.tsx
 * @brief Setting Category View Component
 * @author sailing-innocent
 * @date 2025-03-01
 */

import { useState, useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Input } from '@components/ui/input'
import { Button } from '@components/ui/button'
import { Badge } from '@components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@components/ui/tabs'
import {
  Box,
  MapPin,
  Building,
  Lightbulb,
  Zap,
  PawPrint,
  Calendar,
  Search,
  Settings,
} from 'lucide-react'
import type { Setting, SettingType } from '@lib/data/analysis'

interface SettingCategoryViewProps {
  settings: Setting[]
  selectedSettingId?: string
  onSelectSetting: (setting: Setting) => void
  isLoading?: boolean
}

const settingTypeConfig: Record<SettingType, { label: string; icon: React.ElementType; color: string }> = {
  item: { label: '物品', icon: Box, color: 'bg-blue-500' },
  location: { label: '地点', icon: MapPin, color: 'bg-green-500' },
  organization: { label: '组织', icon: Building, color: 'bg-purple-500' },
  concept: { label: '概念', icon: Lightbulb, color: 'bg-yellow-500' },
  magic_system: { label: '能力体系', icon: Zap, color: 'bg-orange-500' },
  creature: { label: '生物', icon: PawPrint, color: 'bg-pink-500' },
  event_type: { label: '事件类型', icon: Calendar, color: 'bg-cyan-500' },
}

const importanceColors: Record<string, string> = {
  critical: 'bg-red-500',
  major: 'bg-orange-500',
  minor: 'bg-blue-500',
  background: 'bg-gray-500',
}

const importanceLabels: Record<string, string> = {
  critical: '核心',
  major: '重要',
  minor: '次要',
  background: '背景',
}

export function SettingCategoryView({
  settings,
  selectedSettingId,
  onSelectSetting,
  isLoading = false,
}: SettingCategoryViewProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState<SettingType | 'all'>('all')

  const filteredSettings = useMemo(() => {
    let result = [...settings]

    // 按类型过滤
    if (activeTab !== 'all') {
      result = result.filter((s) => s.setting_type === activeTab)
    }

    // 搜索过滤
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(
        (s) =>
          s.canonical_name.toLowerCase().includes(query) ||
          s.description?.toLowerCase().includes(query) ||
          s.category?.toLowerCase().includes(query)
      )
    }

    // 按重要性排序
    const importanceOrder = { critical: 0, major: 1, minor: 2, background: 3 }
    result.sort((a, b) => importanceOrder[a.importance] - importanceOrder[b.importance])

    return result
  }, [settings, activeTab, searchQuery])

  const groupedByType = useMemo(() => {
    const groups: Record<string, Setting[]> = {}
    settings.forEach((setting) => {
      if (!groups[setting.setting_type]) {
        groups[setting.setting_type] = []
      }
      groups[setting.setting_type].push(setting)
    })
    return groups
  }, [settings])

  if (isLoading) {
    return (
      <Card className="w-full h-full">
        <CardContent className="flex items-center justify-center h-64">
          <div className="w-8 h-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="w-full h-full flex flex-col">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Settings className="w-5 h-5" />
          设定分类
          <Badge variant="secondary">{settings.length}</Badge>
        </CardTitle>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col gap-4 overflow-hidden">
        {/* 搜索 */}
        <div className="relative">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="搜索设定..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8"
          />
        </div>

        {/* 类型标签页 */}
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as SettingType | 'all')}>
          <TabsList className="grid grid-cols-4 lg:grid-cols-8">
            <TabsTrigger value="all">
              全部
              <Badge variant="secondary" className="ml-1 text-xs">
                {settings.length}
              </Badge>
            </TabsTrigger>
            {Object.entries(settingTypeConfig).map(([type, config]) => (
              <TabsTrigger key={type} value={type} className="hidden lg:flex">
                <config.icon className="w-4 h-4 mr-1" />
                {config.label}
                <Badge variant="secondary" className="ml-1 text-xs">
                  {groupedByType[type]?.length || 0}
                </Badge>
              </TabsTrigger>
            ))}
          </TabsList>

          {/* 移动端类型选择 */}
          <div className="lg:hidden flex flex-wrap gap-2 mt-2">
            {Object.entries(settingTypeConfig).map(([type, config]) => (
              <Button
                key={type}
                variant={activeTab === type ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveTab(type as SettingType)}
              >
                <config.icon className="w-3 h-3 mr-1" />
                {config.label}
                <Badge variant="secondary" className="ml-1 text-xs">
                  {groupedByType[type]?.length || 0}
                </Badge>
              </Button>
            ))}
          </div>

          <TabsContent value={activeTab} className="mt-4">
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {filteredSettings.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Settings className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>没有找到设定</p>
                </div>
              ) : (
                filteredSettings.map((setting) => {
                  const typeConfig = settingTypeConfig[setting.setting_type]
                  const TypeIcon = typeConfig.icon

                  return (
                    <div
                      key={setting.id}
                      onClick={() => onSelectSetting(setting)}
                      className={`
                        group flex items-center gap-3 p-3 rounded-lg cursor-pointer
                        transition-colors hover:bg-accent
                        ${selectedSettingId === setting.id ? 'bg-accent border border-accent-foreground/20' : 'border border-transparent'}
                      `}
                    >
                      {/* 类型图标 */}
                      <div
                        className={`
                          w-10 h-10 rounded-lg flex items-center justify-center text-white
                          ${typeConfig.color}
                        `}
                      >
                        <TypeIcon className="w-5 h-5" />
                      </div>

                      {/* 设定信息 */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">
                            {setting.canonical_name}
                          </span>
                          <Badge
                            className={`text-xs text-white ${importanceColors[setting.importance]}`}
                          >
                            {importanceLabels[setting.importance]}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <span>{typeConfig.label}</span>
                          {setting.category && (
                            <>
                              <span>·</span>
                              <span>{setting.category}</span>
                            </>
                          )}
                        </div>
                        {setting.description && (
                          <p className="text-sm text-muted-foreground mt-1 line-clamp-1">
                            {setting.description}
                          </p>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

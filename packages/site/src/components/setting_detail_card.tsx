/**
 * @file setting_detail_card.tsx
 * @brief Setting Detail Card Component
 * @author sailing-innocent
 * @date 2025-03-01
 */

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@components/ui/button'
import { Badge } from '@components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@components/ui/tabs'
import { Separator } from '@components/ui/separator'
import {
  Box,
  MapPin,
  Building,
  Lightbulb,
  Zap,
  PawPrint,
  Calendar,
  Settings,
  Tag,
  Link2,
  BookOpen,
} from 'lucide-react'
import type { Setting, SettingDetail } from '@lib/data/analysis'

interface SettingDetailCardProps {
  setting: Setting | null
  detail: SettingDetail | null
  isLoading?: boolean
}

const settingTypeConfig: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  item: { label: '物品', icon: Box, color: 'bg-blue-500' },
  location: { label: '地点', icon: MapPin, color: 'bg-green-500' },
  organization: { label: '组织', icon: Building, color: 'bg-purple-500' },
  concept: { label: '概念', icon: Lightbulb, color: 'bg-yellow-500' },
  magic_system: { label: '能力体系', icon: Zap, color: 'bg-orange-500' },
  creature: { label: '生物', icon: PawPrint, color: 'bg-pink-500' },
  event_type: { label: '事件类型', icon: Calendar, color: 'bg-cyan-500' },
}

const importanceConfig: Record<string, { label: string; color: string }> = {
  critical: { label: '核心', color: 'bg-red-500' },
  major: { label: '重要', color: 'bg-orange-500' },
  minor: { label: '次要', color: 'bg-blue-500' },
  background: { label: '背景', color: 'bg-gray-500' },
}

export function SettingDetailCard({
  setting,
  detail,
  isLoading = false,
}: SettingDetailCardProps) {
  const [activeTab, setActiveTab] = useState('overview')

  if (isLoading) {
    return (
      <Card className="w-full h-full">
        <CardContent className="flex items-center justify-center h-64">
          <div className="w-8 h-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </CardContent>
      </Card>
    )
  }

  if (!setting) {
    return (
      <Card className="w-full h-full">
        <CardContent className="flex flex-col items-center justify-center h-64 text-muted-foreground">
          <Settings className="w-16 h-16 mb-4 opacity-50" />
          <p>选择一个设定查看详情</p>
        </CardContent>
      </Card>
    )
  }

  const typeConfig = settingTypeConfig[setting.setting_type] || settingTypeConfig.item
  const importanceConfig_item = importanceConfig[setting.importance] || importanceConfig.minor
  const TypeIcon = typeConfig.icon

  return (
    <Card className="w-full h-full flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-start gap-4">
          <div
            className={`
              w-14 h-14 rounded-xl flex items-center justify-center text-white
              ${typeConfig.color}
            `}
          >
            <TypeIcon className="w-7 h-7" />
          </div>
          <div className="flex-1 min-w-0">
            <CardTitle className="text-xl flex items-center gap-2 flex-wrap">
              <span className="truncate">{setting.canonical_name}</span>
              <Badge className={`text-white ${importanceConfig_item.color}`}>
                {importanceConfig_item.label}
              </Badge>
            </CardTitle>
            <div className="flex items-center gap-2 text-sm text-muted-foreground mt-1">
              <span>{typeConfig.label}</span>
              {setting.category && (
                <>
                  <span>·</span>
                  <Badge variant="secondary" className="text-xs">
                    {setting.category}
                  </Badge>
                </>
              )}
            </div>
          </div>
        </div>

        {setting.description && (
          <p className="text-sm text-muted-foreground mt-3">
            {setting.description}
          </p>
        )}
      </CardHeader>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
        <TabsList className="mx-6">
          <TabsTrigger value="overview">
            <BookOpen className="w-4 h-4 mr-2" />
            概览
          </TabsTrigger>
          <TabsTrigger value="attributes">
            <Tag className="w-4 h-4 mr-2" />
            属性 ({detail?.attributes?.length || 0})
          </TabsTrigger>
          <TabsTrigger value="relations">
            <Link2 className="w-4 h-4 mr-2" />
            关联 ({detail?.related_settings?.length || 0})
          </TabsTrigger>
        </TabsList>

        <CardContent className="flex-1 overflow-y-auto pt-4">
          <TabsContent value="overview" className="mt-0 space-y-4">
            {/* 基本信息 */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium">基本信息</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">标准名称:</span>
                  <p>{setting.canonical_name}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">设定类型:</span>
                  <p>{typeConfig.label}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">重要性:</span>
                  <p>{importanceConfig_item.label}</p>
                </div>
                {setting.category && (
                  <div>
                    <span className="text-muted-foreground">子分类:</span>
                    <p>{setting.category}</p>
                  </div>
                )}
              </div>
            </div>

            <Separator />

            {/* 统计信息 */}
            {detail?.stats && (
              <div className="space-y-3">
                <h4 className="text-sm font-medium">统计信息</h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-3 rounded-lg bg-accent/50 text-center">
                    <p className="text-2xl font-bold">{detail.stats.mention_count || 0}</p>
                    <p className="text-xs text-muted-foreground">提及次数</p>
                  </div>
                  <div className="p-3 rounded-lg bg-accent/50 text-center">
                    <p className="text-2xl font-bold">{detail.related_characters?.length || 0}</p>
                    <p className="text-xs text-muted-foreground">关联人物</p>
                  </div>
                  <div className="p-3 rounded-lg bg-accent/50 text-center">
                    <p className="text-2xl font-bold">{detail.related_settings?.length || 0}</p>
                    <p className="text-xs text-muted-foreground">关联设定</p>
                  </div>
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="attributes" className="mt-0">
            {!detail?.attributes || detail.attributes.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Tag className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>暂无属性信息</p>
              </div>
            ) : (
              <div className="space-y-2">
                {detail.attributes.map((attr) => (
                  <div
                    key={attr.id}
                    className="flex items-start justify-between p-3 rounded-lg border hover:bg-accent/30 transition-colors"
                  >
                    <div>
                      <p className="text-sm font-medium">{attr.attr_key}</p>
                      <p className="text-sm text-muted-foreground">{attr.attr_value}</p>
                      {attr.description && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {attr.description}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="relations" className="mt-0">
            {!detail?.related_settings || detail.related_settings.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Link2 className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>暂无关联设定</p>
              </div>
            ) : (
              <div className="space-y-2">
                {detail.related_settings.map((rel) => (
                  <div
                    key={rel.id}
                    className="flex items-center gap-3 p-3 rounded-lg border hover:bg-accent/30 transition-colors"
                  >
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                      <Link2 className="w-4 h-4" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium">{rel.relation_type}</p>
                      {rel.description && (
                        <p className="text-sm text-muted-foreground">
                          {rel.description}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </CardContent>
      </Tabs>
    </Card>
  )
}

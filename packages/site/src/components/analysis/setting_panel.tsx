/**
 * @file setting_panel.tsx
 * @brief Setting Management Panel
 * @author sailing-innocent
 * @date 2025-02-01
 */

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  api_get_settings_by_edition,
  api_create_setting,
  api_delete_setting,
  api_get_setting_detail,
  api_get_setting_types,
  api_add_setting_attribute,
  api_delete_setting_attribute,
} from '@lib/api/analysis'
import type { Setting, SettingDetail, SettingType } from '@lib/data/analysis'

interface SettingPanelProps {
  editionId: number
}

const SETTING_TYPE_LABELS: Record<SettingType, string> = {
  item: '物品',
  location: '地点',
  organization: '组织',
  concept: '概念',
  magic_system: '力量体系',
  creature: '生物',
  event_type: '事件类型',
}

const IMPORTANCE_LABELS: Record<string, string> = {
  critical: '关键',
  major: '主要',
  normal: '普通',
  minor: '次要',
}

export default function SettingPanel({ editionId }: SettingPanelProps) {
  const [settings, setSettings] = useState<Setting[]>([])
  const [typeStats, setTypeStats] = useState<{ type: string; count: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeType, setActiveType] = useState<string>('all')
  const [searchKeyword, setSearchKeyword] = useState('')
  const [selectedSetting, setSelectedSetting] = useState<Setting | null>(null)
  const [settingDetail, setSettingDetail] = useState<SettingDetail | null>(null)

  // Create dialog state
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [newSetting, setNewSetting] = useState({
    setting_type: 'item' as SettingType,
    canonical_name: '',
    category: '',
    description: '',
    importance: 'normal',
  })

  const fetchSettings = async () => {
    setLoading(true)
    setError(null)
    try {
      const settingType = activeType === 'all' ? undefined : activeType
      const result = await api_get_settings_by_edition(editionId, settingType)
      
      // Handle backend response format: {success: true, data: [...]}
      const settingList = result.data || result || []
      
      const filtered = searchKeyword
        ? settingList.filter((s: Setting) => s.canonical_name.toLowerCase().includes(searchKeyword.toLowerCase()))
        : settingList
      
      setSettings(filtered)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchTypeStats = async () => {
    try {
      const result = await api_get_setting_types()
      // API returns { types: SettingType[], labels: Record<SettingType, string> }
      // Convert to array format for UI
      const statsArray = result.types.map(type => ({
        type,
        count: 0 // Count will be calculated from settings data
      }))
      setTypeStats(statsArray)
    } catch (err) {
      console.error('Failed to load type stats:', err)
      // Fallback to empty array to prevent reduce error
      setTypeStats([])
    }
  }

  useEffect(() => {
    fetchSettings()
    fetchTypeStats()
  }, [editionId, activeType])

  const handleSearch = () => {
    fetchSettings()
  }

  const handleSelectSetting = async (setting: Setting) => {
    setSelectedSetting(setting)
    try {
      const detail = await api_get_setting_detail(setting.id)
      setSettingDetail(detail)
    } catch (err) {
      console.error('Failed to load detail:', err)
    }
  }

  const handleCreateSetting = async () => {
    if (!newSetting.canonical_name.trim()) return

    try {
      const created = await api_create_setting({
        edition_id: editionId,
        setting_type: newSetting.setting_type,
        canonical_name: newSetting.canonical_name,
        category: newSetting.category || undefined,
        description: newSetting.description || undefined,
        importance: newSetting.importance,
      })
      setSettings([created, ...settings])
      setCreateDialogOpen(false)
      setNewSetting({
        setting_type: 'item',
        canonical_name: '',
        category: '',
        description: '',
        importance: 'normal',
      })
      fetchTypeStats()
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败')
    }
  }

  const handleDeleteSetting = async (setting: Setting) => {
    if (!confirm(`确定要删除「${setting.canonical_name}」吗？`)) return

    try {
      await api_delete_setting(setting.id)
      setSettings(settings.filter(s => s.id !== setting.id))
      if (selectedSetting?.id === setting.id) {
        setSelectedSetting(null)
        setSettingDetail(null)
      }
      fetchTypeStats()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex gap-2">
          <Skeleton className="h-10 flex-1" />
          <Skeleton className="h-10 w-24" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      </div>
    )
  }

  // Show setting detail
  if (selectedSetting && settingDetail) {
    return (
      <SettingDetailCard
        detail={settingDetail}
        onBack={() => {
          setSelectedSetting(null)
          setSettingDetail(null)
        }}
        onUpdate={() => {
          fetchSettings()
          handleSelectSetting(selectedSetting)
        }}
      />
    )
  }

  return (
    <div className="space-y-4">
      {/* Type Tabs */}
      <Tabs value={activeType} onValueChange={setActiveType}>
        <TabsList className="flex-wrap h-auto">
          <TabsTrigger value="all">
            全部 ({typeStats.reduce((a, b) => a + b.count, 0)})
          </TabsTrigger>
          {typeStats.map(({ type, count }) => (
            <TabsTrigger key={type} value={type}>
              {SETTING_TYPE_LABELS[type as SettingType] || type} ({count})
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Toolbar */}
      <div className="flex flex-wrap gap-2">
        <Input
          placeholder="搜索设定..."
          value={searchKeyword}
          onChange={(e) => setSearchKeyword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="flex-1 min-w-48"
        />
        <Button variant="outline" onClick={handleSearch}>搜索</Button>
        
        {/* Create Dialog */}
        <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button>新增设定</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新增设定</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>设定类型</Label>
                <Select
                  value={newSetting.setting_type}
                  onValueChange={(v) => setNewSetting({ ...newSetting, setting_type: v as SettingType })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(SETTING_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>名称</Label>
                <Input
                  value={newSetting.canonical_name}
                  onChange={(e) => setNewSetting({ ...newSetting, canonical_name: e.target.value })}
                  placeholder="设定名称"
                />
              </div>
              <div className="space-y-2">
                <Label>分类（可选）</Label>
                <Input
                  value={newSetting.category}
                  onChange={(e) => setNewSetting({ ...newSetting, category: e.target.value })}
                  placeholder="如：武器、防具、消耗品"
                />
              </div>
              <div className="space-y-2">
                <Label>重要程度</Label>
                <Select
                  value={newSetting.importance}
                  onValueChange={(v) => setNewSetting({ ...newSetting, importance: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(IMPORTANCE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>描述</Label>
                <Textarea
                  value={newSetting.description}
                  onChange={(e) => setNewSetting({ ...newSetting, description: e.target.value })}
                  placeholder="设定描述（可选）"
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>取消</Button>
              <Button onClick={handleCreateSetting}>创建</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Error message */}
      {error && (
        <div className="text-sm text-red-500 p-2 bg-red-50 rounded">{error}</div>
      )}

      {/* Setting List */}
      {settings.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          暂无设定，点击「新增设定」开始创建
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {settings.map((setting) => (
            <Card
              key={setting.id}
              className="cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => handleSelectSetting(setting)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-base">{setting.canonical_name}</CardTitle>
                    {setting.category && (
                      <span className="text-xs text-muted-foreground">{setting.category}</span>
                    )}
                  </div>
                  <div className="flex gap-1">
                    <Badge variant="outline">
                      {SETTING_TYPE_LABELS[setting.setting_type as SettingType] || setting.setting_type}
                    </Badge>
                    <Badge variant="secondary">
                      {IMPORTANCE_LABELS[setting.importance] || setting.importance}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {setting.description && (
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-2">
                    {setting.description}
                  </p>
                )}
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{setting.attribute_count} 属性</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-500 hover:text-red-700 h-6 px-2"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteSetting(setting)
                    }}
                  >
                    删除
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

// Setting Detail Card Component
interface SettingDetailCardProps {
  detail: SettingDetail
  onBack: () => void
  onUpdate: () => void
}

function SettingDetailCard({ detail, onBack, onUpdate }: SettingDetailCardProps) {
  const [addAttrOpen, setAddAttrOpen] = useState(false)
  const [newAttr, setNewAttr] = useState({ key: '', value: '' })

  const handleAddAttribute = async () => {
    if (!newAttr.key.trim()) return
    try {
      await api_add_setting_attribute(detail.setting.id, newAttr.key, newAttr.value)
      setAddAttrOpen(false)
      setNewAttr({ key: '', value: '' })
      onUpdate()
    } catch (err) {
      console.error('Failed to add attribute:', err)
    }
  }

  const handleRemoveAttribute = async (attrId: number) => {
    try {
      await api_delete_setting_attribute(attrId)
      onUpdate()
    } catch (err) {
      console.error('Failed to remove attribute:', err)
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={onBack}>← 返回</Button>
          <h2 className="text-xl font-bold">{detail.setting.canonical_name}</h2>
          <Badge variant="outline">
            {SETTING_TYPE_LABELS[detail.setting.setting_type as SettingType]}
          </Badge>
          {detail.setting.category && (
            <Badge variant="secondary">{detail.setting.category}</Badge>
          )}
        </div>
      </div>

      {/* Description */}
      {detail.setting.description && (
        <Card>
          <CardContent className="pt-4">
            <p className="text-muted-foreground">{detail.setting.description}</p>
          </CardContent>
        </Card>
      )}

      {/* Attributes */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">属性</CardTitle>
            <Dialog open={addAttrOpen} onOpenChange={setAddAttrOpen}>
              <DialogTrigger asChild>
                <Button size="sm">添加属性</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>添加属性</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label>属性名</Label>
                    <Input
                      value={newAttr.key}
                      onChange={(e) => setNewAttr({ ...newAttr, key: e.target.value })}
                      placeholder="如：等级、效果、材料"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>属性值</Label>
                    <Input
                      value={newAttr.value}
                      onChange={(e) => setNewAttr({ ...newAttr, value: e.target.value })}
                      placeholder="属性值"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setAddAttrOpen(false)}>取消</Button>
                  <Button onClick={handleAddAttribute}>添加</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </CardHeader>
        <CardContent>
          {detail.attributes.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">暂无属性</p>
          ) : (
            <div className="space-y-2">
              {detail.attributes.map((attr) => (
                <div key={attr.id} className="flex items-center justify-between text-sm py-1 px-2 rounded hover:bg-muted/50">
                  <span>
                    <span className="font-medium">{attr.attr_key}：</span>
                    <span className="text-muted-foreground">{String(attr.attr_value)}</span>
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-red-500 hover:text-red-700"
                    onClick={() => handleRemoveAttribute(attr.id)}
                  >
                    删除
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Character Links */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">关联人物</CardTitle>
        </CardHeader>
        <CardContent>
          {detail.character_links.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">暂无关联人物</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {detail.character_links.map((link) => (
                <Badge key={link.id} variant="secondary">
                  {link.character_name} ({link.link_type})
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

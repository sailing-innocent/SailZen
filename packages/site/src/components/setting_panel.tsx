/**
 * @file setting_panel.tsx
 * @brief Setting Management Panel
 * @author sailing-innocent
 * @date 2025-03-01
 */

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@components/ui/tabs'
import { Badge } from '@components/ui/badge'
import { Alert, AlertDescription } from '@components/ui/alert'
import { Separator } from '@components/ui/separator'
import {
  Settings,
  Sparkles,
  AlertCircle,
  RefreshCw,
  CheckCircle,
  Network,
} from 'lucide-react'
import { SettingCategoryView } from './setting_category_view'
import { SettingDetailCard } from './setting_detail_card'
import { SettingExtractionConfigPanel } from './setting_extraction_config'
import { SettingRelationGraph } from './setting_relation_graph'
import {
  api_get_settings_by_edition,
  api_get_setting_detail,
  api_create_setting,
  api_delete_setting,
} from '@lib/api/analysis'
import {
  api_create_setting_extraction,
  api_preview_setting_extraction,
  api_save_setting_extraction_result,
  api_get_setting_relations,
} from '@lib/api/setting_extraction'
import type {
  Setting,
  SettingDetail,
  SettingExtractionConfig,
  TextRangeSelection,
} from '@lib/data/analysis'

interface SettingPanelProps {
  editionId: number
  workTitle?: string
  rangeSelection?: TextRangeSelection
}

export function SettingPanel({
  editionId,
  workTitle = '',
  rangeSelection,
}: SettingPanelProps) {
  const [activeTab, setActiveTab] = useState('list')
  const [settings, setSettings] = useState<Setting[]>([])
  const [selectedSetting, setSelectedSetting] = useState<Setting | null>(null)
  const [settingDetail, setSettingDetail] = useState<SettingDetail | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isExtracting, setIsExtracting] = useState(false)
  const [extractionResult, setExtractionResult] = useState<any>(null)
  const [graphData, setGraphData] = useState<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] })
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const [extractionConfig, setExtractionConfig] = useState<SettingExtractionConfig>({
    setting_types: ['item', 'location', 'organization', 'concept', 'magic_system', 'creature', 'event_type'],
    min_importance: 'background',
    extract_relations: true,
    extract_attributes: true,
    max_settings: 100,
    temperature: 0.3,
    prompt_template_id: 'setting_extraction_v1',
  })

  // 加载设定列表
  const loadSettings = useCallback(async () => {
    if (!editionId) return
    
    setIsLoading(true)
    setError(null)
    
    try {
      const data = await api_get_settings_by_edition(editionId)
      setSettings(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载设定列表失败')
    } finally {
      setIsLoading(false)
    }
  }, [editionId])

  // 加载设定详情
  const loadSettingDetail = useCallback(async (settingId: string) => {
    setIsLoading(true)
    setError(null)
    
    try {
      const detail = await api_get_setting_detail(settingId)
      setSettingDetail(detail)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载设定详情失败')
    } finally {
      setIsLoading(false)
    }
  }, [])

  // 加载关系图数据
  const loadGraphData = useCallback(async () => {
    if (!editionId) return
    
    try {
      const data = await api_get_setting_relations(editionId)
      if (data.success) {
        setGraphData({
          nodes: data.nodes || [],
          edges: data.edges || [],
        })
      }
    } catch (err) {
      console.error('Failed to load graph data:', err)
    }
  }, [editionId])

  // 初始加载
  useEffect(() => {
    loadSettings()
    loadGraphData()
  }, [loadSettings, loadGraphData])

  // 选择设定时加载详情
  useEffect(() => {
    if (selectedSetting) {
      loadSettingDetail(selectedSetting.id)
    } else {
      setSettingDetail(null)
    }
  }, [selectedSetting, loadSettingDetail])

  // 执行设定提取
  const handleStartExtraction = async () => {
    if (!editionId || !rangeSelection) {
      setError('请先选择文本范围')
      return
    }

    setIsExtracting(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const result = await api_create_setting_extraction({
        edition_id: editionId,
        range_selection: rangeSelection,
        config: extractionConfig,
        work_title: workTitle,
      })

      if (result.success && result.result) {
        setExtractionResult(result.result)
        setSuccessMessage(`提取到 ${result.result.settings.length} 个设定`)
        setActiveTab('extracted')
      } else {
        setError(result.error || '提取失败')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '提取失败')
    } finally {
      setIsExtracting(false)
    }
  }

  // 预览提取
  const handlePreview = async () => {
    if (!editionId) {
      setError('缺少版本ID')
      return
    }

    setIsExtracting(true)
    setError(null)

    try {
      const result = await api_preview_setting_extraction({
        edition_id: editionId,
        chapter_count: 3,
        work_title: workTitle,
      })

      if (result.success) {
        setExtractionResult(result)
        setSuccessMessage(`预览完成，发现 ${result.total_detected} 个设定`)
        setActiveTab('extracted')
      } else {
        setError(result.error || '预览失败')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '预览失败')
    } finally {
      setIsExtracting(false)
    }
  }

  // 保存提取结果
  const handleSaveExtractionResult = async () => {
    if (!extractionResult || !editionId) return

    setIsLoading(true)
    setError(null)

    try {
      const settingsToSave = extractionResult.settings?.map((s: any) => ({
        ...s,
        edition_id: editionId,
      })) || extractionResult.preview_settings?.map((s: any) => ({
        ...s,
        edition_id: editionId,
      }))

      const result = await api_save_setting_extraction_result({
        settings: settingsToSave,
        edition_id: editionId,
      })

      if (result.success) {
        setSuccessMessage(`成功保存 ${result.saved_count} 个设定`)
        loadSettings()
        loadGraphData()
        setActiveTab('list')
      } else {
        setError(result.error || '保存失败')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    } finally {
      setIsLoading(false)
    }
  }

  // 删除设定
  const handleDeleteSetting = async (settingId: string) => {
    if (!confirm('确定要删除这个设定吗？')) return

    setIsLoading(true)
    setError(null)

    try {
      await api_delete_setting(settingId)
      setSuccessMessage('设定已删除')
      loadSettings()
      loadGraphData()
      if (selectedSetting?.id === settingId) {
        setSelectedSetting(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* 消息提示 */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {successMessage && (
        <Alert className="bg-green-50 border-green-200">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">{successMessage}</AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="list">
            <Settings className="w-4 h-4 mr-2" />
            设定列表 ({settings.length})
          </TabsTrigger>
          <TabsTrigger value="extract">
            <Sparkles className="w-4 h-4 mr-2" />
            AI 提取
          </TabsTrigger>
          <TabsTrigger value="extracted" disabled={!extractionResult}>
            <CheckCircle className="w-4 h-4 mr-2" />
            提取结果
          </TabsTrigger>
          <TabsTrigger value="graph">
            <Network className="w-4 h-4 mr-2" />
            关系图
          </TabsTrigger>
        </TabsList>

        <TabsContent value="list" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SettingCategoryView
              settings={settings}
              selectedSettingId={selectedSetting?.id}
              onSelectSetting={setSelectedSetting}
              isLoading={isLoading}
            />
            <SettingDetailCard
              setting={selectedSetting}
              detail={settingDetail}
              isLoading={isLoading}
            />
          </div>
        </TabsContent>

        <TabsContent value="extract">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SettingExtractionConfigPanel
              config={extractionConfig}
              onConfigChange={setExtractionConfig}
              onStartExtraction={handleStartExtraction}
              onPreview={handlePreview}
              isLoading={isExtracting}
              disabled={!editionId}
            />
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Sparkles className="w-5 h-5" />
                  使用说明
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm text-muted-foreground">
                <p>
                  <strong className="text-foreground">设定提取</strong>
                  功能使用 AI 分析选中的文本范围，自动识别其中的世界观设定元素。
                </p>
                <ul className="list-disc list-inside space-y-1">
                  <li>识别物品、地点、组织等多种设定类型</li>
                  <li>判断设定的重要性和在故事中的作用</li>
                  <li>提取设定的详细属性和特征</li>
                  <li>识别设定之间的关系（包含、属于、对立等）</li>
                  <li>记录设定的首次出现和关键使用场景</li>
                </ul>
                <Separator />
                <p>
                  <strong className="text-foreground">提示：</strong>
                  建议先使用"预览"功能查看前3章的提取结果，确认配置合适后再进行全量提取。
                </p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="extracted">
          {extractionResult && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-lg">提取结果</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    提取到 {extractionResult.settings?.length || extractionResult.total_detected || 0} 个设定
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setExtractionResult(null)}
                  >
                    取消
                  </Button>
                  <Button onClick={handleSaveExtractionResult} disabled={isLoading}>
                    {isLoading ? (
                      <>
                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        保存中...
                      </>
                    ) : (
                      <>
                        <CheckCircle className="w-4 h-4 mr-2" />
                        保存到数据库
                      </>
                    )}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {(extractionResult.settings || extractionResult.preview_settings || []).map(
                    (setting: any, index: number) => (
                      <div
                        key={index}
                        className="flex items-center justify-between p-3 rounded-lg border hover:bg-accent/50 transition-colors"
                      >
                        <div>
                          <p className="font-medium">{setting.canonical_name}</p>
                          <p className="text-sm text-muted-foreground">
                            {setting.setting_type} · {setting.importance}
                            {setting.category && ` · ${setting.category}`}
                          </p>
                          {setting.description && (
                            <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                              {setting.description}
                            </p>
                          )}
                        </div>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="graph">
          <SettingRelationGraph
            nodes={graphData.nodes}
            edges={graphData.edges}
            isLoading={isLoading}
            onNodeClick={(node) => {
              const setting = settings.find((s) => s.id === node.id.replace('setting_', ''))
              if (setting) {
                setSelectedSetting(setting)
                setActiveTab('list')
              }
            }}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}

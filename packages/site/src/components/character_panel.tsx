/**
 * @file character_panel.tsx
 * @brief Character Management Panel
 * @author sailing-innocent
 * @date 2025-03-01
 */

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@components/ui/tabs'
import { Badge } from '@components/ui/badge'
import { Separator } from '@components/ui/separator'
import { Alert, AlertDescription } from '@components/ui/alert'
import {
  Users,
  Sparkles,
  AlertCircle,
  RefreshCw,
  CheckCircle,
} from 'lucide-react'
import { CharacterList } from './character_list'
import { CharacterProfileCard } from './character_profile_card'
import { CharacterDetectionConfigPanel } from './character_detection_config'
import { CharacterAttributeEditor } from './character_attribute_editor'
import {
  api_get_characters_by_edition,
  api_get_character_profile,
  api_create_character,
  api_delete_character,
  api_add_character_attribute,
  api_delete_character_attribute,
} from '@lib/api/analysis'
import {
  api_create_character_detection,
  api_preview_character_detection,
  api_save_detection_result,
} from '@lib/api/character_detection'
import type {
  Character,
  CharacterProfile,
  CharacterDetectionConfig,
  TextRangeSelection,
} from '@lib/data/analysis'

interface CharacterPanelProps {
  editionId: number
  workTitle?: string
  rangeSelection?: TextRangeSelection
}

export function CharacterPanel({
  editionId,
  workTitle = '',
  rangeSelection,
}: CharacterPanelProps) {
  const [activeTab, setActiveTab] = useState('list')
  const [characters, setCharacters] = useState<Character[]>([])
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null)
  const [characterProfile, setCharacterProfile] = useState<CharacterProfile | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isDetecting, setIsDetecting] = useState(false)
  const [detectionResult, setDetectionResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const [detectionConfig, setDetectionConfig] = useState<CharacterDetectionConfig>({
    detect_aliases: true,
    detect_attributes: true,
    detect_relations: true,
    min_confidence: 0.5,
    max_characters: 100,
    temperature: 0.3,
    prompt_template_id: 'character_detection_v2',
  })

  // 加载人物列表
  const loadCharacters = useCallback(async () => {
    if (!editionId) return
    
    setIsLoading(true)
    setError(null)
    
    try {
      const data = await api_get_characters_by_edition(editionId)
      setCharacters(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载人物列表失败')
    } finally {
      setIsLoading(false)
    }
  }, [editionId])

  // 加载人物详情
  const loadCharacterProfile = useCallback(async (characterId: string) => {
    setIsLoading(true)
    setError(null)
    
    try {
      const profile = await api_get_character_profile(characterId)
      setCharacterProfile(profile)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载人物详情失败')
    } finally {
      setIsLoading(false)
    }
  }, [])

  // 初始加载
  useEffect(() => {
    loadCharacters()
  }, [loadCharacters])

  // 选择人物时加载详情
  useEffect(() => {
    if (selectedCharacter) {
      loadCharacterProfile(selectedCharacter.id)
    } else {
      setCharacterProfile(null)
    }
  }, [selectedCharacter, loadCharacterProfile])

  // 执行人物检测
  const handleStartDetection = async () => {
    if (!editionId || !rangeSelection) {
      setError('请先选择文本范围')
      return
    }

    setIsDetecting(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const result = await api_create_character_detection({
        edition_id: editionId,
        range_selection: rangeSelection,
        config: detectionConfig,
        work_title: workTitle,
      })

      if (result.success && result.result) {
        setDetectionResult(result.result)
        setSuccessMessage(`检测到 ${result.result.characters.length} 个人物`)
        setActiveTab('detected')
      } else {
        setError(result.error || '检测失败')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '检测失败')
    } finally {
      setIsDetecting(false)
    }
  }

  // 预览检测
  const handlePreview = async () => {
    if (!editionId) {
      setError('缺少版本ID')
      return
    }

    setIsDetecting(true)
    setError(null)

    try {
      const result = await api_preview_character_detection({
        edition_id: editionId,
        chapter_count: 3,
        work_title: workTitle,
      })

      if (result.success) {
        setDetectionResult(result)
        setSuccessMessage(`预览完成，发现 ${result.total_detected} 个人物`)
        setActiveTab('detected')
      } else {
        setError(result.error || '预览失败')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '预览失败')
    } finally {
      setIsDetecting(false)
    }
  }

  // 保存检测结果
  const handleSaveDetectionResult = async () => {
    if (!detectionResult || !editionId) return

    setIsLoading(true)
    setError(null)

    try {
      const charactersToSave = detectionResult.characters?.map((char: any) => ({
        ...char,
        edition_id: editionId,
      })) || detectionResult.preview_characters?.map((char: any) => ({
        ...char,
        edition_id: editionId,
      }))

      const result = await api_save_detection_result({
        characters: charactersToSave,
        auto_deduplicate: true,
      })

      if (result.success) {
        setSuccessMessage(`成功保存 ${result.saved_count} 个人物`)
        loadCharacters()
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

  // 删除人物
  const handleDeleteCharacter = async (characterId: string) => {
    if (!confirm('确定要删除这个人物吗？')) return

    setIsLoading(true)
    setError(null)

    try {
      await api_delete_character(characterId)
      setSuccessMessage('人物已删除')
      loadCharacters()
      if (selectedCharacter?.id === characterId) {
        setSelectedCharacter(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    } finally {
      setIsLoading(false)
    }
  }

  // 添加属性
  const handleAddAttribute = async (
    attribute: Omit<CharacterAttribute, 'id' | 'created_at' | 'updated_at'>
  ) => {
    if (!selectedCharacter) return

    try {
      await api_add_character_attribute(selectedCharacter.id, {
        ...attribute,
        character_id: selectedCharacter.id,
      })
      loadCharacterProfile(selectedCharacter.id)
      setSuccessMessage('属性已添加')
    } catch (err) {
      setError(err instanceof Error ? err.message : '添加属性失败')
    }
  }

  // 删除属性
  const handleDeleteAttribute = async (attributeId: string) => {
    if (!selectedCharacter) return

    try {
      await api_delete_character_attribute(selectedCharacter.id, attributeId)
      loadCharacterProfile(selectedCharacter.id)
      setSuccessMessage('属性已删除')
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除属性失败')
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
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="list">
            <Users className="w-4 h-4 mr-2" />
            人物列表 ({characters.length})
          </TabsTrigger>
          <TabsTrigger value="detect">
            <Sparkles className="w-4 h-4 mr-2" />
            AI 检测
          </TabsTrigger>
          <TabsTrigger value="detected" disabled={!detectionResult}>
            <CheckCircle className="w-4 h-4 mr-2" />
            检测结果
          </TabsTrigger>
        </TabsList>

        <TabsContent value="list" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <CharacterList
              characters={characters}
              selectedCharacterId={selectedCharacter?.id}
              onSelectCharacter={setSelectedCharacter}
              onDeleteCharacter={handleDeleteCharacter}
              isLoading={isLoading}
            />
            <CharacterProfileCard
              profile={characterProfile}
              isLoading={isLoading}
            />
          </div>

          {selectedCharacter && characterProfile && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">属性编辑</CardTitle>
              </CardHeader>
              <CardContent>
                <CharacterAttributeEditor
                  attributes={characterProfile.attributes}
                  onAddAttribute={handleAddAttribute}
                  onUpdateAttribute={async (id, updates) => {
                    // TODO: 实现更新属性API
                  }}
                  onDeleteAttribute={handleDeleteAttribute}
                />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="detect">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <CharacterDetectionConfigPanel
              config={detectionConfig}
              onConfigChange={setDetectionConfig}
              onStartDetection={handleStartDetection}
              onPreview={handlePreview}
              isLoading={isDetecting}
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
                  <strong className="text-foreground">人物检测</strong>
                  功能使用 AI 分析选中的文本范围，自动识别其中的人物角色。
                </p>
                <ul className="list-disc list-inside space-y-1">
                  <li>识别所有出现的人物名称</li>
                  <li>检测人物的不同称呼形式（别名）</li>
                  <li>判断人物在故事中的重要性</li>
                  <li>提取人物的外貌、性格、能力等属性</li>
                  <li>识别人物之间的关系网络</li>
                </ul>
                <Separator />
                <p>
                  <strong className="text-foreground">提示：</strong>
                  建议先使用"预览"功能查看前3章的检测结果，确认配置合适后再进行全量检测。
                </p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="detected">
          {detectionResult && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-lg">检测结果</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    检测到 {detectionResult.characters?.length || detectionResult.total_detected || 0} 个人物
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setDetectionResult(null)}
                  >
                    取消
                  </Button>
                  <Button onClick={handleSaveDetectionResult} disabled={isLoading}>
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
                  {(detectionResult.characters || detectionResult.preview_characters || []).map(
                    (char: any, index: number) => (
                      <div
                        key={index}
                        className="flex items-center justify-between p-3 rounded-lg border hover:bg-accent/50 transition-colors"
                      >
                        <div>
                          <p className="font-medium">{char.canonical_name}</p>
                          <p className="text-sm text-muted-foreground">
                            {char.role_type} · 提及 {char.mention_count || 0} 次
                          </p>
                          {char.description && (
                            <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                              {char.description}
                            </p>
                          )}
                        </div>
                        <Badge variant="secondary">
                          {(char.role_confidence * 100).toFixed(0)}% 置信度
                        </Badge>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

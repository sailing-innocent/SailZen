/**
 * @file outline_extraction_config.tsx
 * @brief Outline Extraction Config Panel Component
 * @author sailing-innocent
 * @date 2025-02-28
 */

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { BookOpen, Settings, Sparkles, Users, Zap, Eye, Play, Brain } from 'lucide-react'
import type {
  OutlineExtractionConfig,
  OutlineGranularity,
  OutlineExtractionType,
  LLMProvider,
} from '@lib/data/analysis'

export interface OutlineExtractionConfigPanelProps {
  /** 当前配置 */
  config: OutlineExtractionConfig
  /** 配置变更回调 */
  onConfigChange: (config: OutlineExtractionConfig) => void
  /** 预览回调 */
  onPreview?: () => void
  /** 开始提取回调 */
  onStart?: () => void
  /** 是否正在处理 */
  isProcessing?: boolean
  /** 是否可编辑 */
  editable?: boolean
  /** 可用的 LLM Provider 列表 */
  providers?: LLMProvider[]
  /** 默认 Provider ID */
  defaultProvider?: string
}

const GRANULARITY_OPTIONS: { value: OutlineGranularity; label: string; description: string }[] = [
  { value: 'act', label: '幕', description: '大的故事阶段（如第一幕、第二幕）' },
  { value: 'arc', label: '弧', description: '完整的情节线（如主角成长弧）' },
  { value: 'scene', label: '场景', description: '具体的场景（推荐）' },
  { value: 'beat', label: '节拍', description: '最小的情节单位' },
]

const OUTLINE_TYPE_OPTIONS: { value: OutlineExtractionType; label: string; description: string }[] = [
  { value: 'main', label: '主线大纲', description: '故事的主要情节线' },
  { value: 'subplot', label: '支线大纲', description: '次要情节线' },
  { value: 'character_arc', label: '人物弧光', description: '人物成长变化轨迹' },
  { value: 'theme', label: '主题大纲', description: '主题发展脉络' },
]

/**
 * 大纲提取配置面板
 * 
 * 配置选项包括：
 * - 分析粒度（幕/弧/场景/节拍）
 * - 大纲类型（主线/支线/人物弧光/主题）
 * - 是否提取转折点
 * - 是否关联人物
 * - 最大节点数限制
 */
export function OutlineExtractionConfigPanel({
  config,
  onConfigChange,
  onPreview,
  onStart,
  isProcessing = false,
  editable = true,
  providers = [],
  defaultProvider,
}: OutlineExtractionConfigPanelProps) {
  const [localConfig, setLocalConfig] = useState<OutlineExtractionConfig>(config)

  // 当 defaultProvider 变化时，如果当前没有设置 llm_provider，则使用默认值
  useEffect(() => {
    if (defaultProvider && !localConfig.llm_provider) {
      const newConfig = { ...localConfig, llm_provider: defaultProvider }
      setLocalConfig(newConfig)
      onConfigChange(newConfig)
    }
  }, [defaultProvider])

  const handleChange = <K extends keyof OutlineExtractionConfig>(
    key: K,
    value: OutlineExtractionConfig[K]
  ) => {
    const newConfig = { ...localConfig, [key]: value }
    setLocalConfig(newConfig)
    onConfigChange(newConfig)
  }

  // 处理 Provider 变更
  const handleProviderChange = (providerId: string) => {
    const provider = providers.find(p => p.id === providerId)
    const newConfig = { 
      ...localConfig, 
      llm_provider: providerId,
      llm_model: provider?.default_model
    }
    setLocalConfig(newConfig)
    onConfigChange(newConfig)
  }

  const handlePreview = () => {
    onPreview?.()
  }

  const handleStart = () => {
    onStart?.()
  }

  // 获取当前选中的 Provider
  const selectedProvider = providers.find(p => p.id === localConfig.llm_provider)

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Settings className="w-5 h-5 text-primary" />
          <CardTitle className="text-lg">大纲提取配置</CardTitle>
        </div>
        <CardDescription>
          配置 AI 分析参数，从文本中提取结构化大纲
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* LLM Provider 选择 */}
        {providers.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-muted-foreground" />
              <Label className="text-sm font-medium">AI 模型</Label>
            </div>
            <Select
              value={localConfig.llm_provider || ''}
              onValueChange={handleProviderChange}
              disabled={!editable || isProcessing}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="选择 LLM Provider" />
              </SelectTrigger>
              <SelectContent>
                {providers.map((provider) => (
                  <SelectItem key={provider.id} value={provider.id}>
                    <div className="flex flex-col items-start">
                      <span>{provider.name}</span>
                      <span className="text-xs text-muted-foreground">
                        {provider.models.length} 个可用模型
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedProvider && (
              <div className="flex flex-wrap gap-1">
                {selectedProvider.models.map((model) => (
                  <Badge 
                    key={model} 
                    variant={model === selectedProvider.default_model ? "default" : "outline"}
                    className="text-xs"
                  >
                    {model}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        )}

        <Separator />

        {/* 分析粒度 */}
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-muted-foreground" />
            <Label className="text-sm font-medium">分析粒度</Label>
          </div>
          <Select
            value={localConfig.granularity}
            onValueChange={(v) => handleChange('granularity', v as OutlineGranularity)}
            disabled={!editable || isProcessing}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {GRANULARITY_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  <div className="flex flex-col items-start">
                    <span>{opt.label}</span>
                    <span className="text-xs text-muted-foreground">{opt.description}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* 大纲类型 */}
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-muted-foreground" />
            <Label className="text-sm font-medium">大纲类型</Label>
          </div>
          <Select
            value={localConfig.outline_type}
            onValueChange={(v) => handleChange('outline_type', v as OutlineExtractionType)}
            disabled={!editable || isProcessing}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {OUTLINE_TYPE_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  <div className="flex flex-col items-start">
                    <span>{opt.label}</span>
                    <span className="text-xs text-muted-foreground">{opt.description}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Separator />

        {/* 选项开关 */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-muted-foreground" />
              <div className="space-y-0.5">
                <Label className="text-sm font-medium">提取转折点</Label>
                <p className="text-xs text-muted-foreground">识别关键情节点（触发事件、高潮等）</p>
              </div>
            </div>
            <Switch
              checked={localConfig.extract_turning_points}
              onCheckedChange={(v) => handleChange('extract_turning_points', v)}
              disabled={!editable || isProcessing}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-muted-foreground" />
              <div className="space-y-0.5">
                <Label className="text-sm font-medium">关联人物</Label>
                <p className="text-xs text-muted-foreground">自动识别涉及的人物</p>
              </div>
            </div>
            <Switch
              checked={localConfig.extract_characters}
              onCheckedChange={(v) => handleChange('extract_characters', v)}
              disabled={!editable || isProcessing}
            />
          </div>
        </div>

        <Separator />

        {/* 最大节点数 */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium">最大节点数</Label>
            <Badge variant="secondary">{localConfig.max_nodes}</Badge>
          </div>
          <Slider
            value={[localConfig.max_nodes]}
            onValueChange={([v]) => handleChange('max_nodes', v)}
            min={10}
            max={100}
            step={10}
            disabled={!editable || isProcessing}
          />
          <p className="text-xs text-muted-foreground">
            限制生成的最大节点数量，避免结果过于复杂
          </p>
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-2 pt-2">
          <Button
            variant="outline"
            className="flex-1"
            onClick={handlePreview}
            disabled={isProcessing}
          >
            <Eye className="w-4 h-4 mr-2" />
            预览
          </Button>
          <Button
            className="flex-1"
            onClick={handleStart}
            disabled={isProcessing}
          >
            <Play className="w-4 h-4 mr-2" />
            {isProcessing ? '处理中...' : '开始提取'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export default OutlineExtractionConfigPanel

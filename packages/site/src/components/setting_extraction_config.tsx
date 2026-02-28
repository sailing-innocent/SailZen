/**
 * @file setting_extraction_config.tsx
 * @brief Setting Extraction Configuration Panel
 * @author sailing-innocent
 * @date 2025-03-01
 */

import { useState } from 'react'
import { Button } from '@components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Label } from '@components/ui/label'
import { Switch } from '@components/ui/switch'
import { Slider } from '@components/ui/slider'
import { Input } from '@components/ui/input'
import { Checkbox } from '@components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@components/ui/select'
import { Settings, Sparkles, MapPin, Building, Box, Lightbulb, Zap, PawPrint, Calendar } from 'lucide-react'
import type { SettingExtractionConfig } from '@lib/data/analysis'

interface SettingExtractionConfigPanelProps {
  config: SettingExtractionConfig
  onConfigChange: (config: SettingExtractionConfig) => void
  onStartExtraction: () => void
  onPreview: () => void
  isLoading?: boolean
  disabled?: boolean
}

const defaultConfig: SettingExtractionConfig = {
  setting_types: ['item', 'location', 'organization', 'concept', 'magic_system', 'creature', 'event_type'],
  min_importance: 'background',
  extract_relations: true,
  extract_attributes: true,
  max_settings: 100,
  temperature: 0.3,
  prompt_template_id: 'setting_extraction_v1',
}

const settingTypeOptions = [
  { value: 'item', label: '物品', icon: Box },
  { value: 'location', label: '地点', icon: MapPin },
  { value: 'organization', label: '组织', icon: Building },
  { value: 'concept', label: '概念', icon: Lightbulb },
  { value: 'magic_system', label: '能力体系', icon: Zap },
  { value: 'creature', label: '生物', icon: PawPrint },
  { value: 'event_type', label: '事件类型', icon: Calendar },
]

const importanceOptions = [
  { value: 'critical', label: '核心' },
  { value: 'major', label: '重要' },
  { value: 'minor', label: '次要' },
  { value: 'background', label: '背景' },
]

export function SettingExtractionConfigPanel({
  config,
  onConfigChange,
  onStartExtraction,
  onPreview,
  isLoading = false,
  disabled = false,
}: SettingExtractionConfigPanelProps) {
  const [localConfig, setLocalConfig] = useState<SettingExtractionConfig>({
    ...defaultConfig,
    ...config,
  })

  const handleChange = <K extends keyof SettingExtractionConfig>(
    key: K,
    value: SettingExtractionConfig[K]
  ) => {
    const newConfig = { ...localConfig, [key]: value }
    setLocalConfig(newConfig)
    onConfigChange(newConfig)
  }

  const toggleSettingType = (type: string) => {
    const currentTypes = localConfig.setting_types || []
    const newTypes = currentTypes.includes(type)
      ? currentTypes.filter((t) => t !== type)
      : [...currentTypes, type]
    handleChange('setting_types', newTypes)
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Settings className="w-5 h-5" />
          设定提取配置
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* 设定类型选择 */}
        <div className="space-y-3">
          <Label className="text-sm font-medium">设定类型</Label>
          <div className="grid grid-cols-2 gap-2">
            {settingTypeOptions.map((option) => {
              const Icon = option.icon
              const isSelected = localConfig.setting_types?.includes(option.value)
              return (
                <div
                  key={option.value}
                  className={`
                    flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition-colors
                    ${isSelected ? 'bg-primary/10 border-primary' : 'hover:bg-accent'}
                  `}
                  onClick={() => toggleSettingType(option.value)}
                >
                  <Checkbox checked={isSelected} />
                  <Icon className="w-4 h-4" />
                  <span className="text-sm">{option.label}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* 提取选项 */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium flex items-center gap-2">
            <Settings className="w-4 h-4" />
            提取选项
          </h4>
          
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="extract-attributes" className="text-sm">提取属性</Label>
                <p className="text-xs text-muted-foreground">
                  提取设定的详细属性和特征
                </p>
              </div>
              <Switch
                id="extract-attributes"
                checked={localConfig.extract_attributes}
                onCheckedChange={(checked) => handleChange('extract_attributes', checked)}
                disabled={disabled}
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="extract-relations" className="text-sm">识别关系</Label>
                <p className="text-xs text-muted-foreground">
                  检测设定之间的关系网络
                </p>
              </div>
              <Switch
                id="extract-relations"
                checked={localConfig.extract_relations}
                onCheckedChange={(checked) => handleChange('extract_relations', checked)}
                disabled={disabled}
              />
            </div>
          </div>
        </div>

        {/* 高级设置 */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium">高级设置</h4>
          
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="min-importance" className="text-sm">最小重要性</Label>
              <Select
                value={localConfig.min_importance}
                onValueChange={(value) => handleChange('min_importance', value)}
                disabled={disabled}
              >
                <SelectTrigger id="min-importance">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {importanceOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                低于此重要性的设定将被过滤
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="max-settings" className="text-sm">最大提取数量</Label>
              <Input
                id="max-settings"
                type="number"
                value={localConfig.max_settings}
                onChange={(e) => handleChange('max_settings', parseInt(e.target.value) || 100)}
                min={10}
                max={500}
                disabled={disabled}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="prompt-template" className="text-sm">提示词模板</Label>
              <Select
                value={localConfig.prompt_template_id}
                onValueChange={(value) => handleChange('prompt_template_id', value)}
                disabled={disabled}
              >
                <SelectTrigger id="prompt-template">
                  <SelectValue placeholder="选择模板" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="setting_extraction_v1">
                    V1 - 基础版
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-2 pt-2">
          <Button
            variant="outline"
            onClick={onPreview}
            disabled={disabled || isLoading}
            className="flex-1"
          >
            <Sparkles className="w-4 h-4 mr-2" />
            预览
          </Button>
          <Button
            onClick={onStartExtraction}
            disabled={disabled || isLoading}
            className="flex-1"
          >
            {isLoading ? (
              <>
                <div className="w-4 h-4 mr-2 animate-spin rounded-full border-2 border-current border-t-transparent" />
                提取中...
              </>
            ) : (
              <>
                <Settings className="w-4 h-4 mr-2" />
                开始提取
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

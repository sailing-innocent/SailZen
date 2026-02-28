/**
 * @file character_detection_config.tsx
 * @brief Character Detection Configuration Panel
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@components/ui/select'
import { Users, Sparkles, Settings } from 'lucide-react'
import type { CharacterDetectionConfig } from '@lib/data/analysis'

interface CharacterDetectionConfigPanelProps {
  config: CharacterDetectionConfig
  onConfigChange: (config: CharacterDetectionConfig) => void
  onStartDetection: () => void
  onPreview: () => void
  isLoading?: boolean
  disabled?: boolean
}

const defaultConfig: CharacterDetectionConfig = {
  detect_aliases: true,
  detect_attributes: true,
  detect_relations: true,
  min_confidence: 0.5,
  max_characters: 100,
  llm_provider: undefined,
  llm_model: undefined,
  temperature: 0.3,
  prompt_template_id: 'character_detection_v2',
}

export function CharacterDetectionConfigPanel({
  config,
  onConfigChange,
  onStartDetection,
  onPreview,
  isLoading = false,
  disabled = false,
}: CharacterDetectionConfigPanelProps) {
  const [localConfig, setLocalConfig] = useState<CharacterDetectionConfig>({
    ...defaultConfig,
    ...config,
  })

  const handleChange = <K extends keyof CharacterDetectionConfig>(
    key: K,
    value: CharacterDetectionConfig[K]
  ) => {
    const newConfig = { ...localConfig, [key]: value }
    setLocalConfig(newConfig)
    onConfigChange(newConfig)
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Users className="w-5 h-5" />
          人物检测配置
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* 检测选项 */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium flex items-center gap-2">
            <Settings className="w-4 h-4" />
            检测选项
          </h4>
          
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="detect-aliases" className="text-sm">识别别名</Label>
                <p className="text-xs text-muted-foreground">
                  检测人物的不同称呼形式（昵称、头衔等）
                </p>
              </div>
              <Switch
                id="detect-aliases"
                checked={localConfig.detect_aliases}
                onCheckedChange={(checked) => handleChange('detect_aliases', checked)}
                disabled={disabled}
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="detect-attributes" className="text-sm">提取属性</Label>
                <p className="text-xs text-muted-foreground">
                  提取人物的外貌、性格、能力等属性
                </p>
              </div>
              <Switch
                id="detect-attributes"
                checked={localConfig.detect_attributes}
                onCheckedChange={(checked) => handleChange('detect_attributes', checked)}
                disabled={disabled}
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="detect-relations" className="text-sm">识别关系</Label>
                <p className="text-xs text-muted-foreground">
                  检测人物之间的关系网络
                </p>
              </div>
              <Switch
                id="detect-relations"
                checked={localConfig.detect_relations}
                onCheckedChange={(checked) => handleChange('detect_relations', checked)}
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
              <div className="flex justify-between">
                <Label htmlFor="min-confidence" className="text-sm">最小置信度</Label>
                <span className="text-sm text-muted-foreground">
                  {(localConfig.min_confidence * 100).toFixed(0)}%
                </span>
              </div>
              <Slider
                id="min-confidence"
                value={[localConfig.min_confidence * 100]}
                onValueChange={([value]) => handleChange('min_confidence', value / 100)}
                min={30}
                max={90}
                step={5}
                disabled={disabled}
              />
              <p className="text-xs text-muted-foreground">
                低于此置信度的检测结果将被过滤
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="max-characters" className="text-sm">最大检测数量</Label>
              <Input
                id="max-characters"
                type="number"
                value={localConfig.max_characters}
                onChange={(e) => handleChange('max_characters', parseInt(e.target.value) || 100)}
                min={10}
                max={500}
                disabled={disabled}
              />
              <p className="text-xs text-muted-foreground">
                限制最多检测的人物数量
              </p>
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
                  <SelectItem value="character_detection_v2">
                    V2 - 增强版（推荐）
                  </SelectItem>
                  <SelectItem value="character_detection_v1">
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
            onClick={onStartDetection}
            disabled={disabled || isLoading}
            className="flex-1"
          >
            {isLoading ? (
              <>
                <div className="w-4 h-4 mr-2 animate-spin rounded-full border-2 border-current border-t-transparent" />
                检测中...
              </>
            ) : (
              <>
                <Users className="w-4 h-4 mr-2" />
                开始检测
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * @file character_attribute_editor.tsx
 * @brief Character Attribute Editor Component
 * @author sailing-innocent
 * @date 2025-03-01
 */

import { useState } from 'react'
import { Button } from '@components/ui/button'
import { Input } from '@components/ui/input'
import { Label } from '@components/ui/label'
import { Badge } from '@components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@components/ui/select'
import { Plus, X, Edit2, Trash2, Sparkles } from 'lucide-react'
import type { CharacterAttribute, CharacterAttributeCategory } from '@lib/data/analysis'

interface CharacterAttributeEditorProps {
  attributes: CharacterAttribute[]
  onAddAttribute: (attribute: Omit<CharacterAttribute, 'id' | 'created_at' | 'updated_at'>) => void
  onUpdateAttribute: (attributeId: string, updates: Partial<CharacterAttribute>) => void
  onDeleteAttribute: (attributeId: string) => void
  readOnly?: boolean
}

const categoryLabels: Record<CharacterAttributeCategory, string> = {
  appearance: '外貌',
  personality: '性格',
  ability: '能力',
  background: '背景',
  relationship: '关系',
  other: '其他',
}

const categoryColors: Record<CharacterAttributeCategory, string> = {
  appearance: 'bg-pink-100 text-pink-800 border-pink-200',
  personality: 'bg-blue-100 text-blue-800 border-blue-200',
  ability: 'bg-amber-100 text-amber-800 border-amber-200',
  background: 'bg-green-100 text-green-800 border-green-200',
  relationship: 'bg-purple-100 text-purple-800 border-purple-200',
  other: 'bg-gray-100 text-gray-800 border-gray-200',
}

export function CharacterAttributeEditor({
  attributes,
  onAddAttribute,
  onUpdateAttribute,
  onDeleteAttribute,
  readOnly = false,
}: CharacterAttributeEditorProps) {
  const [isAdding, setIsAdding] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [newAttribute, setNewAttribute] = useState({
    category: 'other' as CharacterAttributeCategory,
    attr_key: '',
    attr_value: '',
    confidence: 1.0,
  })

  const handleAdd = () => {
    if (!newAttribute.attr_key.trim() || !newAttribute.attr_value.trim()) return
    
    onAddAttribute({
      category: newAttribute.category,
      attr_key: newAttribute.attr_key.trim(),
      attr_value: newAttribute.attr_value.trim(),
      confidence: newAttribute.confidence,
      character_id: '', // 由父组件填充
    })
    
    setNewAttribute({
      category: 'other',
      attr_key: '',
      attr_value: '',
      confidence: 1.0,
    })
    setIsAdding(false)
  }

  const groupedAttributes = attributes.reduce((acc, attr) => {
    const category = attr.category || 'other'
    if (!acc[category]) acc[category] = []
    acc[category].push(attr)
    return acc
  }, {} as Record<string, CharacterAttribute[]>)

  return (
    <div className="space-y-4">
      {/* 添加按钮 */}
      {!readOnly && (
        <Dialog open={isAdding} onOpenChange={setIsAdding}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm" className="w-full">
              <Plus className="w-4 h-4 mr-2" />
              添加属性
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>添加人物属性</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label>属性类别</Label>
                <Select
                  value={newAttribute.category}
                  onValueChange={(value) =>
                    setNewAttribute({ ...newAttribute, category: value as CharacterAttributeCategory })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(categoryLabels).map(([key, label]) => (
                      <SelectItem key={key} value={key}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>属性名称</Label>
                <Input
                  value={newAttribute.attr_key}
                  onChange={(e) =>
                    setNewAttribute({ ...newAttribute, attr_key: e.target.value })
                  }
                  placeholder="例如：身高、性格特点"
                />
              </div>

              <div className="space-y-2">
                <Label>属性值</Label>
                <Input
                  value={newAttribute.attr_value}
                  onChange={(e) =>
                    setNewAttribute({ ...newAttribute, attr_value: e.target.value })
                  }
                  placeholder="例如：180cm、开朗乐观"
                />
              </div>

              <div className="space-y-2">
                <Label>置信度: {(newAttribute.confidence * 100).toFixed(0)}%</Label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={newAttribute.confidence * 100}
                  onChange={(e) =>
                    setNewAttribute({
                      ...newAttribute,
                      confidence: parseInt(e.target.value) / 100,
                    })
                  }
                  className="w-full"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <Button variant="outline" onClick={() => setIsAdding(false)} className="flex-1">
                  取消
                </Button>
                <Button onClick={handleAdd} className="flex-1">
                  添加
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* 属性列表 */}
      <div className="space-y-4">
        {Object.entries(groupedAttributes).length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Sparkles className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>暂无属性</p>
          </div>
        ) : (
          Object.entries(groupedAttributes).map(([category, attrs]) => (
            <div key={category} className="space-y-2">
              <h4 className="text-sm font-medium flex items-center gap-2">
                <Badge variant="outline" className={categoryColors[category as CharacterAttributeCategory]}>
                  {categoryLabels[category as CharacterAttributeCategory]}
                </Badge>
                <span className="text-muted-foreground">({attrs.length})</span>
              </h4>
              <div className="space-y-2">
                {attrs.map((attr) => (
                  <AttributeItem
                    key={attr.id}
                    attribute={attr}
                    isEditing={editingId === attr.id}
                    onStartEdit={() => setEditingId(attr.id)}
                    onCancelEdit={() => setEditingId(null)}
                    onSave={(updates) => {
                      onUpdateAttribute(attr.id, updates)
                      setEditingId(null)
                    }}
                    onDelete={() => onDeleteAttribute(attr.id)}
                    readOnly={readOnly}
                  />
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

interface AttributeItemProps {
  attribute: CharacterAttribute
  isEditing: boolean
  onStartEdit: () => void
  onCancelEdit: () => void
  onSave: (updates: Partial<CharacterAttribute>) => void
  onDelete: () => void
  readOnly: boolean
}

function AttributeItem({
  attribute,
  isEditing,
  onStartEdit,
  onCancelEdit,
  onSave,
  onDelete,
  readOnly,
}: AttributeItemProps) {
  const [editValue, setEditValue] = useState(attribute.attr_value)
  const [editConfidence, setEditConfidence] = useState(attribute.confidence || 1.0)

  if (isEditing) {
    return (
      <div className="p-3 rounded-lg border bg-accent/50 space-y-3">
        <div className="space-y-2">
          <Label className="text-sm">{attribute.attr_key}</Label>
          <Input
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            autoFocus
          />
        </div>
        <div className="space-y-2">
          <Label className="text-sm">置信度: {(editConfidence * 100).toFixed(0)}%</Label>
          <input
            type="range"
            min="0"
            max="100"
            value={editConfidence * 100}
            onChange={(e) => setEditConfidence(parseInt(e.target.value) / 100)}
            className="w-full"
          />
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onCancelEdit}
            className="flex-1"
          >
            <X className="w-4 h-4 mr-1" />
            取消
          </Button>
          <Button
            size="sm"
            onClick={() => onSave({ attr_value: editValue, confidence: editConfidence })}
            className="flex-1"
          >
            <Edit2 className="w-4 h-4 mr-1" />
            保存
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between p-2 rounded-lg border hover:bg-accent/30 transition-colors group">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{attribute.attr_key}</p>
        <p className="text-sm text-muted-foreground truncate">{attribute.attr_value}</p>
      </div>
      <div className="flex items-center gap-2">
        {attribute.confidence && (
          <Badge variant="outline" className="text-xs">
            {(attribute.confidence * 100).toFixed(0)}%
          </Badge>
        )}
        {!readOnly && (
          <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onStartEdit}
            >
              <Edit2 className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-destructive"
              onClick={onDelete}
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * @file outline_node_editor.tsx
 * @brief Outline Node Editor Component
 * @author sailing-innocent
 * @date 2025-02-28
 */

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  BookOpen,
  Target,
  Sparkles,
  ChevronRight,
  Save,
  X,
  Plus,
  Trash2,
  Link2,
  Users,
} from 'lucide-react'
import type { OutlineTreeNode, OutlineNodeType, TextEvidence } from '@lib/data/analysis'
import { EvidenceCard } from './evidence_card'

export interface OutlineNodeEditorProps {
  /** 当前编辑的节点 */
  node: OutlineTreeNode | null
  /** 所有节点列表（用于选择父节点） */
  allNodes?: OutlineTreeNode[]
  /** 节点证据列表 */
  evidences?: TextEvidence[]
  /** 保存回调 */
  onSave: (nodeId: string, data: Partial<OutlineTreeNode>) => void
  /** 取消回调 */
  onCancel: () => void
  /** 添加证据回调 */
  onAddEvidence?: (nodeId: string) => void
  /** 删除证据回调 */
  onDeleteEvidence?: (evidenceId: string) => void
  /** 是否显示 */
  open: boolean
}

const NODE_TYPE_OPTIONS: { value: OutlineNodeType; label: string; icon: React.ReactNode }[] = [
  { value: 'act', label: '幕', icon: <BookOpen className="w-4 h-4" /> },
  { value: 'arc', label: '弧', icon: <Target className="w-4 h-4" /> },
  { value: 'scene', label: '场景', icon: <Sparkles className="w-4 h-4" /> },
  { value: 'beat', label: '节拍', icon: <ChevronRight className="w-4 h-4" /> },
  { value: 'event', label: '事件', icon: <Sparkles className="w-4 h-4" /> },
]

const SIGNIFICANCE_OPTIONS = [
  { value: 'critical', label: '关键', color: 'bg-red-100 text-red-800' },
  { value: 'major', label: '主要', color: 'bg-orange-100 text-orange-800' },
  { value: 'normal', label: '普通', color: 'bg-blue-100 text-blue-800' },
  { value: 'minor', label: '次要', color: 'bg-gray-100 text-gray-800' },
]

/**
 * 大纲节点编辑器
 * 
 * 用于编辑大纲节点的详细信息：
 * - 标题和类型
 * - 内容描述
 * - 重要性级别
 * - 父节点关系
 * - 关联证据
 */
export function OutlineNodeEditor({
  node,
  allNodes = [],
  evidences = [],
  onSave,
  onCancel,
  onAddEvidence,
  onDeleteEvidence,
  open,
}: OutlineNodeEditorProps) {
  const [formData, setFormData] = useState<Partial<OutlineTreeNode>>({})
  const [activeTab, setActiveTab] = useState<'basic' | 'evidence' | 'advanced'>('basic')

  // 当节点变化时，重置表单
  useEffect(() => {
    if (node) {
      setFormData({
        title: node.title,
        content: node.content,
        node_type: node.node_type,
        significance: node.significance,
        parent_id: node.parent_id,
      })
    }
  }, [node])

  if (!node) return null

  const handleSave = () => {
    onSave(node.id, formData)
  }

  const handleChange = <K extends keyof OutlineTreeNode>(
    key: K,
    value: OutlineTreeNode[K]
  ) => {
    setFormData((prev) => ({ ...prev, [key]: value }))
  }

  // 构建父节点选项（排除当前节点及其子节点）
  const parentOptions = allNodes.filter((n) => {
    // 排除当前节点
    if (n.id === node.id) return false
    // 排除当前节点的子节点（简单实现，实际应该递归检查）
    return true
  })

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onCancel()}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BookOpen className="w-5 h-5" />
            编辑大纲节点
          </DialogTitle>
          <DialogDescription>
            编辑节点 "{node.title}" 的详细信息
          </DialogDescription>
        </DialogHeader>

        {/* 标签页切换 */}
        <div className="flex gap-1 p-1 bg-muted rounded-lg">
          {[
            { id: 'basic', label: '基本信息', icon: BookOpen },
            { id: 'evidence', label: '关联证据', icon: Link2 },
            { id: 'advanced', label: '高级设置', icon: Sparkles },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`
                flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors
                ${activeTab === tab.id ? 'bg-background shadow-sm' : 'hover:bg-background/50'}
              `}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        <ScrollArea className="flex-1 pr-4">
          <div className="space-y-6 py-4">
            {/* 基本信息 */}
            {activeTab === 'basic' && (
              <>
                <div className="space-y-2">
                  <Label>节点标题</Label>
                  <Input
                    value={formData.title || ''}
                    onChange={(e) => handleChange('title', e.target.value)}
                    placeholder="输入节点标题..."
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>节点类型</Label>
                    <Select
                      value={formData.node_type || 'scene'}
                      onValueChange={(v) => handleChange('node_type', v as OutlineNodeType)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {NODE_TYPE_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            <div className="flex items-center gap-2">
                              {opt.icon}
                              {opt.label}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>重要性级别</Label>
                    <Select
                      value={formData.significance || 'normal'}
                      onValueChange={(v) => handleChange('significance', v as OutlineTreeNode['significance'])}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {SIGNIFICANCE_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            <Badge variant="outline" className={opt.color}>
                              {opt.label}
                            </Badge>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>内容描述</Label>
                  <Textarea
                    value={formData.content || ''}
                    onChange={(e) => handleChange('content', e.target.value)}
                    placeholder="详细描述该节点的内容..."
                    className="min-h-[120px] resize-none"
                  />
                  <p className="text-xs text-muted-foreground">
                    建议 50-200 字，清晰描述该节点的主要内容和作用
                  </p>
                </div>
              </>
            )}

            {/* 关联证据 */}
            {activeTab === 'evidence' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Link2 className="w-4 h-4 text-muted-foreground" />
                    <Label className="text-base">关联文本证据</Label>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onAddEvidence?.(node.id)}
                  >
                    <Plus className="w-4 h-4 mr-1" />
                    添加证据
                  </Button>
                </div>

                {evidences.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground bg-muted rounded-lg">
                    <Link2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>暂无关联证据</p>
                    <p className="text-sm">添加原文引用作为该节点的支持证据</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {evidences.map((evidence) => (
                      <EvidenceCard
                        key={evidence.id}
                        evidence={evidence}
                        compact
                        onDelete={() => onDeleteEvidence?.(evidence.id)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 高级设置 */}
            {activeTab === 'advanced' && (
              <div className="space-y-6">
                <div className="space-y-2">
                  <Label>父节点</Label>
                  <Select
                    value={formData.parent_id || 'root'}
                    onValueChange={(v) => handleChange('parent_id', v === 'root' ? undefined : v)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="root">无（作为根节点）</SelectItem>
                      {parentOptions.map((n) => (
                        <SelectItem key={n.id} value={n.id}>
                          {n.title}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    更改父节点会调整节点在大纲树中的位置
                  </p>
                </div>

                <Separator />

                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-muted-foreground" />
                    <Label>涉及人物</Label>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {node.evidence_ids?.length ? (
                      <Badge variant="secondary">
                        {node.evidence_ids.length} 个证据
                      </Badge>
                    ) : (
                      <span className="text-sm text-muted-foreground">暂无人物信息</span>
                    )}
                  </div>
                </div>

                <Separator />

                <div className="space-y-2">
                  <Label>节点信息</Label>
                  <div className="text-sm text-muted-foreground space-y-1">
                    <p>ID: {node.id}</p>
                    <p>排序索引: {node.sort_index}</p>
                    <p>创建时间: {new Date(node.created_at).toLocaleString()}</p>
                    {node.updated_at && (
                      <p>更新时间: {new Date(node.updated_at).toLocaleString()}</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            <X className="w-4 h-4 mr-1" />
            取消
          </Button>
          <Button onClick={handleSave}>
            <Save className="w-4 h-4 mr-1" />
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default OutlineNodeEditor

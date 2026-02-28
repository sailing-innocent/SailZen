/**
 * @file evidence_card.tsx
 * @brief Evidence Card Component
 * @author sailing-innocent
 * @date 2025-02-28
 */

import { useState } from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  User,
  MapPin,
  BookOpen,
  Link2,
  Tag,
  MoreVertical,
  Edit2,
  Trash2,
  ExternalLink,
  Clock,
  Check,
  X,
} from 'lucide-react'
import type { TextEvidence } from '@lib/data/analysis'

export interface EvidenceCardProps {
  /** 证据数据 */
  evidence: TextEvidence
  /** 是否高亮显示 */
  highlighted?: boolean
  /** 点击回调 */
  onClick?: (evidence: TextEvidence) => void
  /** 更新回调 */
  onUpdate?: (evidenceId: string, data: Partial<TextEvidence>) => void
  /** 删除回调 */
  onDelete?: (evidenceId: string) => void
  /** 跳转到原文回调 */
  onNavigate?: (evidence: TextEvidence) => void
  /** 是否可编辑 */
  editable?: boolean
  /** 是否紧凑模式 */
  compact?: boolean
}

const EVIDENCE_TYPE_ICONS: Record<string, React.ReactNode> = {
  character: <User className="w-4 h-4" />,
  setting: <MapPin className="w-4 h-4" />,
  outline: <BookOpen className="w-4 h-4" />,
  relation: <Link2 className="w-4 h-4" />,
  custom: <Tag className="w-4 h-4" />,
}

const EVIDENCE_TYPE_LABELS: Record<string, string> = {
  character: '人物',
  setting: '设定',
  outline: '大纲',
  relation: '关系',
  custom: '自定义',
}

const EVIDENCE_TYPE_COLORS: Record<string, string> = {
  character: 'bg-blue-100 text-blue-800 border-blue-200',
  setting: 'bg-green-100 text-green-800 border-green-200',
  outline: 'bg-purple-100 text-purple-800 border-purple-200',
  relation: 'bg-orange-100 text-orange-800 border-orange-200',
  custom: 'bg-gray-100 text-gray-800 border-gray-200',
}

/**
 * 证据卡片组件
 * 
 * 显示单个证据的详细信息，支持：
 * - 显示证据类型、内容、选中文字
 * - 编辑证据内容
 * - 删除证据
 * - 跳转到原文位置
 * - 显示关联目标
 */
export function EvidenceCard({
  evidence,
  highlighted = false,
  onClick,
  onUpdate,
  onDelete,
  onNavigate,
  editable = true,
  compact = false,
}: EvidenceCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [editContent, setEditContent] = useState(evidence.content)
  const [editType, setEditType] = useState(evidence.evidence_type)
  const [editContext, setEditContext] = useState(evidence.context || '')

  const handleSave = () => {
    onUpdate?.(evidence.id, {
      content: editContent,
      evidence_type: editType,
      context: editContext || undefined,
    })
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditContent(evidence.content)
    setEditType(evidence.evidence_type)
    setEditContext(evidence.context || '')
    setIsEditing(false)
  }

  const handleDelete = () => {
    onDelete?.(evidence.id)
    setIsDeleteDialogOpen(false)
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const typeIcon = EVIDENCE_TYPE_ICONS[evidence.evidence_type] || EVIDENCE_TYPE_ICONS.custom
  const typeLabel = EVIDENCE_TYPE_LABELS[evidence.evidence_type] || '其他'
  const typeColor = EVIDENCE_TYPE_COLORS[evidence.evidence_type] || EVIDENCE_TYPE_COLORS.custom

  if (compact) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              className={`
                flex items-center gap-2 p-2 rounded-md cursor-pointer
                transition-colors duration-200
                ${highlighted ? 'bg-primary/10 ring-1 ring-primary' : 'hover:bg-muted'}
              `}
              onClick={() => onClick?.(evidence)}
            >
              <div className={`p-1 rounded ${typeColor}`}>{typeIcon}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{evidence.content}</p>
                <p className="text-xs text-muted-foreground truncate">
                  {evidence.selected_text.slice(0, 50)}
                  {evidence.selected_text.length > 50 ? '...' : ''}
                </p>
              </div>
            </div>
          </TooltipTrigger>
          <TooltipContent side="right" className="max-w-xs">
            <p className="font-medium">{typeLabel}</p>
            <p className="text-sm">{evidence.content}</p>
            <p className="text-xs text-muted-foreground mt-1">
              选中："{evidence.selected_text.slice(0, 100)}"
            </p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  return (
    <>
      <Card
        className={`
          transition-all duration-200
          ${highlighted ? 'ring-2 ring-primary shadow-md' : 'hover:shadow-sm'}
          ${onClick ? 'cursor-pointer' : ''}
        `}
        onClick={() => !isEditing && onClick?.(evidence)}
      >
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className={`${typeColor} flex items-center gap-1`}>
                {typeIcon}
                {typeLabel}
              </Badge>
              {evidence.target_type && (
                <Badge variant="secondary" className="text-xs">
                  {evidence.target_type}
                </Badge>
              )}
            </div>
            {editable && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-6 w-6 -mr-2">
                    <MoreVertical className="w-3 h-3" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => setIsEditing(true)}>
                    <Edit2 className="w-4 h-4 mr-2" />
                    编辑
                  </DropdownMenuItem>
                  {onNavigate && (
                    <DropdownMenuItem onClick={() => onNavigate(evidence)}>
                      <ExternalLink className="w-4 h-4 mr-2" />
                      跳转到原文
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem
                    className="text-destructive"
                    onClick={() => setIsDeleteDialogOpen(true)}
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    删除
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </CardHeader>

        <CardContent className="pt-0 space-y-3">
          {isEditing ? (
            <div className="space-y-3">
              <Select value={editType} onValueChange={setEditType}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(EVIDENCE_TYPE_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value} className="text-xs">
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="min-h-[60px] text-xs resize-none"
                placeholder="证据内容..."
              />
              <Input
                value={editContext}
                onChange={(e) => setEditContext(e.target.value)}
                className="h-8 text-xs"
                placeholder="上下文说明（可选）..."
              />
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" className="h-7 text-xs" onClick={handleCancel}>
                  <X className="w-3 h-3 mr-1" />
                  取消
                </Button>
                <Button size="sm" className="h-7 text-xs" onClick={handleSave}>
                  <Check className="w-3 h-3 mr-1" />
                  保存
                </Button>
              </div>
            </div>
          ) : (
            <>
              <p className="text-sm">{evidence.content}</p>

              {/* 选中的原文 */}
              <div className="bg-muted p-2 rounded text-xs text-muted-foreground border-l-2 border-primary">
                <span className="font-medium">原文：</span>
                {evidence.selected_text}
              </div>

              {/* 上下文（如果有） */}
              {evidence.context && (
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium">上下文：</span>
                  {evidence.context}
                </p>
              )}

              {/* 底部信息 */}
              <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t">
                <div className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatDate(evidence.created_at)}
                </div>
                {evidence.target_id && (
                  <Badge variant="outline" className="text-xs">
                    ID: {evidence.target_id.slice(0, 8)}...
                  </Badge>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* 删除确认对话框 */}
      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              您确定要删除这条证据标注吗？此操作无法撤销。
            </DialogDescription>
          </DialogHeader>
          <div className="bg-muted p-3 rounded text-sm">
            <p className="font-medium">{evidence.content}</p>
            <p className="text-muted-foreground text-xs mt-1">
              原文：{evidence.selected_text.slice(0, 100)}
              {evidence.selected_text.length > 100 ? '...' : ''}
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDeleteDialogOpen(false)}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default EvidenceCard

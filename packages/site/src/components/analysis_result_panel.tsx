/**
 * @file analysis_result_panel.tsx
 * @brief Analysis Result Panel - 分析结果展示面板
 * @author sailing-innocent
 * @date 2025-02-28
 */

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { 
  FileText, 
  Users, 
  Settings, 
  Share2, 
  CheckCircle, 
  XCircle, 
  Clock,
  AlertCircle,
  ChevronRight,
  ChevronDown,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ============================================================================
// Types
// ============================================================================

type ResultType = 'outline' | 'character' | 'setting' | 'relation'

interface AnalysisResult {
  id: string
  type: ResultType
  title: string
  description?: string
  status: 'pending' | 'approved' | 'rejected'
  confidence?: number
  createdAt: string
  data: Record<string, unknown>
}

interface AnalysisResultPanelProps {
  results?: AnalysisResult[]
  onApprove?: (resultId: string) => void
  onReject?: (resultId: string) => void
  onViewDetail?: (result: AnalysisResult) => void
  className?: string
}

// ============================================================================
// Result Type Config
// ============================================================================

const RESULT_TYPE_CONFIG: Record<ResultType, {
  label: string
  icon: React.ReactNode
  color: string
  bgColor: string
}> = {
  outline: {
    label: '大纲',
    icon: <FileText className="w-4 h-4" />,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
  },
  character: {
    label: '人物',
    icon: <Users className="w-4 h-4" />,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
  },
  setting: {
    label: '设定',
    icon: <Settings className="w-4 h-4" />,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
  },
  relation: {
    label: '关系',
    icon: <Share2 className="w-4 h-4" />,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
  },
}

const STATUS_CONFIG: Record<string, {
  label: string
  icon: React.ReactNode
  variant: 'default' | 'secondary' | 'destructive' | 'outline'
}> = {
  pending: {
    label: '待审核',
    icon: <Clock className="w-3 h-3" />,
    variant: 'secondary',
  },
  approved: {
    label: '已批准',
    icon: <CheckCircle className="w-3 h-3" />,
    variant: 'default',
  },
  rejected: {
    label: '已拒绝',
    icon: <XCircle className="w-3 h-3" />,
    variant: 'destructive',
  },
}

// ============================================================================
// Result Card Component
// ============================================================================

interface ResultCardProps {
  result: AnalysisResult
  onApprove?: (resultId: string) => void
  onReject?: (resultId: string) => void
  onViewDetail?: (result: AnalysisResult) => void
}

function ResultCard({ result, onApprove, onReject, onViewDetail }: ResultCardProps) {
  const [expanded, setExpanded] = useState(false)
  const typeConfig = RESULT_TYPE_CONFIG[result.type]
  const statusConfig = STATUS_CONFIG[result.status]

  return (
    <Card className="overflow-hidden">
      <CardHeader className="py-3 px-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={cn("p-2 rounded-lg", typeConfig.bgColor, typeConfig.color)}>
              {typeConfig.icon}
            </div>
            <div>
              <CardTitle className="text-sm font-medium">{result.title}</CardTitle>
              {result.description && (
                <CardDescription className="text-xs mt-0.5">
                  {result.description}
                </CardDescription>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={statusConfig.variant} className="flex items-center gap-1">
              {statusConfig.icon}
              {statusConfig.label}
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent className="px-4 pb-4 pt-0">
          <Separator className="mb-3" />
          
          {/* Result Data Preview */}
          <div className="bg-muted rounded-lg p-3 mb-3">
            <pre className="text-xs overflow-x-auto">
              {JSON.stringify(result.data, null, 2)}
            </pre>
          </div>

          {/* Metadata */}
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-3">
            <div className="flex items-center gap-4">
              {result.confidence !== undefined && (
                <span>置信度: {(result.confidence * 100).toFixed(1)}%</span>
              )}
              <span>创建于: {new Date(result.createdAt).toLocaleString()}</span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            {result.status === 'pending' && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8"
                  onClick={() => onApprove?.(result.id)}
                >
                  <CheckCircle className="w-3 h-3 mr-1" />
                  批准
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 text-destructive hover:text-destructive"
                  onClick={() => onReject?.(result.id)}
                >
                  <XCircle className="w-3 h-3 mr-1" />
                  拒绝
                </Button>
              </>
            )}
            <Button
              size="sm"
              variant="ghost"
              className="h-8 ml-auto"
              onClick={() => onViewDetail?.(result)}
            >
              查看详情
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  )
}

// ============================================================================
// Empty State Component
// ============================================================================

function EmptyState({ type }: { type: ResultType }) {
  const config = RESULT_TYPE_CONFIG[type]
  
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className={cn("p-4 rounded-full mb-4", config.bgColor)}>
        {config.icon}
      </div>
      <h3 className="text-lg font-medium mb-1">暂无{config.label}结果</h3>
      <p className="text-sm text-muted-foreground">
        创建分析任务并执行后，结果将显示在这里
      </p>
    </div>
  )
}

// ============================================================================
// Main Component
// ============================================================================

export function AnalysisResultPanel({
  results = [],
  onApprove,
  onReject,
  onViewDetail,
  className,
}: AnalysisResultPanelProps) {
  const [activeType, setActiveType] = useState<ResultType>('outline')

  // Group results by type
  const groupedResults = results.reduce((acc, result) => {
    if (!acc[result.type]) {
      acc[result.type] = []
    }
    acc[result.type].push(result)
    return acc
  }, {} as Record<ResultType, AnalysisResult[]>)

  // Get counts
  const counts = {
    outline: groupedResults.outline?.length || 0,
    character: groupedResults.character?.length || 0,
    setting: groupedResults.setting?.length || 0,
    relation: groupedResults.relation?.length || 0,
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <FileText className="w-4 h-4" />
          分析结果
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Tabs value={activeType} onValueChange={(v) => setActiveType(v as ResultType)}>
          <TabsList className="w-full grid grid-cols-4 rounded-none border-b bg-transparent">
            {(Object.keys(RESULT_TYPE_CONFIG) as ResultType[]).map((type) => (
              <TabsTrigger
                key={type}
                value={type}
                className="flex items-center gap-2 data-[state=active]:bg-muted"
              >
                {RESULT_TYPE_CONFIG[type].icon}
                <span className="hidden sm:inline">{RESULT_TYPE_CONFIG[type].label}</span>
                {counts[type] > 0 && (
                  <Badge variant="secondary" className="ml-1 text-xs">
                    {counts[type]}
                  </Badge>
                )}
              </TabsTrigger>
            ))}
          </TabsList>

          {(Object.keys(RESULT_TYPE_CONFIG) as ResultType[]).map((type) => (
            <TabsContent key={type} value={type} className="m-0">
              <ScrollArea className="h-[400px]">
                <div className="p-4 space-y-3">
                  {groupedResults[type]?.length > 0 ? (
                    groupedResults[type].map((result) => (
                      <ResultCard
                        key={result.id}
                        result={result}
                        onApprove={onApprove}
                        onReject={onReject}
                        onViewDetail={onViewDetail}
                      />
                    ))
                  ) : (
                    <EmptyState type={type} />
                  )}
                </div>
              </ScrollArea>
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  )
}

export default AnalysisResultPanel

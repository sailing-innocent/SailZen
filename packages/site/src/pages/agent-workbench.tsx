/**
 * @file index.tsx
 * @brief Agent Workbench Page
 * @author sailing-innocent
 * @date 2026-02-28
 * @version 1.0
 *
 * Agent 工作台页面 - 统一的 Agent 交互界面
 * 整合快速任务、小说分析、任务历史、成本监控等功能
 */

import React, { useEffect, useState } from 'react'
import PageLayout from '@components/page_layout'
import { useIsMobile } from '@/hooks/use-mobile'

// Store
import {
  useUnifiedAgentStore,
} from '@/lib/store/unifiedAgentStore'
import {
  type TaskType,
  type TaskStatus,
} from '@/lib/api/unifiedAgent'

// UI Components
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// Icons
import {
  Bot,
  Sparkles,
  BookOpen,
  History,
  Settings,
  Plus,
  RotateCw,
  PlayCircle,
  PauseCircle,
  AlertCircle,
  CheckCircle,
  Clock,
  Activity,
  Cpu,
  BarChart3,
  Wallet,
  Zap,
  Code,
  PenTool,
  MessageSquare,
  XCircle,
  ChevronRight,
  Terminal,
  TrendingUp,
} from 'lucide-react'

// ============================================================================
// Types
// ============================================================================

type WorkbenchTab = 'quick' | 'novel' | 'history' | 'settings'

// ============================================================================
// Task Result Display Component
// ============================================================================

const TaskResultDisplay: React.FC<{ resultData: Record<string, unknown> }> = ({ resultData }) => {
  // 提取响应内容
  const response = resultData.response as string | undefined
  const usage = resultData.usage as Record<string, number> | undefined
  const model = resultData.model as string | undefined
  const finishReason = resultData.finish_reason as string | undefined

  if (!response && !usage) {
    return (
      <pre className="text-xs text-muted-foreground overflow-auto max-h-[200px]">
        {JSON.stringify(resultData, null, 2)}
      </pre>
    )
  }

  return (
    <div className="space-y-3">
      {/* 模型信息 */}
      {model && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded">{model}</span>
          {finishReason && finishReason !== 'stop' && (
            <span className="text-amber-600">({finishReason})</span>
          )}
        </div>
      )}

      {/* 响应内容 */}
      {response && (
        <div className="bg-white rounded p-3 border">
          <p className="text-sm whitespace-pre-wrap leading-relaxed">{response}</p>
        </div>
      )}

      {/* Token 使用情况 */}
      {usage && (
        <div className="flex items-center gap-4 text-xs text-muted-foreground pt-2 border-t">
          {usage.prompt_tokens !== undefined && (
            <span>输入: {usage.prompt_tokens.toLocaleString()} tokens</span>
          )}
          {usage.completion_tokens !== undefined && (
            <span>输出: {usage.completion_tokens.toLocaleString()} tokens</span>
          )}
          {usage.total_tokens !== undefined && (
            <span>总计: {usage.total_tokens.toLocaleString()} tokens</span>
          )}
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Status Badge Component
// ============================================================================

const StatusBadge: React.FC<{ status: TaskStatus; showIcon?: boolean }> = ({
  status,
  showIcon = true,
}) => {
  const config: Record<
    TaskStatus | 'unknown',
    { color: string; icon: React.ReactNode; label: string }
  > = {
    pending: {
      color: 'bg-yellow-100 text-yellow-800 border-yellow-300',
      icon: <Clock className="w-3 h-3" />,
      label: '待处理',
    },
    running: {
      color: 'bg-blue-100 text-blue-800 border-blue-300',
      icon: <Activity className="w-3 h-3 animate-pulse" />,
      label: '运行中',
    },
    completed: {
      color: 'bg-green-100 text-green-800 border-green-300',
      icon: <CheckCircle className="w-3 h-3" />,
      label: '已完成',
    },
    failed: {
      color: 'bg-red-100 text-red-800 border-red-300',
      icon: <AlertCircle className="w-3 h-3" />,
      label: '失败',
    },
    cancelled: {
      color: 'bg-gray-100 text-gray-800 border-gray-300',
      icon: <XCircle className="w-3 h-3" />,
      label: '已取消',
    },
    unknown: {
      color: 'bg-gray-100 text-gray-800 border-gray-300',
      icon: <Clock className="w-3 h-3" />,
      label: '未知',
    },
  }

  const { color, icon, label } = config[status] || config.unknown

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${color}`}
    >
      {showIcon && icon}
      {label}
    </span>
  )
}

// ============================================================================
// Task Type Badge
// ============================================================================

const TaskTypeBadge: React.FC<{ type: TaskType }> = ({ type }) => {
  const config: Record<TaskType, { icon: React.ReactNode; label: string; color: string }> = {
    novel_analysis: {
      icon: <BookOpen className="w-3 h-3" />,
      label: '小说分析',
      color: 'bg-purple-100 text-purple-800',
    },
    code: {
      icon: <Code className="w-3 h-3" />,
      label: '代码',
      color: 'bg-blue-100 text-blue-800',
    },
    writing: {
      icon: <PenTool className="w-3 h-3" />,
      label: '写作',
      color: 'bg-pink-100 text-pink-800',
    },
    general: {
      icon: <MessageSquare className="w-3 h-3" />,
      label: '通用',
      color: 'bg-gray-100 text-gray-800',
    },
  }

  const { icon, label, color } = config[type]

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${color}`}>
      {icon}
      {label}
    </span>
  )
}

// ============================================================================
// Sidebar Component
// ============================================================================

const Sidebar: React.FC<{
  activeTab: WorkbenchTab
  onTabChange: (tab: WorkbenchTab) => void
}> = ({ activeTab, onTabChange }) => {
  // Use individual selectors to avoid creating new objects
  const tasks = useUnifiedAgentStore((state) => state.tasks)

  // Calculate stats from tasks directly to avoid hook issues
  const pendingCount = React.useMemo(() => tasks.filter((t) => t.status === 'pending').length, [tasks])
  const runningCount = React.useMemo(() => tasks.filter((t) => t.status === 'running').length, [tasks])
  const totalCount = tasks.length
  const totalCost = React.useMemo(() => tasks.reduce((sum, t) => sum + (Number(t.actualCost) || 0), 0), [tasks])
  const activeTaskCount = pendingCount + runningCount

  const menuItems = React.useMemo(() => [
    { id: 'quick' as WorkbenchTab, icon: <Zap className="w-4 h-4" />, label: '快速任务' },
    { id: 'novel' as WorkbenchTab, icon: <BookOpen className="w-4 h-4" />, label: '小说分析' },
    {
      id: 'history' as WorkbenchTab,
      icon: <History className="w-4 h-4" />,
      label: '任务历史',
      badge: activeTaskCount > 0 ? activeTaskCount : undefined,
    },
    { id: 'settings' as WorkbenchTab, icon: <Settings className="w-4 h-4" />, label: '设置' },
  ], [activeTaskCount])

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-primary/10">
            <Bot className="w-5 h-5 text-primary" />
          </div>
          <div>
            <CardTitle className="text-base">Agent 工作台</CardTitle>
            <CardDescription className="text-xs">AI 任务管理中心</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-3">
        <nav className="space-y-1">
          {menuItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${activeTab === item.id
                ? 'bg-primary text-primary-foreground'
                : 'hover:bg-muted text-muted-foreground hover:text-foreground'
                }`}
            >
              <div className="flex items-center gap-2">
                {item.icon}
                <span>{item.label}</span>
              </div>
              {item.badge ? (
                <Badge
                  variant={activeTab === item.id ? 'secondary' : 'default'}
                  className="text-xs h-5 min-w-5 flex items-center justify-center"
                >
                  {item.badge}
                </Badge>
              ) : null}
            </button>
          ))}
        </nav>

        <Separator className="my-4" />

        {/* Quick Stats */}
        <div className="space-y-3">
          <p className="text-xs font-medium text-muted-foreground">今日概览</p>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2 rounded-lg bg-muted">
              <p className="text-lg font-bold">{totalCount}</p>
              <p className="text-xs text-muted-foreground">总任务</p>
            </div>
            <div className="p-2 rounded-lg bg-muted">
              <p className="text-lg font-bold">${totalCost.toFixed(3)}</p>
              <p className="text-xs text-muted-foreground">总成本</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ============================================================================
// Quick Task Panel
// ============================================================================

const QuickTaskPanel: React.FC = () => {
  const createTask = useUnifiedAgentStore((state) => state.createTask)
  const isCreatingTask = useUnifiedAgentStore((state) => state.isCreatingTask)
  const agents = useUnifiedAgentStore((state) => state.agents)
  const loadAgents = useUnifiedAgentStore((state) => state.loadAgents)
  const [selectedType, setSelectedType] = useState<TaskType>('general')
  const [prompt, setPrompt] = useState('')
  const [priority, setPriority] = useState(5)

  useEffect(() => {
    loadAgents()
  }, [loadAgents])

  const taskTypes: { type: TaskType; icon: React.ReactNode; label: string; desc: string }[] = [
    {
      type: 'general',
      icon: <MessageSquare className="w-5 h-5" />,
      label: '通用对话',
      desc: '问答、头脑风暴、一般性对话',
    },
    {
      type: 'code',
      icon: <Code className="w-5 h-5" />,
      label: '代码辅助',
      desc: '代码审查、生成、重构、Bug 修复',
    },
    {
      type: 'writing',
      icon: <PenTool className="w-5 h-5" />,
      label: '写作辅助',
      desc: '文本补全、润色、翻译、摘要',
    },
  ]

  const handleSubmit = async () => {
    if (!prompt.trim()) return

    const subTypeMap: Record<TaskType, string> = {
      general: 'chat',
      code: 'code_review',
      writing: 'text_completion',
      novel_analysis: 'outline_extraction',
    }

    await createTask({
      taskType: selectedType,
      subType: subTypeMap[selectedType],
      priority,
      config: { prompt },
    })

    setPrompt('')
  }

  return (
    <div className="space-y-4">
      {/* Task Type Selection */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-primary" />
            选择任务类型
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {taskTypes.map((type) => (
              <button
                key={type.type}
                onClick={() => setSelectedType(type.type)}
                className={`p-4 rounded-lg border text-left transition-all ${selectedType === type.type
                  ? 'border-primary bg-primary/5'
                  : 'border-muted hover:border-primary/30 hover:bg-muted/50'
                  }`}
              >
                <div
                  className={`p-2 rounded-lg w-fit mb-2 ${selectedType === type.type ? 'bg-primary/10' : 'bg-muted'
                    }`}
                >
                  {React.cloneElement(type.icon as React.ReactElement, {
                    className: `w-5 h-5 ${selectedType === type.type ? 'text-primary' : 'text-muted-foreground'}`,
                  })}
                </div>
                <p className="font-medium text-sm">{type.label}</p>
                <p className="text-xs text-muted-foreground mt-1">{type.desc}</p>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Prompt Input */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">输入任务内容</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="输入你的任务描述..."
            className="w-full min-h-[150px] p-3 rounded-lg border resize-none focus:outline-none focus:ring-2 focus:ring-primary/50"
          />

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">优先级:</span>
              <Select value={String(priority)} onValueChange={(v) => setPriority(Number(v))}>
                <SelectTrigger className="w-24">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((p) => (
                    <SelectItem key={p} value={String(p)}>
                      {p} {p <= 3 ? '🔥' : p <= 6 ? '⚡' : '📌'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button
              onClick={handleSubmit}
              disabled={isCreatingTask || !prompt.trim()}
              className="flex items-center gap-2"
            >
              {isCreatingTask ? (
                <RotateCw className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              {isCreatingTask ? '创建中...' : '创建任务'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Available Agents */}
      {agents.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">可用 Agent</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {agents.map((agent) => (
                <Badge key={agent.agentType} variant="outline" className="px-3 py-1">
                  {agent.name}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// ============================================================================
// Novel Analysis Panel
// ============================================================================

const NovelAnalysisPanel: React.FC = () => {
  const createTask = useUnifiedAgentStore((state) => state.createTask)
  const isCreatingTask = useUnifiedAgentStore((state) => state.isCreatingTask)
  const [selectedAnalysis, setSelectedAnalysis] = useState<string>('outline_extraction')

  const analysisTypes: { value: string; icon: React.ReactNode; label: string; desc: string }[] = [
    {
      value: 'outline_extraction',
      icon: <BarChart3 className="w-4 h-4" />,
      label: '大纲提取',
      desc: '从章节内容中提取故事大纲和结构',
    },
    {
      value: 'character_detection',
      icon: <Bot className="w-4 h-4" />,
      label: '人物检测',
      desc: '识别和分析小说中的角色',
    },
    {
      value: 'setting_extraction',
      icon: <Terminal className="w-4 h-4" />,
      label: '设定提取',
      desc: '提取世界观、物品、地点等设定',
    },
    {
      value: 'relation_analysis',
      icon: <TrendingUp className="w-4 h-4" />,
      label: '关系分析',
      desc: '分析角色之间的关系网络',
    },
  ]

  const handleStartAnalysis = async () => {
    // 这里需要选择版本和章节，简化处理
    await createTask({
      taskType: 'novel_analysis',
      subType: selectedAnalysis,
      priority: 5,
      config: {},
    })
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-primary" />
            小说分析
          </CardTitle>
          <CardDescription>选择分析类型并开始分析小说内容</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {analysisTypes.map((type) => (
              <button
                key={type.value}
                onClick={() => setSelectedAnalysis(type.value)}
                className={`p-4 rounded-lg border text-left transition-all ${selectedAnalysis === type.value
                  ? 'border-primary bg-primary/5'
                  : 'border-muted hover:border-primary/30'
                  }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  {type.icon}
                  <span className="font-medium">{type.label}</span>
                </div>
                <p className="text-xs text-muted-foreground">{type.desc}</p>
              </button>
            ))}
          </div>

          <Button
            onClick={handleStartAnalysis}
            disabled={isCreatingTask}
            className="w-full"
          >
            {isCreatingTask ? (
              <RotateCw className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <PlayCircle className="w-4 h-4 mr-2" />
            )}
            开始分析
          </Button>
        </CardContent>
      </Card>

      {/* Link to full analysis page */}
      <Card className="bg-muted/50">
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">需要更多分析选项？</p>
              <p className="text-sm text-muted-foreground">使用完整的小说分析页面</p>
            </div>
            <Button variant="outline" onClick={() => (window.location.href = '/analysis')}>
              前往分析页面
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

// ============================================================================
// Task Monitor Panel
// ============================================================================

const TaskMonitorPanel: React.FC = () => {
  const tasks = useUnifiedAgentStore((state) => state.tasks)
  const currentTask = useUnifiedAgentStore((state) => state.currentTask)
  const currentTaskProgress = useUnifiedAgentStore((state) => state.currentTaskProgress)
  const loadTasks = useUnifiedAgentStore((state) => state.loadTasks)
  const loadTask = useUnifiedAgentStore((state) => state.loadTask)
  const cancelTask = useUnifiedAgentStore((state) => state.cancelTask)
  const deleteTask = useUnifiedAgentStore((state) => state.deleteTask)
  const setTaskFilter = useUnifiedAgentStore((state) => state.setTaskFilter)
  const taskFilter = useUnifiedAgentStore((state) => state.taskFilter)
  const isLoading = useUnifiedAgentStore((state) => state.isLoading)
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)

  // Calculate stats directly to avoid hook issues
  const stats = React.useMemo(() => {
    return {
      total: tasks.length,
      pending: tasks.filter((t) => t.status === 'pending').length,
      running: tasks.filter((t) => t.status === 'running').length,
      completed: tasks.filter((t) => t.status === 'completed').length,
      failed: tasks.filter((t) => t.status === 'failed').length,
    }
  }, [tasks])

  useEffect(() => {
    loadTasks()
  }, [loadTasks, taskFilter])

  const handleSelectTask = (taskId: number) => {
    setSelectedTaskId(taskId)
    loadTask(taskId)
  }

  const filteredTasks = tasks.filter((task) => {
    if (taskFilter.status && task.status !== taskFilter.status) return false
    if (taskFilter.taskType && task.taskType !== taskFilter.taskType) return false
    return true
  })

  return (
    <div className="space-y-4">
      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: '总任务', value: stats.total, color: 'bg-blue-500' },
          { label: '待处理', value: stats.pending, color: 'bg-yellow-500' },
          { label: '运行中', value: stats.running, color: 'bg-blue-500' },
          { label: '已完成', value: stats.completed, color: 'bg-green-500' },
          { label: '失败', value: stats.failed, color: 'bg-red-500' },
        ].map((stat) => (
          <Card key={stat.label} className="cursor-pointer hover:shadow-md transition-shadow">
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground">{stat.label}</p>
              <p className="text-2xl font-bold">{stat.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm text-muted-foreground">筛选:</span>
            <Select
              value={taskFilter.status || 'all'}
              onValueChange={(v) => setTaskFilter({ status: v === 'all' ? undefined : (v as TaskStatus) })}
            >
              <SelectTrigger className="w-32">
                <SelectValue placeholder="状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                <SelectItem value="pending">待处理</SelectItem>
                <SelectItem value="running">运行中</SelectItem>
                <SelectItem value="completed">已完成</SelectItem>
                <SelectItem value="failed">失败</SelectItem>
                <SelectItem value="cancelled">已取消</SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={taskFilter.taskType || 'all'}
              onValueChange={(v) => setTaskFilter({ taskType: v === 'all' ? undefined : (v as TaskType) })}
            >
              <SelectTrigger className="w-32">
                <SelectValue placeholder="类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部类型</SelectItem>
                <SelectItem value="novel_analysis">小说分析</SelectItem>
                <SelectItem value="code">代码</SelectItem>
                <SelectItem value="writing">写作</SelectItem>
                <SelectItem value="general">通用</SelectItem>
              </SelectContent>
            </Select>

            <Button variant="ghost" size="sm" onClick={() => loadTasks()}>
              <RotateCw className="w-4 h-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Task List & Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Task List */}
        <Card className="h-[500px]">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">任务列表</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[420px]">
              <div className="space-y-1 p-3">
                {filteredTasks.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <Bot className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p>暂无任务</p>
                  </div>
                ) : (
                  filteredTasks.map((task) => (
                    <div
                      key={task.id}
                      onClick={() => handleSelectTask(task.id)}
                      className={`p-3 rounded-lg cursor-pointer transition-all border ${selectedTaskId === task.id
                        ? 'border-primary bg-primary/5'
                        : 'border-transparent hover:bg-muted'
                        }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <TaskTypeBadge type={task.taskType} />
                            <span className="text-xs text-muted-foreground">#{task.id}</span>
                          </div>
                          <p className="text-sm font-medium truncate">
                            {task.currentPhase || task.subType || 'Task'}
                          </p>
                        </div>
                        <StatusBadge status={task.status} showIcon={false} />
                      </div>

                      <div className="mt-2 space-y-1">
                        <Progress value={task.progress} className="h-1.5" />
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>{task.progress}%</span>
                          <span>${Number(task.actualCost || 0).toFixed(4)}</span>
                        </div>
                      </div>

                      {task.status === 'running' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="w-full mt-2 h-7 text-xs"
                          onClick={(e) => {
                            e.stopPropagation()
                            cancelTask(task.id)
                          }}
                        >
                          <XCircle className="w-3 h-3 mr-1" />
                          取消
                        </Button>
                      )}
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Task Detail */}
        <Card className="h-[500px]">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">任务详情</CardTitle>
          </CardHeader>
          <CardContent>
            {!currentTask || selectedTaskId !== currentTask.id ? (
              <div className="h-full flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <Terminal className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p>选择一个任务查看详情</p>
                </div>
              </div>
            ) : (
              <ScrollArea className="h-[420px]">
                <div className="space-y-4">
                  {/* Basic Info */}
                  <div className="flex items-center justify-between">
                    <TaskTypeBadge type={currentTask.taskType} />
                    <StatusBadge status={currentTask.status} />
                  </div>

                  {/* Progress */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">进度</span>
                      <span className="text-sm">{currentTask.progress}%</span>
                    </div>
                    <Progress value={currentTask.progress} className="h-2" />
                  </div>

                  {/* Cost Info */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-muted">
                      <p className="text-xs text-muted-foreground">Token 消耗</p>
                      <p className="text-lg font-medium">{currentTask.actualTokens.toLocaleString()}</p>
                    </div>
                    <div className="p-3 rounded-lg bg-muted">
                      <p className="text-xs text-muted-foreground">成本</p>
                      <p className="text-lg font-medium">${Number(currentTask.actualCost || 0).toFixed(4)}</p>
                    </div>
                  </div>

                  {/* Current Phase */}
                  {currentTask.currentPhase && (
                    <div className="p-3 rounded-lg bg-primary/5 border border-primary/20">
                      <p className="text-xs text-muted-foreground mb-1">当前阶段</p>
                      <p className="text-sm">{currentTask.currentPhase}</p>
                    </div>
                  )}

                  {/* Progress Detail */}
                  {currentTaskProgress && (
                    <div className="space-y-2">
                      <p className="text-sm font-medium">执行详情</p>
                      {currentTaskProgress.currentStep && (
                        <p className="text-sm text-muted-foreground">
                          步骤: {currentTaskProgress.currentStep} / {currentTaskProgress.totalSteps}
                        </p>
                      )}
                      {currentTaskProgress.estimatedRemainingSeconds && (
                        <p className="text-sm text-muted-foreground">
                          预计剩余: {Math.ceil(currentTaskProgress.estimatedRemainingSeconds / 60)} 分钟
                        </p>
                      )}
                    </div>
                  )}

                  {/* Error Message */}
                  {currentTask.errorMessage && (
                    <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30">
                      <p className="text-xs text-muted-foreground mb-1">错误信息</p>
                      <p className="text-sm text-destructive">{currentTask.errorMessage}</p>
                    </div>
                  )}

                  {/* Task Result */}
                  {(() => {
                    console.log('[TaskDetail] Task status:', currentTask.status)
                    console.log('[TaskDetail] Task resultData:', currentTask.resultData)
                    return null
                  })()}
                  {currentTask.resultData && currentTask.status === 'completed' && (
                    <div className="p-3 rounded-lg bg-green-50 border border-green-200">
                      <p className="text-xs text-green-600 mb-2 flex items-center gap-1">
                        <CheckCircle className="w-3 h-3" />
                        执行结果
                      </p>
                      <TaskResultDisplay resultData={currentTask.resultData} />
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 pt-4 border-t">
                    {currentTask.status === 'running' && (
                      <Button variant="outline" size="sm" onClick={() => cancelTask(currentTask.id)}>
                        <PauseCircle className="w-4 h-4 mr-1" />
                        取消任务
                      </Button>
                    )}
                    {(currentTask.status === 'completed' ||
                      currentTask.status === 'failed' ||
                      currentTask.status === 'cancelled') && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => deleteTask(currentTask.id)}
                        >
                          <XCircle className="w-4 h-4 mr-1" />
                          删除任务
                        </Button>
                      )}
                  </div>
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// ============================================================================
// Cost Display Component
// ============================================================================

const CostDisplayPanel: React.FC = () => {
  // Use individual selectors to avoid creating new objects
  const tasks = useUnifiedAgentStore((state) => state.tasks)
  const schedulerStatus = useUnifiedAgentStore((state) => state.schedulerStatus)
  const loadSchedulerStatus = useUnifiedAgentStore((state) => state.loadSchedulerStatus)
  const startScheduler = useUnifiedAgentStore((state) => state.startScheduler)
  const stopScheduler = useUnifiedAgentStore((state) => state.stopScheduler)
  const isLoading = useUnifiedAgentStore((state) => state.isLoading)

  useEffect(() => {
    loadSchedulerStatus()
  }, [loadSchedulerStatus])

  // Calculate stats directly
  const totalCost = React.useMemo(() => tasks.reduce((sum, t) => sum + (Number(t.actualCost) || 0), 0), [tasks])
  const totalTokens = React.useMemo(() => tasks.reduce((sum, t) => sum + t.actualTokens, 0), [tasks])

  const budgetLimit = 10.0 // 示例预算限制
  const budgetUsed = totalCost
  const budgetPercent = Math.min((budgetUsed / budgetLimit) * 100, 100)

  const handleToggleScheduler = async () => {
    if (schedulerStatus?.isRunning) {
      await stopScheduler()
    } else {
      await startScheduler()
    }
    // 刷新状态
    await loadSchedulerStatus()
  }

  return (
    <div className="space-y-4">
      {/* Cost Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wallet className="w-5 h-5 text-primary" />
            成本概览
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Budget Progress */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">今日预算使用</span>
              <span className="text-sm font-medium">
                ${budgetUsed.toFixed(2)} / ${budgetLimit.toFixed(2)}
              </span>
            </div>
            <Progress value={budgetPercent} className="h-2" />
            <p className="text-xs text-muted-foreground mt-1">{budgetPercent.toFixed(1)}% 已使用</p>
          </div>

          {/* Cost Stats */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 rounded-lg bg-muted">
              <p className="text-xs text-muted-foreground">总 Token 消耗</p>
              <p className="text-xl font-bold">{totalTokens.toLocaleString()}</p>
            </div>
            <div className="p-3 rounded-lg bg-muted">
              <p className="text-xs text-muted-foreground">总成本</p>
              <p className="text-xl font-bold">${totalCost.toFixed(3)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Scheduler Status */}
      {schedulerStatus && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Cpu className="w-4 h-4" />
              调度器状态
              <Badge variant={schedulerStatus.isRunning ? 'default' : 'secondary'}>
                {schedulerStatus.isRunning ? '运行中' : '已停止'}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Scheduler Control Button */}
            <div className="mb-4">
              <Button
                variant={schedulerStatus.isRunning ? 'outline' : 'default'}
                size="sm"
                className="w-full"
                disabled={isLoading}
                onClick={handleToggleScheduler}
              >
                {isLoading ? (
                  <RotateCw className="w-4 h-4 animate-spin mr-2" />
                ) : schedulerStatus.isRunning ? (
                  <PauseCircle className="w-4 h-4 mr-2" />
                ) : (
                  <PlayCircle className="w-4 h-4 mr-2" />
                )}
                {isLoading
                  ? '处理中...'
                  : schedulerStatus.isRunning
                    ? '停止调度器'
                    : '启动调度器'}
              </Button>
              {!schedulerStatus.isRunning && (
                <p className="text-xs text-muted-foreground mt-2 text-center">
                  调度器停止时，新任务不会自动执行
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="p-2 rounded-lg bg-muted">
                <p className="text-xs text-muted-foreground">总任务</p>
                <p className="text-lg font-semibold">{schedulerStatus.stats.totalTasks}</p>
              </div>
              <div className="p-2 rounded-lg bg-muted">
                <p className="text-xs text-muted-foreground">待处理</p>
                <p className="text-lg font-semibold">{schedulerStatus.stats.pendingTasks}</p>
              </div>
              <div className="p-2 rounded-lg bg-muted">
                <p className="text-xs text-muted-foreground">运行中</p>
                <p className="text-lg font-semibold">{schedulerStatus.stats.runningTasks}</p>
              </div>
              <div className="p-2 rounded-lg bg-muted">
                <p className="text-xs text-muted-foreground">已完成</p>
                <p className="text-lg font-semibold">{schedulerStatus.stats.completedTasks}</p>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">总 Token 消耗</span>
                <span className="font-medium">
                  {(schedulerStatus.stats.totalTokensConsumed || 0).toLocaleString()}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm mt-1">
                <span className="text-muted-foreground">总成本</span>
                <span className="font-medium">
                  ${Number(schedulerStatus.stats.totalCost || 0).toFixed(3)}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// ============================================================================
// Settings Panel
// ============================================================================

const SettingsPanel: React.FC = () => {
  const useUnifiedAPI = useUnifiedAgentStore((state) => state.useUnifiedAPI)
  const setUseUnifiedAPI = useUnifiedAgentStore((state) => state.setUseUnifiedAPI)
  const reset = useUnifiedAgentStore((state) => state.reset)

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            工作台设置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Feature Flag */}
          <div className="flex items-center justify-between p-3 rounded-lg border">
            <div>
              <p className="font-medium">使用统一 API</p>
              <p className="text-sm text-muted-foreground">启用新的统一 Agent API</p>
            </div>
            <Button
              variant={useUnifiedAPI ? 'default' : 'outline'}
              size="sm"
              onClick={() => setUseUnifiedAPI(!useUnifiedAPI)}
            >
              {useUnifiedAPI ? '已启用' : '已禁用'}
            </Button>
          </div>

          <Separator />

          {/* Reset */}
          <div className="flex items-center justify-between p-3 rounded-lg border border-destructive/30">
            <div>
              <p className="font-medium text-destructive">重置 Store</p>
              <p className="text-sm text-muted-foreground">清除所有本地状态和数据</p>
            </div>
            <Button variant="destructive" size="sm" onClick={reset}>
              重置
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* About */}
      <Card className="bg-muted/50">
        <CardContent className="p-4">
          <p className="text-sm text-muted-foreground">
            Agent 工作台 v1.0 - 统一的 AI 任务管理中心
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            支持小说分析、代码辅助、写作辅助和通用对话
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

// ============================================================================
// Main Agent Workbench Page
// ============================================================================

const AgentWorkbenchPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<WorkbenchTab>('quick')
  const connectRealtimeUpdates = useUnifiedAgentStore((state) => state.connectRealtimeUpdates)
  const disconnectRealtimeUpdates = useUnifiedAgentStore((state) => state.disconnectRealtimeUpdates)
  const error = useUnifiedAgentStore((state) => state.error)
  const clearError = useUnifiedAgentStore((state) => state.clearError)
  const isMobile = useIsMobile()

  useEffect(() => {
    connectRealtimeUpdates()
    return () => disconnectRealtimeUpdates()
  }, [])

  return (
    <PageLayout>
      <div className={`flex gap-4 ${isMobile ? 'flex-col' : 'flex-row'}`}>
        {/* Sidebar */}
        <div className={isMobile ? 'w-full' : 'w-64 flex-shrink-0'}>
          <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
        </div>

        {/* Main Content */}
        <div className="flex-1 min-w-0">
          <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                  <Bot className="w-7 h-7 text-primary" />
                  Agent 工作台
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                  统一的 AI 任务管理中心
                </p>
              </div>
            </div>

            {/* Error Alert */}
            {error && (
              <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-lg flex items-center justify-between">
                <div className="flex items-center gap-2 text-destructive">
                  <AlertCircle className="w-4 h-4" />
                  <span className="text-sm">{error}</span>
                </div>
                <Button variant="ghost" size="sm" onClick={clearError}>
                  关闭
                </Button>
              </div>
            )}

            {/* Content Grid */}
            <div className={`grid gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-3'}`}>
              {/* Main Panel */}
              <div className={isMobile ? '' : 'col-span-3'}>
                {activeTab === 'quick' && <QuickTaskPanel />}
                {activeTab === 'novel' && <NovelAnalysisPanel />}
                {activeTab === 'history' && <TaskMonitorPanel />}
                {activeTab === 'settings' && <SettingsPanel />}
              </div>
            </div>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}

export default AgentWorkbenchPage

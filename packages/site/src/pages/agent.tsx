/**
 * Agent Page
 * AI Agent 交互入口页面
 * 
 * 功能：
 * 1. 提交 Prompt 任务
 * 2. 查看任务历史和状态
 * 3. 实时跟踪任务执行
 * 4. 查看任务结果和输出
 */

import React, { useEffect, useState, useRef } from 'react'
import { useAgentStore } from '@/lib/store/agentStore'
import { useIsMobile } from '@/hooks/use-mobile'
import PageLayout from '@components/page_layout'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
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
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

import {
  Send,
  RotateCw,
  AlertCircle,
  CheckCircle,
  Clock,
  Terminal,
  Activity,
  Bot,
  History,
  ChevronRight,
  Sparkles,
  Settings,
  PauseCircle,
  PlayCircle,
  XCircle,
  MessageSquare,
  Cpu,
  BarChart3,
} from 'lucide-react'

// ============================================================================
// Status Badge Component
// ============================================================================

const StatusBadge: React.FC<{ status: string; showIcon?: boolean }> = ({ 
  status, 
  showIcon = true 
}) => {
  const variants: Record<string, { 
    variant: 'default' | 'secondary' | 'destructive' | 'outline' | 'success'
    icon: React.ReactNode 
    color: string
  }> = {
    pending: { 
      variant: 'secondary', 
      icon: <Clock className="w-3 h-3" />,
      color: 'bg-yellow-100 text-yellow-800 border-yellow-300'
    },
    scheduled: { 
      variant: 'secondary', 
      icon: <Clock className="w-3 h-3" />,
      color: 'bg-blue-100 text-blue-800 border-blue-300'
    },
    processing: { 
      variant: 'default', 
      icon: <Activity className="w-3 h-3 animate-pulse" />,
      color: 'bg-purple-100 text-purple-800 border-purple-300'
    },
    running: { 
      variant: 'default', 
      icon: <Activity className="w-3 h-3 animate-pulse" />,
      color: 'bg-green-100 text-green-800 border-green-300'
    },
    completed: { 
      variant: 'success' as const, 
      icon: <CheckCircle className="w-3 h-3" />,
      color: 'bg-emerald-100 text-emerald-800 border-emerald-300'
    },
    failed: { 
      variant: 'destructive', 
      icon: <AlertCircle className="w-3 h-3" />,
      color: 'bg-red-100 text-red-800 border-red-300'
    },
    cancelled: { 
      variant: 'outline', 
      icon: <XCircle className="w-3 h-3" />,
      color: 'bg-gray-100 text-gray-800 border-gray-300'
    },
    created: { 
      variant: 'secondary', 
      icon: <Clock className="w-3 h-3" />,
      color: 'bg-gray-100 text-gray-800 border-gray-300'
    },
    preparing: { 
      variant: 'secondary', 
      icon: <Clock className="w-3 h-3" />,
      color: 'bg-blue-100 text-blue-800 border-blue-300'
    },
    paused: { 
      variant: 'outline', 
      icon: <PauseCircle className="w-3 h-3" />,
      color: 'bg-orange-100 text-orange-800 border-orange-300'
    },
  }

  const { icon, color } = variants[status] || { 
    variant: 'secondary', 
    icon: null,
    color: 'bg-gray-100 text-gray-800'
  }

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${color}`}>
      {showIcon && icon}
      {status}
    </span>
  )
}

// ============================================================================
// Scheduler Status Card
// ============================================================================

const SchedulerStatusCard: React.FC = () => {
  const { schedulerState, startScheduler, stopScheduler, loadSchedulerState } = useAgentStore()
  const isMobile = useIsMobile()

  useEffect(() => {
    loadSchedulerState()
    const interval = setInterval(loadSchedulerState, 5000)
    return () => clearInterval(interval)
  }, [loadSchedulerState])

  if (!schedulerState) {
    return (
      <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 text-muted-foreground">
            <RotateCw className="w-4 h-4 animate-spin" />
            <span className="text-sm">Loading scheduler status...</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 border-blue-200 dark:border-blue-800">
      <CardContent className="p-4">
        <div className={`flex ${isMobile ? 'flex-col gap-3' : 'items-center justify-between'}`}>
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${schedulerState.is_running ? 'bg-green-500/20' : 'bg-gray-500/20'}`}>
              <Cpu className={`w-5 h-5 ${schedulerState.is_running ? 'text-green-600' : 'text-gray-600'}`} />
            </div>
            <div>
              <p className="font-medium text-sm">Agent Scheduler</p>
              <p className="text-xs text-muted-foreground">
                {schedulerState.is_running ? 'Running' : 'Stopped'} • {schedulerState.active_agent_count} active
              </p>
            </div>
          </div>
          
          <div className={`flex items-center gap-4 ${isMobile ? 'justify-between w-full' : ''}`}>
            <div className="flex items-center gap-4 text-sm">
              <div className="text-center">
                <p className="text-lg font-bold">{schedulerState.total_processed}</p>
                <p className="text-xs text-muted-foreground">Processed</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-destructive">{schedulerState.total_failed}</p>
                <p className="text-xs text-muted-foreground">Failed</p>
              </div>
            </div>
            
            <Button
              variant={schedulerState.is_running ? "outline" : "default"}
              size="sm"
              onClick={schedulerState.is_running ? stopScheduler : startScheduler}
              className="flex items-center gap-1"
            >
              {schedulerState.is_running ? (
                <><PauseCircle className="w-4 h-4" /> Stop</>
              ) : (
                <><PlayCircle className="w-4 h-4" /> Start</>
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ============================================================================
// Prompt Input Component
// ============================================================================

const PromptInput: React.FC = () => {
  const [content, setContent] = useState('')
  const [priority, setPriority] = useState(5)
  const [promptType, setPromptType] = useState('general')
  const { submitPrompt, isLoading } = useAgentStore()
  const isMobile = useIsMobile()
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = async () => {
    if (!content.trim()) return
    await submitPrompt(content, { priority, prompt_type: promptType })
    setContent('')
    // 自动调整高度
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handleSubmit()
    }
  }

  const adjustHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px'
    }
  }

  const promptTypes = [
    { value: 'general', label: '通用', icon: '✨' },
    { value: 'code', label: '代码', icon: '💻' },
    { value: 'analysis', label: '分析', icon: '📊' },
    { value: 'writing', label: '写作', icon: '✍️' },
    { value: 'data', label: '数据', icon: '📈' },
  ]

  return (
    <Card className="border-primary/20 shadow-lg">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Sparkles className="w-5 h-5 text-primary" />
          新建任务
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Prompt Type Selection */}
        <div className="flex flex-wrap gap-2">
          {promptTypes.map((type) => (
            <button
              key={type.value}
              onClick={() => setPromptType(type.value)}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-full text-sm transition-colors ${
                promptType === type.value
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted hover:bg-muted/80'
              }`}
            >
              <span>{type.icon}</span>
              <span>{type.label}</span>
            </button>
          ))}
        </div>

        {/* Text Input */}
        <Textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => {
            setContent(e.target.value)
            adjustHeight()
          }}
          onKeyDown={handleKeyDown}
          placeholder="输入你的任务描述... (Ctrl+Enter 快速提交)"
          className="min-h-[120px] resize-none border-muted-foreground/20 focus:border-primary"
          disabled={isLoading}
        />

        {/* Controls */}
        <div className={`flex ${isMobile ? 'flex-col gap-3' : 'items-center justify-between'}`}>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Label className="text-sm text-muted-foreground">优先级:</Label>
              <Select value={String(priority)} onValueChange={(v) => setPriority(Number(v))}>
                <SelectTrigger className="w-20">
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
          </div>

          <Button
            onClick={handleSubmit}
            disabled={isLoading || !content.trim()}
            className="flex items-center gap-2"
            size={isMobile ? 'default' : 'lg'}
          >
            {isLoading ? (
              <RotateCw className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            {isLoading ? '提交中...' : '提交任务'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

// ============================================================================
// Task History List
// ============================================================================

const TaskHistoryList: React.FC<{
  onSelectTask: (taskId: number) => void
  selectedTaskId: number | null
}> = ({ onSelectTask, selectedTaskId }) => {
  const { tasks, prompts, loadTasks, loadPrompts, cancelTask } = useAgentStore()
  const isMobile = useIsMobile()

  useEffect(() => {
    loadTasks()
    loadPrompts()
  }, [loadTasks, loadPrompts])

  // 合并 tasks 和 prompts 数据
  const taskList = tasks.map((task) => {
    const prompt = prompts.find((p) => p.id === task.prompt_id)
    return {
      ...task,
      promptContent: prompt?.content || 'Unknown prompt',
    }
  })

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-base">
          <span className="flex items-center gap-2">
            <History className="w-4 h-4" />
            任务历史
          </span>
          <Button variant="ghost" size="sm" onClick={() => loadTasks()}>
            <RotateCw className="w-4 h-4" />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className={isMobile ? 'h-[300px]' : 'h-[calc(100vh-400px)]'}>
          <div className="space-y-1 p-3">
            {taskList.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Bot className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p className="text-sm">暂无任务</p>
                <p className="text-xs mt-1">提交一个 Prompt 开始</p>
              </div>
            ) : (
              taskList.map((task) => (
                <div
                  key={task.id}
                  onClick={() => onSelectTask(task.id)}
                  className={`p-3 rounded-lg cursor-pointer transition-all border ${
                    selectedTaskId === task.id
                      ? 'border-primary bg-primary/5 shadow-sm'
                      : 'border-transparent hover:bg-muted'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {task.promptContent.slice(0, 50)}
                        {task.promptContent.length > 50 ? '...' : ''}
                      </p>
                    </div>
                    <StatusBadge status={task.status} showIcon={false} />
                  </div>
                  
                  <div className="space-y-2">
                    <Progress value={task.progress} className="h-1.5" />
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>#{task.id} • {task.agent_type}</span>
                      <span>{task.progress}%</span>
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
  )
}

// ============================================================================
// Task Detail Panel
// ============================================================================

const TaskDetailPanel: React.FC<{ taskId: number | null }> = ({ taskId }) => {
  const { currentTask, loadTaskDetail, isLoading } = useAgentStore()
  const isMobile = useIsMobile()

  useEffect(() => {
    if (taskId) {
      loadTaskDetail(taskId)
    }
  }, [taskId, loadTaskDetail])

  if (!taskId || !currentTask) {
    return (
      <Card className="h-full flex items-center justify-center">
        <div className="text-center p-8 text-muted-foreground">
          <MessageSquare className="w-16 h-16 mx-auto mb-4 opacity-20" />
          <p className="text-lg font-medium">选择一个任务查看详情</p>
          <p className="text-sm mt-2">点击左侧任务列表中的项目</p>
        </div>
      </Card>
    )
  }

  const { task, steps, outputs, prompt } = currentTask

  return (
    <Card className="h-full">
      <CardHeader className="pb-3 border-b">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <CardTitle className="text-base flex items-center gap-2 mb-1">
              <Terminal className="w-4 h-4" />
              任务 #{task.id}
            </CardTitle>
            <p className="text-sm text-muted-foreground line-clamp-2">
              {prompt.content}
            </p>
          </div>
          <StatusBadge status={task.status} />
        </div>
      </CardHeader>
      
      <CardContent className="p-0">
        <ScrollArea className={isMobile ? 'h-[400px]' : 'h-[calc(100vh-380px)]'}>
          <div className="p-4 space-y-6">
            {/* Progress */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">执行进度</span>
                <span className="text-sm font-bold">{task.progress}%</span>
              </div>
              <Progress value={task.progress} className="h-2" />
            </div>

            {/* Steps */}
            {steps.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <Activity className="w-4 h-4" />
                  执行步骤
                </h4>
                <div className="space-y-2">
                  {steps.map((step, index) => (
                    <div
                      key={step.id}
                      className="flex gap-3 p-3 rounded-lg bg-muted/50 border border-muted"
                    >
                      <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center text-xs font-medium">
                        {index + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="outline" className="text-xs capitalize">
                            {step.step_type}
                          </Badge>
                          {step.title && (
                            <span className="text-sm font-medium">{step.title}</span>
                          )}
                        </div>
                        {step.content_summary && (
                          <p className="text-xs text-muted-foreground">
                            {step.content_summary}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Outputs */}
            {outputs.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4" />
                  输出结果
                </h4>
                {outputs.map((output) => (
                  <div
                    key={output.id}
                    className="p-4 rounded-lg bg-muted border border-muted"
                  >
                    <Badge variant="secondary" className="mb-2">
                      {output.output_type}
                    </Badge>
                    <pre className="text-sm whitespace-pre-wrap font-mono bg-background p-3 rounded border">
                      {output.content}
                    </pre>
                  </div>
                ))}
              </div>
            )}

            {/* Error */}
            {task.error_message && (
              <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/30">
                <div className="flex items-center gap-2 mb-2 text-destructive">
                  <AlertCircle className="w-4 h-4" />
                  <span className="font-medium">执行错误</span>
                </div>
                <p className="text-sm text-destructive/80">{task.error_message}</p>
              </div>
            )}

            {/* Task Info */}
            <div className="pt-4 border-t">
              <h4 className="text-sm font-medium mb-2">任务信息</h4>
              <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                <div>Agent 类型: <span className="text-foreground">{task.agent_type}</span></div>
                <div>创建时间: <span className="text-foreground">{new Date(task.created_at).toLocaleString()}</span></div>
                {task.started_at && (
                  <div>开始时间: <span className="text-foreground">{new Date(task.started_at).toLocaleString()}</span></div>
                )}
                {task.completed_at && (
                  <div>完成时间: <span className="text-foreground">{new Date(task.completed_at).toLocaleString()}</span></div>
                )}
              </div>
            </div>
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

// ============================================================================
// Quick Templates
// ============================================================================

const QuickTemplates: React.FC<{ onSelect: (content: string) => void }> = ({ onSelect }) => {
  const templates = [
    { 
      icon: '💻', 
      title: '代码审查', 
      desc: '审查代码质量和潜在问题',
      content: '请帮我审查以下代码，找出潜在的问题和改进建议：\n\n```\n// 粘贴你的代码 here\n```'
    },
    { 
      icon: '📊', 
      title: '数据分析', 
      desc: '分析数据并生成报告',
      content: '请分析以下数据并提供洞察：\n\n数据描述：\n- \n\n分析目标：\n- '
    },
    { 
      icon: '✍️', 
      title: '文档生成', 
      desc: '生成技术文档或说明',
      content: '请帮我生成一份关于 [主题] 的技术文档，包含以下内容：\n\n1. 概述\n2. 详细说明\n3. 示例\n4. 注意事项'
    },
    { 
      icon: '🤔', 
      title: '问题解答', 
      desc: '解答技术或概念问题',
      content: '我有一个问题：\n\n问题：\n\n背景信息：\n\n期望的回答方向：'
    },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {templates.map((template) => (
        <button
          key={template.title}
          onClick={() => onSelect(template.content)}
          className="p-3 rounded-lg border border-muted bg-card hover:bg-muted/50 hover:border-primary/30 transition-all text-left"
        >
          <div className="text-2xl mb-2">{template.icon}</div>
          <div className="font-medium text-sm">{template.title}</div>
          <div className="text-xs text-muted-foreground mt-1">{template.desc}</div>
        </button>
      ))}
    </div>
  )
}

// ============================================================================
// Main Agent Page
// ============================================================================

const AgentPage: React.FC = () => {
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const { connectRealtimeUpdates, disconnectRealtimeUpdates, error, clearError } = useAgentStore()
  const isMobile = useIsMobile()

  useEffect(() => {
    connectRealtimeUpdates()
    return () => disconnectRealtimeUpdates()
  }, [connectRealtimeUpdates, disconnectRealtimeUpdates])

  return (
    <PageLayout>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Bot className="w-7 h-7 text-primary" />
              AI Agent
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              智能任务助手 • 自动化处理 • 持续学习
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

        {/* Scheduler Status */}
        <SchedulerStatusCard />

        {/* Main Content */}
        <div className={`grid gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-12'}`}>
          {/* Left Column - Input & Templates */}
          <div className={`space-y-4 ${isMobile ? '' : 'col-span-5'}`}>
            <PromptInput />
            
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">快速模板</CardTitle>
              </CardHeader>
              <CardContent>
                <QuickTemplates onSelect={(content) => {
                  // 可以通过全局状态或 ref 设置到 PromptInput
                  console.log('Selected template:', content)
                }} />
              </CardContent>
            </Card>
          </div>

          {/* Right Column - Task History & Detail */}
          <div className={`space-y-4 ${isMobile ? '' : 'col-span-7'}`}>
            <div className={`grid gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-2'}`}>
              <TaskHistoryList 
                onSelectTask={setSelectedTaskId}
                selectedTaskId={selectedTaskId}
              />
              <TaskDetailPanel taskId={selectedTaskId} />
            </div>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}

export default AgentPage

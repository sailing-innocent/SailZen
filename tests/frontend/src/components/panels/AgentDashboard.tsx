import { useEffect, useState } from 'react'
import { 
  Monitor, Apple, Server, Activity, CheckCircle, XCircle, Clock, 
  Wifi, WifiOff, Cpu, MemoryStick, HardDrive, PlayCircle, ChevronRight
} from 'lucide-react'
import { useAgentStore } from '../../store/useAgentStore'
import type { Agent, AgentTask, OpenCodeSession } from '../../types'
import { cn } from '../../lib/utils'

const PLATFORM_ICON: Record<string, typeof Monitor> = {
  windows: Monitor,
  macos: Apple,
  linux: Server,
}

const STATUS_COLORS: Record<string, string> = {
  online: 'bg-emerald-500',
  offline: 'bg-slate-500',
  busy: 'bg-amber-500',
  maintenance: 'bg-purple-500',
}

const TASK_STATUS_COLORS: Record<string, string> = {
  pending: 'text-slate-400',
  assigned: 'text-blue-400',
  running: 'text-amber-400',
  success: 'text-emerald-400',
  failed: 'text-red-400',
}

interface Props {
  onClose?: () => void
}

export default function AgentDashboard({ onClose }: Props) {
  const {
    agents, tasks, sessions, stats, skills,
    selectedAgentId, selectedAgentDetail,
    loadAll, selectAgent, startPolling, stopPolling, dispatchTask, startSession
  } = useAgentStore()

  const [showTaskForm, setShowTaskForm] = useState(false)
  const [selectedSkill, setSelectedSkill] = useState<string>('')
  const [selectedTargetAgent, setSelectedTargetAgent] = useState<string>('')

  useEffect(() => {
    loadAll()
    startPolling(3000)
    return () => stopPolling()
  }, [])

  const handleDispatchTask = async () => {
    if (!selectedSkill) return
    try {
      const task = await dispatchTask(selectedSkill, selectedTargetAgent || undefined, {
        working_dir: selectedAgentDetail?.agent.working_dir || '.',
      })
      // 自动创建Session执行任务
      if (task.agent_id) {
        await startSession(
          task.agent_id,
          task.id,
          selectedSkill,
          selectedAgentDetail?.agent.working_dir || '.',
          {}
        )
      }
      setShowTaskForm(false)
      setSelectedSkill('')
      setSelectedTargetAgent('')
    } catch (e) {
      console.error('Failed to dispatch task:', e)
    }
  }

  return (
    <div className="h-full flex flex-col bg-slate-950 text-slate-100">
      {/* Header Stats */}
      <div className="flex-shrink-0 p-4 border-b border-slate-800 bg-slate-900">
        <div className="flex items-center gap-6">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Activity className="text-blue-400" size={20} />
            Multi-Agent Dashboard
          </h2>
          {stats && (
            <div className="flex gap-4 text-sm">
              <StatBadge label="Agents" value={`${stats.online_agents}/${stats.total_agents}`} color="blue" />
              <StatBadge label="Running" value={stats.running_tasks} color="amber" />
              <StatBadge label="Completed" value={stats.completed_tasks} color="emerald" />
              <StatBadge label="Failed" value={stats.failed_tasks} color="red" />
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* Agent List */}
        <div className="w-72 flex-shrink-0 border-r border-slate-800 bg-slate-900 overflow-y-auto">
          <div className="p-3 border-b border-slate-800 flex justify-between items-center">
            <h3 className="text-sm font-semibold text-slate-400">Agents</h3>
            <span className="text-xs text-slate-500">{agents.length} total</span>
          </div>
          <div className="p-2 space-y-2">
            {agents.length === 0 ? (
              <div className="text-center text-slate-500 py-8">
                <Server className="mx-auto mb-2 opacity-30" size={32} />
                <p className="text-sm">No agents registered</p>
                <p className="text-xs mt-1">Start an agent to see it here</p>
              </div>
            ) : (
              agents.map(agent => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  isSelected={selectedAgentId === agent.id}
                  onClick={() => selectAgent(agent.id)}
                />
              ))
            )}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {selectedAgentDetail ? (
            <AgentDetailView 
              detail={selectedAgentDetail} 
              sessions={sessions.filter(s => s.agent_id === selectedAgentId)}
              tasks={tasks.filter(t => t.agent_id === selectedAgentId)}
              skills={skills}
              onDispatchTask={() => setShowTaskForm(true)}
            />
          ) : (
            <div className="flex-1 flex flex-col">
              {/* Quick Actions */}
              <div className="p-4 border-b border-slate-800">
                <h3 className="text-sm font-semibold text-slate-400 mb-3">Quick Actions</h3>
                <div className="flex gap-2 flex-wrap">
                  {skills.slice(0, 6).map(skill => (
                    <button
                      key={skill.name}
                      onClick={() => {
                        setSelectedSkill(skill.name)
                        setShowTaskForm(true)
                      }}
                      className="px-3 py-1.5 text-xs rounded-lg border border-slate-700 hover:border-blue-500 hover:bg-blue-500/10 transition-colors"
                    >
                      {skill.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* Recent Tasks */}
              <div className="flex-1 overflow-y-auto p-4">
                <h3 className="text-sm font-semibold text-slate-400 mb-3">Recent Tasks</h3>
                <div className="space-y-2">
                  {tasks.slice(0, 20).map(task => (
                    <TaskRow key={task.id} task={task} />
                  ))}
                  {tasks.length === 0 && (
                    <div className="text-center text-slate-500 py-8">
                      <Clock className="mx-auto mb-2 opacity-30" size={32} />
                      <p className="text-sm">No tasks yet</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Active Sessions Panel */}
        {sessions.length > 0 && (
          <div className="w-80 flex-shrink-0 border-l border-slate-800 bg-slate-900 overflow-y-auto">
            <div className="p-3 border-b border-slate-800">
              <h3 className="text-sm font-semibold text-slate-400 flex items-center gap-2">
                <PlayCircle size={14} className="text-emerald-400" />
                Active Sessions ({sessions.length})
              </h3>
            </div>
            <div className="p-2 space-y-2">
              {sessions.map(session => (
                <SessionCard key={session.id} session={session} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Task Dispatch Modal */}
      {showTaskForm && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-6" onClick={() => setShowTaskForm(false)}>
          <div className="bg-slate-900 rounded-xl border border-slate-700 p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4">Dispatch Task</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">Skill</label>
                <select
                  value={selectedSkill}
                  onChange={e => setSelectedSkill(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm"
                >
                  <option value="">Select a skill...</option>
                  {skills.map(s => (
                    <option key={s.name} value={s.name}>{s.name} - {s.description}</option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm text-slate-400 mb-1">Target Agent (optional)</label>
                <select
                  value={selectedTargetAgent}
                  onChange={e => setSelectedTargetAgent(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm"
                >
                  <option value="">Auto-assign</option>
                  {agents.filter(a => a.status === 'online').map(a => (
                    <option key={a.id} value={a.id}>{a.name} ({a.platform})</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex gap-2 mt-6">
              <button
                onClick={() => setShowTaskForm(false)}
                className="flex-1 px-4 py-2 rounded-lg border border-slate-600 hover:bg-slate-800 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDispatchTask}
                disabled={!selectedSkill}
                className="flex-1 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Dispatch
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ================== Sub Components ==================

function StatBadge({ label, value, color }: { label: string; value: number | string; color: string }) {
  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-500/20 text-blue-400',
    amber: 'bg-amber-500/20 text-amber-400',
    emerald: 'bg-emerald-500/20 text-emerald-400',
    red: 'bg-red-500/20 text-red-400',
  }
  return (
    <div className={cn('px-2 py-1 rounded-md', colorClasses[color])}>
      <span className="opacity-70">{label}:</span> <span className="font-medium">{value}</span>
    </div>
  )
}

function AgentCard({ agent, isSelected, onClick }: { agent: Agent; isSelected: boolean; onClick: () => void }) {
  const PlatformIcon = PLATFORM_ICON[agent.platform] || Server
  const isOnline = agent.status === 'online' || agent.status === 'busy'

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left p-3 rounded-lg border transition-all',
        isSelected
          ? 'border-blue-500 bg-blue-500/10'
          : 'border-slate-700 hover:border-slate-500 hover:bg-slate-800'
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn(
          'p-2 rounded-lg',
          agent.platform === 'windows' ? 'bg-blue-500/20' : 
          agent.platform === 'macos' ? 'bg-slate-500/20' : 'bg-orange-500/20'
        )}>
          <PlatformIcon size={20} className={
            agent.platform === 'windows' ? 'text-blue-400' : 
            agent.platform === 'macos' ? 'text-slate-300' : 'text-orange-400'
          } />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm truncate">{agent.name}</span>
            {agent.role === 'manager' && (
              <span className="px-1.5 py-0.5 text-[10px] bg-purple-500/20 text-purple-400 rounded">Manager</span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={cn('w-2 h-2 rounded-full', STATUS_COLORS[agent.status])} />
            <span className="text-xs text-slate-400">{agent.status}</span>
            {isOnline ? (
              <Wifi size={12} className="text-emerald-400" />
            ) : (
              <WifiOff size={12} className="text-slate-500" />
            )}
          </div>
          {agent.capabilities.length > 0 && (
            <div className="flex gap-1 mt-2 flex-wrap">
              {agent.capabilities.slice(0, 3).map(cap => (
                <span key={cap} className="px-1.5 py-0.5 text-[10px] bg-slate-700 text-slate-300 rounded">
                  {cap}
                </span>
              ))}
              {agent.capabilities.length > 3 && (
                <span className="text-[10px] text-slate-500">+{agent.capabilities.length - 3}</span>
              )}
            </div>
          )}
        </div>
        <ChevronRight size={16} className="text-slate-500" />
      </div>
    </button>
  )
}

function AgentDetailView({ 
  detail, sessions, tasks, skills, onDispatchTask 
}: { 
  detail: AgentWithTasks
  sessions: OpenCodeSession[]
  tasks: AgentTask[]
  skills: { name: string; description: string }[]
  onDispatchTask: () => void
}) {
  const { agent, current_task, recent_tasks, active_sessions } = detail
  const PlatformIcon = PLATFORM_ICON[agent.platform] || Server

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Agent Header */}
      <div className="p-6 border-b border-slate-800 bg-gradient-to-r from-slate-900 to-slate-800">
        <div className="flex items-center gap-4">
          <div className={cn(
            'p-4 rounded-xl',
            agent.platform === 'windows' ? 'bg-blue-500/20' : 
            agent.platform === 'macos' ? 'bg-slate-500/20' : 'bg-orange-500/20'
          )}>
            <PlatformIcon size={32} className={
              agent.platform === 'windows' ? 'text-blue-400' : 
              agent.platform === 'macos' ? 'text-slate-300' : 'text-orange-400'
            } />
          </div>
          <div>
            <h2 className="text-xl font-bold">{agent.name}</h2>
            <div className="flex items-center gap-3 mt-1 text-sm text-slate-400">
              <span>{agent.host}:{agent.port}</span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <span className={cn('w-2 h-2 rounded-full', STATUS_COLORS[agent.status])} />
                {agent.status}
              </span>
              {agent.role === 'manager' && (
                <>
                  <span>•</span>
                  <span className="text-purple-400">Manager</span>
                </>
              )}
            </div>
          </div>
          <div className="ml-auto">
            <button
              onClick={onDispatchTask}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors"
            >
              Dispatch Task
            </button>
          </div>
        </div>

        {/* Capabilities */}
        <div className="mt-4 flex gap-2 flex-wrap">
          {agent.capabilities.map(cap => (
            <span key={cap} className="px-2 py-1 text-xs bg-slate-700 text-slate-300 rounded-md">
              {cap}
            </span>
          ))}
        </div>
      </div>

      {/* Current Task */}
      {current_task && (
        <div className="p-4 border-b border-slate-800 bg-amber-500/5">
          <h3 className="text-sm font-semibold text-amber-400 mb-2 flex items-center gap-2">
            <Activity size={14} />
            Current Task
          </h3>
          <TaskRow task={current_task} expanded />
        </div>
      )}

      {/* Active Sessions */}
      {active_sessions.length > 0 && (
        <div className="p-4 border-b border-slate-800">
          <h3 className="text-sm font-semibold text-slate-400 mb-3">Active Sessions</h3>
          <div className="space-y-2">
            {active_sessions.map(session => (
              <SessionCard key={session.id} session={session} expanded />
            ))}
          </div>
        </div>
      )}

      {/* Recent Tasks */}
      <div className="p-4">
        <h3 className="text-sm font-semibold text-slate-400 mb-3">Recent Tasks</h3>
        <div className="space-y-2">
          {recent_tasks.map(task => (
            <TaskRow key={task.id} task={task} />
          ))}
          {recent_tasks.length === 0 && (
            <p className="text-sm text-slate-500">No recent tasks</p>
          )}
        </div>
      </div>
    </div>
  )
}

function TaskRow({ task, expanded }: { task: AgentTask; expanded?: boolean }) {
  const statusIcon = {
    pending: Clock,
    assigned: Activity,
    running: Activity,
    success: CheckCircle,
    failed: XCircle,
  }[task.status] || Clock
  const StatusIcon = statusIcon

  return (
    <div className={cn(
      'p-3 rounded-lg border border-slate-700 bg-slate-800/50',
      expanded && 'border-amber-500/30'
    )}>
      <div className="flex items-center gap-3">
        <StatusIcon size={16} className={TASK_STATUS_COLORS[task.status]} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm">{task.task_type}</span>
            <span className={cn('text-xs', TASK_STATUS_COLORS[task.status])}>{task.status}</span>
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            ID: {task.id} • Priority: {task.priority}
          </div>
        </div>
        {task.started_at && (
          <span className="text-xs text-slate-500">
            {new Date(task.started_at).toLocaleTimeString()}
          </span>
        )}
      </div>
      {expanded && task.result && (
        <div className="mt-3 p-2 bg-slate-900 rounded text-xs font-mono overflow-x-auto">
          <pre>{JSON.stringify(task.result, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

function SessionCard({ session, expanded }: { session: OpenCodeSession; expanded?: boolean }) {
  const isActive = session.status === 'running' || session.status === 'starting'
  
  return (
    <div className={cn(
      'p-3 rounded-lg border',
      isActive ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-slate-700 bg-slate-800/50'
    )}>
      <div className="flex items-center gap-3">
        <div className={cn(
          'w-2 h-2 rounded-full',
          isActive ? 'bg-emerald-500 animate-pulse' : 'bg-slate-500'
        )} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm">{session.skill}</span>
            <span className={cn(
              'text-xs',
              isActive ? 'text-emerald-400' : 'text-slate-400'
            )}>{session.status}</span>
          </div>
          <div className="text-xs text-slate-500 mt-0.5 truncate">
            {session.working_dir}
          </div>
        </div>
      </div>
      
      {/* Live Logs */}
      {(expanded || isActive) && session.logs.length > 0 && (
        <div className="mt-3 max-h-32 overflow-y-auto">
          <div className="p-2 bg-slate-900 rounded text-xs font-mono space-y-0.5">
            {session.logs.slice(-5).map((log, i) => (
              <div key={i} className="text-slate-300 whitespace-pre-wrap">{log}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Agent Monitor Component
 * 用于调试 Agent 系统的 UI 状态
 */

import React, { useEffect, useState } from 'react';
import { useAgentStore } from '@/lib/store/agentStore';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  Play, 
  Square, 
  RotateCw, 
  AlertCircle, 
  CheckCircle, 
  Clock,
  Terminal,
  Activity
} from 'lucide-react';

// ============================================================================
// Status Badge Component
// ============================================================================

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const variants: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; icon: React.ReactNode }> = {
    pending: { variant: 'secondary', icon: <Clock className="w-3 h-3 mr-1" /> },
    scheduled: { variant: 'secondary', icon: <Clock className="w-3 h-3 mr-1" /> },
    processing: { variant: 'default', icon: <Activity className="w-3 h-3 mr-1" /> },
    running: { variant: 'default', icon: <Activity className="w-3 h-3 mr-1" /> },
    completed: { variant: 'default', icon: <CheckCircle className="w-3 h-3 mr-1" /> },
    failed: { variant: 'destructive', icon: <AlertCircle className="w-3 h-3 mr-1" /> },
    cancelled: { variant: 'outline', icon: <Square className="w-3 h-3 mr-1" /> },
    created: { variant: 'secondary', icon: <Clock className="w-3 h-3 mr-1" /> },
    preparing: { variant: 'secondary', icon: <Clock className="w-3 h-3 mr-1" /> },
    paused: { variant: 'outline', icon: <Clock className="w-3 h-3 mr-1" /> },
  };

  const { variant, icon } = variants[status] || { variant: 'secondary', icon: null };

  return (
    <Badge variant={variant} className="flex items-center">
      {icon}
      {status}
    </Badge>
  );
};

// ============================================================================
// Scheduler Status Component
// ============================================================================

const SchedulerStatus: React.FC = () => {
  const { schedulerState, startScheduler, stopScheduler, loadSchedulerState, isLoading } = useAgentStore();

  useEffect(() => {
    loadSchedulerState();
    const interval = setInterval(loadSchedulerState, 5000);
    return () => clearInterval(interval);
  }, [loadSchedulerState]);

  if (!schedulerState) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="w-5 h-5" />
            Scheduler Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">Loading...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="w-5 h-5" />
          Scheduler Status
          <StatusBadge status={schedulerState.is_running ? 'running' : 'stopped'} />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Active Agents</p>
              <p className="text-2xl font-bold">{schedulerState.active_agent_count}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Max Concurrent</p>
              <p className="text-2xl font-bold">{schedulerState.max_concurrent_agents}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Total Processed</p>
              <p className="text-2xl font-bold">{schedulerState.total_processed}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Total Failed</p>
              <p className="text-2xl font-bold text-destructive">{schedulerState.total_failed}</p>
            </div>
          </div>
          
          <div className="flex gap-2">
            {schedulerState.is_running ? (
              <Button 
                variant="destructive" 
                onClick={stopScheduler}
                disabled={isLoading}
                className="flex items-center gap-2"
              >
                <Square className="w-4 h-4" />
                Stop Scheduler
              </Button>
            ) : (
              <Button 
                onClick={startScheduler}
                disabled={isLoading}
                className="flex items-center gap-2"
              >
                <Play className="w-4 h-4" />
                Start Scheduler
              </Button>
            )}
            <Button 
              variant="outline" 
              onClick={loadSchedulerState}
              disabled={isLoading}
              className="flex items-center gap-2"
            >
              <RotateCw className="w-4 h-4" />
              Refresh
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// ============================================================================
// Task List Component
// ============================================================================

const TaskList: React.FC = () => {
  const { tasks, loadTasks, cancelTask, loadTaskDetail, isLoading } = useAgentStore();
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const handleSelectTask = (taskId: number) => {
    setSelectedTaskId(taskId);
    loadTaskDetail(taskId);
  };

  return (
    <Card className="h-[500px]">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Terminal className="w-5 h-5" />
            Tasks
          </span>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => loadTasks()}
            disabled={isLoading}
          >
            <RotateCw className="w-4 h-4" />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px]">
          <div className="space-y-2">
            {tasks.length === 0 ? (
              <p className="text-muted-foreground text-center py-8">No tasks yet</p>
            ) : (
              tasks.map((task) => (
                <div
                  key={task.id}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedTaskId === task.id 
                      ? 'border-primary bg-primary/5' 
                      : 'hover:bg-muted'
                  }`}
                  onClick={() => handleSelectTask(task.id)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium">Task #{task.id}</span>
                    <StatusBadge status={task.status} />
                  </div>
                  <div className="space-y-2">
                    <Progress value={task.progress} className="h-2" />
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <span>Type: {task.agent_type}</span>
                      <span>{task.progress}%</span>
                    </div>
                    {task.step_count > 0 && (
                      <p className="text-xs text-muted-foreground">
                        {task.step_count} steps
                      </p>
                    )}
                  </div>
                  {task.status === 'running' && (
                    <Button
                      variant="destructive"
                      size="sm"
                      className="mt-2 w-full"
                      onClick={(e) => {
                        e.stopPropagation();
                        cancelTask(task.id);
                      }}
                    >
                      Cancel
                    </Button>
                  )}
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

// ============================================================================
// Task Detail Component
// ============================================================================

const TaskDetail: React.FC = () => {
  const { currentTask } = useAgentStore();

  if (!currentTask) {
    return (
      <Card className="h-[500px]">
        <CardHeader>
          <CardTitle>Task Detail</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-center py-8">
            Select a task to view details
          </p>
        </CardContent>
      </Card>
    );
  }

  const { task, steps, outputs, prompt } = currentTask;

  return (
    <Card className="h-[500px]">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Task #{task.id}</span>
          <StatusBadge status={task.status} />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px]">
          <div className="space-y-4">
            {/* Prompt Info */}
            <div className="p-3 bg-muted rounded-lg">
              <p className="text-sm font-medium mb-1">Prompt:</p>
              <p className="text-sm text-muted-foreground">{prompt.content}</p>
            </div>

            {/* Progress */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Progress</span>
                <span className="text-sm">{task.progress}%</span>
              </div>
              <Progress value={task.progress} className="h-2" />
            </div>

            {/* Steps */}
            {steps.length > 0 && (
              <div>
                <p className="text-sm font-medium mb-2">Steps:</p>
                <div className="space-y-2">
                  {steps.map((step) => (
                    <div
                      key={step.id}
                      className="p-2 border rounded text-sm"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className="text-xs">
                          {step.step_type}
                        </Badge>
                        <span className="font-medium">{step.title}</span>
                      </div>
                      {step.content_summary && (
                        <p className="text-muted-foreground text-xs">
                          {step.content_summary}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Outputs */}
            {outputs.length > 0 && (
              <div>
                <p className="text-sm font-medium mb-2">Outputs:</p>
                {outputs.map((output) => (
                  <div
                    key={output.id}
                    className="p-2 border rounded text-sm"
                  >
                    <Badge variant="outline" className="text-xs mb-1">
                      {output.output_type}
                    </Badge>
                    <p className="text-muted-foreground whitespace-pre-wrap">
                      {output.content}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {/* Error */}
            {task.error_message && (
              <div className="p-3 bg-destructive/10 border border-destructive rounded-lg">
                <p className="text-sm font-medium text-destructive">Error:</p>
                <p className="text-sm text-destructive">{task.error_message}</p>
              </div>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

// ============================================================================
// Prompt Form Component
// ============================================================================

const PromptForm: React.FC = () => {
  const [content, setContent] = useState('');
  const [priority, setPriority] = useState(5);
  const { submitPrompt, isLoading } = useAgentStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;
    
    await submitPrompt(content, { priority });
    setContent('');
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Submit Prompt</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Enter your prompt here..."
              className="w-full h-24 p-3 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary"
              disabled={isLoading}
            />
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium">Priority:</label>
              <input
                type="number"
                min={1}
                max={10}
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                className="w-16 p-2 border rounded"
                disabled={isLoading}
              />
            </div>
            <Button 
              type="submit" 
              disabled={isLoading || !content.trim()}
              className="flex items-center gap-2"
            >
              {isLoading ? (
                <RotateCw className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              Submit
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
};

// ============================================================================
// Main Agent Monitor Component
// ============================================================================

export const AgentMonitor: React.FC = () => {
  const { connectRealtimeUpdates, disconnectRealtimeUpdates, error, clearError } = useAgentStore();

  useEffect(() => {
    connectRealtimeUpdates();
    return () => disconnectRealtimeUpdates();
  }, [connectRealtimeUpdates, disconnectRealtimeUpdates]);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold">Agent Monitor</h1>
      
      {error && (
        <div className="p-4 bg-destructive/10 border border-destructive rounded-lg flex items-center justify-between">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" size="sm" onClick={clearError}>
            Dismiss
          </Button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <SchedulerStatus />
          <PromptForm />
        </div>
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <TaskList />
            <TaskDetail />
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentMonitor;

/**
 * Agent Store
 * Zustand store for managing Agent state
 */

import { create } from 'zustand';
import { agentAPI, AgentTask, AgentStep, AgentOutput, UserPrompt, SchedulerState, AgentStreamEvent } from '@/lib/api/agent';

// ============================================================================
// Types
// ============================================================================

interface AgentState {
  // Data
  prompts: UserPrompt[];
  tasks: AgentTask[];
  currentTask: {
    task: AgentTask;
    steps: AgentStep[];
    outputs: AgentOutput[];
    prompt: UserPrompt;
  } | null;
  schedulerState: SchedulerState | null;
  
  // UI State
  isLoading: boolean;
  error: string | null;
  wsConnection: WebSocket | null;
  
  // Actions - Prompts
  submitPrompt: (content: string, options?: Partial<UserPrompt>) => Promise<void>;
  loadPrompts: (params?: { status?: string }) => Promise<void>;
  cancelPrompt: (id: number) => Promise<void>;
  deletePrompt: (id: number) => Promise<void>;
  
  // Actions - Tasks
  loadTasks: (params?: { status?: string }) => Promise<void>;
  loadTaskDetail: (id: number) => Promise<void>;
  cancelTask: (id: number) => Promise<void>;
  
  // Actions - Scheduler
  loadSchedulerState: () => Promise<void>;
  startScheduler: () => Promise<void>;
  stopScheduler: () => Promise<void>;
  
  // Actions - WebSocket
  connectRealtimeUpdates: () => void;
  disconnectRealtimeUpdates: () => void;
  handleAgentEvent: (event: AgentStreamEvent) => void;
  
  // Actions - Utils
  clearError: () => void;
  clearCurrentTask: () => void;
}

// ============================================================================
// Store
// ============================================================================

export const useAgentStore = create<AgentState>((set, get) => ({
  // Initial State
  prompts: [],
  tasks: [],
  currentTask: null,
  schedulerState: null,
  isLoading: false,
  error: null,
  wsConnection: null,

  // --------------------------------------------------------------------------
  // Prompt Actions
  // --------------------------------------------------------------------------

  submitPrompt: async (content, options = {}) => {
    set({ isLoading: true, error: null });
    try {
      const prompt = await agentAPI.createPrompt({
        content,
        prompt_type: options.prompt_type || 'general',
        priority: options.priority || 5,
        context: options.context || {},
        session_id: options.session_id,
        parent_prompt_id: options.parent_prompt_id,
      });
      set((state) => ({ 
        prompts: [prompt, ...state.prompts],
        isLoading: false 
      }));
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to submit prompt', 
        isLoading: false 
      });
    }
  },

  loadPrompts: async (params) => {
    set({ isLoading: true, error: null });
    try {
      const prompts = await agentAPI.listPrompts(params);
      set({ prompts, isLoading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to load prompts', 
        isLoading: false 
      });
    }
  },

  cancelPrompt: async (id) => {
    set({ isLoading: true, error: null });
    try {
      const prompt = await agentAPI.cancelPrompt(id);
      set((state) => ({
        prompts: state.prompts.map((p) => (p.id === id ? prompt : p)),
        isLoading: false,
      }));
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to cancel prompt', 
        isLoading: false 
      });
    }
  },

  deletePrompt: async (id) => {
    set({ isLoading: true, error: null });
    try {
      await agentAPI.deletePrompt(id);
      set((state) => ({
        prompts: state.prompts.filter((p) => p.id !== id),
        isLoading: false,
      }));
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to delete prompt', 
        isLoading: false 
      });
    }
  },

  // --------------------------------------------------------------------------
  // Task Actions
  // --------------------------------------------------------------------------

  loadTasks: async (params) => {
    set({ isLoading: true, error: null });
    try {
      const tasks = await agentAPI.listTasks(params);
      set({ tasks, isLoading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to load tasks', 
        isLoading: false 
      });
    }
  },

  loadTaskDetail: async (id) => {
    set({ isLoading: true, error: null });
    try {
      const detail = await agentAPI.getTask(id);
      set({ currentTask: detail, isLoading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to load task detail', 
        isLoading: false 
      });
    }
  },

  cancelTask: async (id) => {
    set({ isLoading: true, error: null });
    try {
      const task = await agentAPI.cancelTask(id);
      set((state) => ({
        tasks: state.tasks.map((t) => (t.id === id ? task : t)),
        currentTask: state.currentTask?.task.id === id 
          ? { ...state.currentTask, task }
          : state.currentTask,
        isLoading: false,
      }));
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to cancel task', 
        isLoading: false 
      });
    }
  },

  // --------------------------------------------------------------------------
  // Scheduler Actions
  // --------------------------------------------------------------------------

  loadSchedulerState: async () => {
    try {
      const schedulerState = await agentAPI.getSchedulerStatus();
      set({ schedulerState });
    } catch (error) {
      console.error('Failed to load scheduler state:', error);
    }
  },

  startScheduler: async () => {
    set({ isLoading: true, error: null });
    try {
      const schedulerState = await agentAPI.startScheduler();
      set({ schedulerState, isLoading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to start scheduler', 
        isLoading: false 
      });
    }
  },

  stopScheduler: async () => {
    set({ isLoading: true, error: null });
    try {
      const schedulerState = await agentAPI.stopScheduler();
      set({ schedulerState, isLoading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to stop scheduler', 
        isLoading: false 
      });
    }
  },

  // --------------------------------------------------------------------------
  // WebSocket Actions
  // --------------------------------------------------------------------------

  connectRealtimeUpdates: () => {
    const { wsConnection, handleAgentEvent, loadTasks, loadSchedulerState } = get();
    
    // Close existing connection
    if (wsConnection) {
      wsConnection.close();
    }

    const ws = agentAPI.connectEventStream(
      (event) => {
        handleAgentEvent(event);
      },
      (error) => {
        console.error('WebSocket error:', error);
        // Try to reconnect after a delay
        setTimeout(() => {
          get().connectRealtimeUpdates();
        }, 5000);
      }
    );

    set({ wsConnection: ws });
    
    // Initial load
    loadTasks();
    loadSchedulerState();
  },

  disconnectRealtimeUpdates: () => {
    const { wsConnection } = get();
    if (wsConnection) {
      wsConnection.close();
      set({ wsConnection: null });
    }
  },

  handleAgentEvent: (event) => {
    const { tasks, currentTask, loadTaskDetail, loadSchedulerState } = get();
    
    switch (event.event_type) {
      case 'task_scheduled':
      case 'task_started':
        // Refresh task list to show new/updated task
        get().loadTasks();
        loadSchedulerState();
        break;
        
      case 'step_update':
        // Update current task steps if viewing the task
        if (currentTask?.task.id === event.task_id) {
          const newStep = event.data.step;
          set((state) => ({
            currentTask: state.currentTask ? {
              ...state.currentTask,
              steps: [...state.currentTask.steps, newStep],
            } : null,
          }));
        }
        break;
        
      case 'progress_update':
        // Update task progress
        set((state) => ({
          tasks: state.tasks.map((t) =>
            t.id === event.task_id ? { ...t, progress: event.data.progress } : t
          ),
          currentTask: state.currentTask?.task.id === event.task_id
            ? {
                ...state.currentTask,
                task: { ...state.currentTask.task, progress: event.data.progress },
              }
            : state.currentTask,
        }));
        break;
        
      case 'task_completed':
      case 'task_failed':
      case 'task_cancelled':
        // Refresh task and scheduler state
        get().loadTasks();
        loadSchedulerState();
        
        // If viewing the task, refresh detail
        if (currentTask?.task.id === event.task_id) {
          loadTaskDetail(event.task_id);
        }
        break;
        
      case 'output_ready':
        // Refresh task detail if viewing
        if (currentTask?.task.id === event.task_id) {
          loadTaskDetail(event.task_id);
        }
        break;
    }
  },

  // --------------------------------------------------------------------------
  // Utils
  // --------------------------------------------------------------------------

  clearError: () => set({ error: null }),
  
  clearCurrentTask: () => set({ currentTask: null }),
}));

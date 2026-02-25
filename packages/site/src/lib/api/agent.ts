/**
 * Agent API Client
 * 用于与后端 Agent 系统交互
 */

import { get_url } from "./config";

// ============================================================================
// Types
// ============================================================================

export interface UserPrompt {
  id: number;
  content: string;
  prompt_type: string;
  context: Record<string, any>;
  priority: number;
  status: 'pending' | 'scheduled' | 'processing' | 'completed' | 'failed' | 'cancelled';
  created_by?: string;
  session_id?: string;
  parent_prompt_id?: number;
  created_at: string;
  scheduled_at?: string;
  started_at?: string;
  completed_at?: string;
}

export interface AgentTask {
  id: number;
  prompt_id: number;
  agent_type: string;
  agent_config: Record<string, any>;
  status: 'created' | 'preparing' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  created_at: string;
  started_at?: string;
  updated_at?: string;
  completed_at?: string;
  error_message?: string;
  error_code?: string;
  step_count: number;
}

export interface AgentStep {
  id: number;
  task_id: number;
  step_number: number;
  step_type: 'thought' | 'action' | 'observation' | 'error' | 'completion';
  title?: string;
  content?: string;
  content_summary?: string;
  meta_data: Record<string, any>;
  created_at: string;
  duration_ms?: number;
}

export interface AgentOutput {
  id: number;
  task_id: number;
  output_type: 'text' | 'code' | 'file' | 'json' | 'error';
  content?: string;
  file_path?: string;
  meta_data: Record<string, any>;
  review_status: 'pending' | 'approved' | 'rejected';
  reviewed_by?: string;
  reviewed_at?: string;
  review_notes?: string;
  created_at: string;
}

export interface AgentTaskDetail {
  task: AgentTask;
  steps: AgentStep[];
  outputs: AgentOutput[];
  prompt: UserPrompt;
}

export interface SchedulerState {
  is_running: boolean;
  last_poll_at?: string;
  active_agent_count: number;
  max_concurrent_agents: number;
  total_processed: number;
  total_failed: number;
  updated_at?: string;
}

export interface CreatePromptRequest {
  content: string;
  prompt_type?: string;
  context?: Record<string, any>;
  priority?: number;
  session_id?: string;
  parent_prompt_id?: number;
}

export interface AgentStreamEvent {
  event_type: 'task_scheduled' | 'task_started' | 'step_update' | 'progress_update' | 'task_completed' | 'task_failed' | 'task_cancelled' | 'output_ready';
  task_id: number;
  timestamp: string;
  data: Record<string, any>;
}

// ============================================================================
// API Client
// ============================================================================

const API_BASE = '/api/v1/agent';

export class AgentAPI {
  private baseUrl: string;

  constructor() {
    this.baseUrl = (get_url() || '') + API_BASE;
  }

  // --------------------------------------------------------------------------
  // User Prompt APIs
  // --------------------------------------------------------------------------

  async createPrompt(request: CreatePromptRequest): Promise<UserPrompt> {
    const res = await fetch(`${this.baseUrl}/prompt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!res.ok) throw new Error(`Failed to create prompt: ${res.statusText}`);
    return res.json();
  }

  async listPrompts(params?: { status?: string; skip?: number; limit?: number }): Promise<UserPrompt[]> {
    const query = new URLSearchParams();
    if (params?.status) query.append('status', params.status);
    if (params?.skip !== undefined) query.append('skip', String(params.skip));
    if (params?.limit !== undefined) query.append('limit', String(params.limit));

    const res = await fetch(`${this.baseUrl}/prompt?${query}`);
    if (!res.ok) throw new Error(`Failed to list prompts: ${res.statusText}`);
    return res.json();
  }

  async getPrompt(id: number): Promise<UserPrompt> {
    const res = await fetch(`${this.baseUrl}/prompt/${id}`);
    if (!res.ok) throw new Error(`Failed to get prompt: ${res.statusText}`);
    return res.json();
  }

  async cancelPrompt(id: number): Promise<UserPrompt> {
    const res = await fetch(`${this.baseUrl}/prompt/${id}/cancel`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to cancel prompt: ${res.statusText}`);
    return res.json();
  }

  async deletePrompt(id: number): Promise<UserPrompt> {
    const res = await fetch(`${this.baseUrl}/prompt/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`Failed to delete prompt: ${res.statusText}`);
    return res.json();
  }

  // --------------------------------------------------------------------------
  // Agent Task APIs
  // --------------------------------------------------------------------------

  async listTasks(params?: { status?: string; skip?: number; limit?: number }): Promise<AgentTask[]> {
    const query = new URLSearchParams();
    if (params?.status) query.append('status', params.status);
    if (params?.skip !== undefined) query.append('skip', String(params.skip));
    if (params?.limit !== undefined) query.append('limit', String(params.limit));

    const res = await fetch(`${this.baseUrl}/task?${query}`);
    if (!res.ok) throw new Error(`Failed to list tasks: ${res.statusText}`);
    return res.json();
  }

  async getTask(id: number): Promise<AgentTaskDetail> {
    const res = await fetch(`${this.baseUrl}/task/${id}`);
    if (!res.ok) throw new Error(`Failed to get task: ${res.statusText}`);
    return res.json();
  }

  async getTaskSteps(id: number, params?: { skip?: number; limit?: number }): Promise<AgentStep[]> {
    const query = new URLSearchParams();
    if (params?.skip !== undefined) query.append('skip', String(params.skip));
    if (params?.limit !== undefined) query.append('limit', String(params.limit));

    const res = await fetch(`${this.baseUrl}/task/${id}/steps?${query}`);
    if (!res.ok) throw new Error(`Failed to get task steps: ${res.statusText}`);
    return res.json();
  }

  async cancelTask(id: number): Promise<AgentTask> {
    const res = await fetch(`${this.baseUrl}/task/${id}/cancel`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to cancel task: ${res.statusText}`);
    return res.json();
  }

  // --------------------------------------------------------------------------
  // Scheduler APIs
  // --------------------------------------------------------------------------

  async getSchedulerStatus(): Promise<SchedulerState> {
    const res = await fetch(`${this.baseUrl}/scheduler/status`);
    if (!res.ok) throw new Error(`Failed to get scheduler status: ${res.statusText}`);
    return res.json();
  }

  async startScheduler(): Promise<SchedulerState> {
    const res = await fetch(`${this.baseUrl}/scheduler/start`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to start scheduler: ${res.statusText}`);
    return res.json();
  }

  async stopScheduler(): Promise<SchedulerState> {
    const res = await fetch(`${this.baseUrl}/scheduler/stop`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to stop scheduler: ${res.statusText}`);
    return res.json();
  }

  async updateSchedulerConfig(maxConcurrentAgents: number): Promise<SchedulerState> {
    const res = await fetch(`${this.baseUrl}/scheduler/config?max_concurrent_agents=${maxConcurrentAgents}`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to update scheduler config: ${res.statusText}`);
    return res.json();
  }

  // --------------------------------------------------------------------------
  // WebSocket
  // --------------------------------------------------------------------------

  connectEventStream(onEvent: (event: AgentStreamEvent) => void, onError?: (error: Event) => void): WebSocket {
    // Build WebSocket URL - use window.location if baseUrl is relative
    let wsUrl: string;
    if (this.baseUrl.startsWith('http')) {
      wsUrl = this.baseUrl.replace(/^http/, 'ws') + '/ws/events';
    } else {
      // Relative URL - construct from current location
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      wsUrl = `${protocol}//${host}${this.baseUrl}/ws/events`;
    }
    console.log('Connecting to WebSocket:', wsUrl);
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onEvent(data);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onerror = (error) => {
      // Silently handle errors - onclose will handle reconnection
      onError?.(error);
    };

    ws.onclose = () => {
      console.log('WebSocket connection closed');
    };

    return ws;
  }
}

// Singleton instance
export const agentAPI = new AgentAPI();


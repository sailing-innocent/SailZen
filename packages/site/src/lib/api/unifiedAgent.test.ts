/**
 * @file unifiedAgent.test.ts
 * @brief Unified Agent API Tests
 * @author sailing-innocent
 * @date 2026-02-28
 * @version 1.0
 */

import {
  UnifiedAgentAPI,
  unifiedAgentAPI,
  mapAnalysisStatusToUnified,
  mapAnalysisTypeToUnified,
  createNovelAnalysisTask,
  createCodeTask,
  createWritingTask,
  createGeneralTask,
  type TaskType,
  type TaskStatus,
  type TaskSubType,
} from './unifiedAgent'

// Mock fetch globally
global.fetch = jest.fn()

describe('UnifiedAgentAPI', () => {
  let api: UnifiedAgentAPI

  beforeEach(() => {
    api = new UnifiedAgentAPI()
    jest.clearAllMocks()
  })

  // ============================================================================
  // Task Management Tests
  // ============================================================================

  describe('createTask', () => {
    it('should create a task successfully', async () => {
      const mockTask = {
        id: 1,
        task_type: 'novel_analysis',
        sub_type: 'outline_extraction',
        status: 'pending',
        progress: 0,
        priority: 5,
        actual_tokens: 0,
        actual_cost: 0,
        created_at: '2026-02-28T10:00:00Z',
      }

      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockTask,
      })

      const result = await api.createTask({
        taskType: 'novel_analysis',
        subType: 'outline_extraction',
        editionId: 1,
        priority: 5,
      })

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/tasks'),
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.any(String),
        })
      )

      expect(result.id).toBe(1)
      expect(result.taskType).toBe('novel_analysis')
      expect(result.status).toBe('pending')
    })

    it('should throw error when creation fails', async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        statusText: 'Bad Request',
      })

      await expect(
        api.createTask({
          taskType: 'novel_analysis',
          subType: 'outline_extraction',
        })
      ).rejects.toThrow('Failed to create task')
    })
  })

  describe('listTasks', () => {
    it('should list tasks with filters', async () => {
      const mockTasks = [
        {
          id: 1,
          task_type: 'novel_analysis',
          status: 'completed',
          progress: 100,
          actual_tokens: 1000,
          actual_cost: 0.01,
          created_at: '2026-02-28T10:00:00Z',
        },
      ]

      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockTasks,
      })

      const result = await api.listTasks({
        status: 'completed',
        taskType: 'novel_analysis',
        limit: 10,
      })

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('status=completed')
      )
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('task_type=novel_analysis')
      )
      expect(result).toHaveLength(1)
      expect(result[0].status).toBe('completed')
    })

    it('should return empty array when no tasks', async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      })

      const result = await api.listTasks()
      expect(result).toEqual([])
    })
  })

  describe('getTask', () => {
    it('should get task details', async () => {
      const mockTask = {
        id: 1,
        task_type: 'code',
        sub_type: 'code_review',
        status: 'running',
        progress: 50,
        current_phase: 'Analyzing code',
        actual_tokens: 500,
        actual_cost: 0.005,
        created_at: '2026-02-28T10:00:00Z',
        started_at: '2026-02-28T10:01:00Z',
      }

      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockTask,
      })

      const result = await api.getTask(1)

      expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/tasks/1'))
      expect(result.id).toBe(1)
      expect(result.currentPhase).toBe('Analyzing code')
    })
  })

  describe('getTaskProgress', () => {
    it('should get task progress', async () => {
      const mockProgress = {
        task_id: 1,
        status: 'running',
        progress: 75,
        current_phase: 'Processing',
        current_step: 3,
        total_steps: 4,
        actual_tokens: 1000,
        actual_cost: 0.01,
      }

      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockProgress,
      })

      const result = await api.getTaskProgress(1)

      expect(result.taskId).toBe(1)
      expect(result.progress).toBe(75)
      expect(result.currentStep).toBe(3)
    })
  })

  describe('cancelTask', () => {
    it('should cancel a task', async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      })

      const result = await api.cancelTask(1)

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/tasks/1/cancel'),
        expect.objectContaining({ method: 'POST' })
      )
      expect(result).toBe(true)
    })
  })

  describe('deleteTask', () => {
    it('should delete a task', async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      })

      const result = await api.deleteTask(1)

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/tasks/1'),
        expect.objectContaining({ method: 'DELETE' })
      )
      expect(result).toBe(true)
    })
  })

  // ============================================================================
  // Agent Info Tests
  // ============================================================================

  describe('listAgents', () => {
    it('should list all agents', async () => {
      const mockAgents = [
        {
          agent_type: 'novel_analysis',
          name: 'Novel Analysis Agent',
          description: 'Analyzes novels',
          supported_task_types: ['novel_analysis'],
          supported_sub_types: ['outline_extraction'],
          capabilities: ['outline', 'character'],
          default_config: {},
        },
      ]

      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAgents,
      })

      const result = await api.listAgents()

      expect(result).toHaveLength(1)
      expect(result[0].agentType).toBe('novel_analysis')
      expect(result[0].name).toBe('Novel Analysis Agent')
    })
  })

  describe('getAgentInfo', () => {
    it('should get agent info', async () => {
      const mockAgent = {
        agent_type: 'general',
        name: 'General Agent',
        description: 'General purpose agent',
        supported_task_types: ['general', 'code', 'writing'],
        supported_sub_types: ['chat', 'qa'],
        capabilities: ['conversation'],
        default_config: { temperature: 0.7 },
      }

      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAgent,
      })

      const result = await api.getAgentInfo('general')

      expect(result.agentType).toBe('general')
      expect(result.supportedTaskTypes).toContain('general')
    })
  })

  describe('estimateTaskCost', () => {
    it('should estimate task cost', async () => {
      const mockEstimate = {
        estimated_tokens: 5000,
        estimated_cost: 0.05,
        estimated_time_seconds: 120,
        confidence: 0.85,
        breakdown: {
          prompt_tokens: 3000,
          completion_tokens: 2000,
          llm_cost: 0.045,
          processing_cost: 0.005,
        },
      }

      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockEstimate,
      })

      const result = await api.estimateTaskCost('novel_analysis', {
        taskType: 'novel_analysis',
        subType: 'outline_extraction',
        editionId: 1,
      })

      expect(result.estimatedTokens).toBe(5000)
      expect(result.estimatedCost).toBe(0.05)
      expect(result.confidence).toBe(0.85)
    })
  })

  // ============================================================================
  // Scheduler Tests
  // ============================================================================

  describe('getSchedulerStatus', () => {
    it('should get scheduler status', async () => {
      const mockStatus = {
        is_running: true,
        stats: {
          total_tasks: 100,
          pending_tasks: 5,
          running_tasks: 2,
          completed_tasks: 90,
          failed_tasks: 2,
          cancelled_tasks: 1,
          total_tokens_consumed: 50000,
          total_cost: 0.5,
        },
      }

      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockStatus,
      })

      const result = await api.getSchedulerStatus()

      expect(result.isRunning).toBe(true)
      expect(result.stats.totalTasks).toBe(100)
      expect(result.stats.totalCost).toBe(0.5)
    })
  })

  describe('startScheduler', () => {
    it('should start scheduler', async () => {
      ;(fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            is_running: true,
            stats: { total_tasks: 0, pending_tasks: 0, running_tasks: 0, completed_tasks: 0, failed_tasks: 0, cancelled_tasks: 0, total_tokens_consumed: 0, total_cost: 0 },
          }),
        })

      const result = await api.startScheduler()

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/scheduler/start'),
        expect.objectContaining({ method: 'POST' })
      )
      expect(result.isRunning).toBe(true)
    })
  })

  describe('stopScheduler', () => {
    it('should stop scheduler', async () => {
      ;(fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            is_running: false,
            stats: { total_tasks: 0, pending_tasks: 0, running_tasks: 0, completed_tasks: 0, failed_tasks: 0, cancelled_tasks: 0, total_tokens_consumed: 0, total_cost: 0 },
          }),
        })

      const result = await api.stopScheduler()

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/scheduler/stop'),
        expect.objectContaining({ method: 'POST' })
      )
      expect(result.isRunning).toBe(false)
    })
  })
})

// ============================================================================
// Helper Functions Tests
// ============================================================================

describe('Helper Functions', () => {
  describe('mapAnalysisStatusToUnified', () => {
    it('should map all status correctly', () => {
      expect(mapAnalysisStatusToUnified('pending')).toBe('pending')
      expect(mapAnalysisStatusToUnified('running')).toBe('running')
      expect(mapAnalysisStatusToUnified('completed')).toBe('completed')
      expect(mapAnalysisStatusToUnified('failed')).toBe('failed')
      expect(mapAnalysisStatusToUnified('cancelled')).toBe('cancelled')
    })

    it('should return pending for unknown status', () => {
      expect(mapAnalysisStatusToUnified('unknown')).toBe('pending')
    })
  })

  describe('mapAnalysisTypeToUnified', () => {
    it('should map all analysis types correctly', () => {
      expect(mapAnalysisTypeToUnified('outline_extraction')).toBe('outline_extraction')
      expect(mapAnalysisTypeToUnified('character_detection')).toBe('character_detection')
      expect(mapAnalysisTypeToUnified('setting_extraction')).toBe('setting_extraction')
      expect(mapAnalysisTypeToUnified('relation_analysis')).toBe('relation_analysis')
      expect(mapAnalysisTypeToUnified('attribute_extraction')).toBe('attribute_extraction')
    })

    it('should return chat for unknown type', () => {
      expect(mapAnalysisTypeToUnified('unknown')).toBe('chat')
    })
  })

  describe('createNovelAnalysisTask', () => {
    it('should create novel analysis task', () => {
      const task = createNovelAnalysisTask(1, 'outline_extraction', [1, 2, 3], {
        priority: 10,
        llmProvider: 'openai',
      })

      expect(task.taskType).toBe('novel_analysis')
      expect(task.subType).toBe('outline_extraction')
      expect(task.editionId).toBe(1)
      expect(task.targetNodeIds).toEqual([1, 2, 3])
      expect(task.priority).toBe(10)
      expect(task.llmProvider).toBe('openai')
    })
  })

  describe('createCodeTask', () => {
    it('should create code task', () => {
      const task = createCodeTask(
        'code_review',
        { code: 'function test() {}' },
        { priority: 5 }
      )

      expect(task.taskType).toBe('code')
      expect(task.subType).toBe('code_review')
      expect(task.config).toEqual({ code: 'function test() {}' })
      expect(task.priority).toBe(5)
    })
  })

  describe('createWritingTask', () => {
    it('should create writing task', () => {
      const task = createWritingTask(
        'summarization',
        { text: 'Long text to summarize' },
        { llmModel: 'gpt-4' }
      )

      expect(task.taskType).toBe('writing')
      expect(task.subType).toBe('summarization')
      expect(task.config).toEqual({ text: 'Long text to summarize' })
      expect(task.llmModel).toBe('gpt-4')
    })
  })

  describe('createGeneralTask', () => {
    it('should create general task', () => {
      const task = createGeneralTask('Hello, how are you?', { priority: 3 })

      expect(task.taskType).toBe('general')
      expect(task.subType).toBe('chat')
      expect(task.config).toEqual({ content: 'Hello, how are you?' })
      expect(task.priority).toBe(3)
    })
  })
})

// ============================================================================
// Singleton Export Test
// ============================================================================

describe('unifiedAgentAPI Singleton', () => {
  it('should export singleton instance', () => {
    expect(unifiedAgentAPI).toBeInstanceOf(UnifiedAgentAPI)
  })
})

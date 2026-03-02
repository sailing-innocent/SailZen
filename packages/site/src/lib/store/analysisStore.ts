/**
 * @file analysisStore.ts
 * @brief Analysis Store - Zustand store for managing analysis state
 * @author sailing-innocent
 * @date 2025-02-28
 */

import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import type {
  AnalysisTask,
  AnalysisTaskRequest,
  AnalysisTaskStatus,
  AnalysisTaskType,
  TextRangeSelection,
  TextEvidence,
  AnalysisStats,
} from '@lib/data/analysis'
import { getDefaultRangeSelection } from '@lib/data/analysis'
import {
  api_preview_range,
  api_get_range_content,
  api_get_selection_modes,
  api_create_evidence,
  api_get_chapter_evidence,
  api_get_target_evidence,
  api_delete_evidence,
  api_get_analysis_stats,
} from '@lib/api/analysis'

// ============================================================================
// Types
// ============================================================================

export interface AnalysisState {
  // Data
  selectedEditionId: number | null
  selectedWorkId: number | null
  stats: AnalysisStats | null
  tasks: AnalysisTask[]
  evidences: TextEvidence[]
  
  // Range Selection State
  rangeSelection: TextRangeSelection | null
  rangePreview: {
    chapterCount: number
    totalChars: number
    totalWords: number
    estimatedTokens: number
    selectedChapters: Array<{
      id: number
      sort_index: number
      label?: string
      title?: string
      char_count?: number
    }>
    warnings: string[]
  } | null
  
  // UI State
  isLoading: boolean
  isPreviewLoading: boolean
  error: string | null
  activePanel: 'tasks' | 'results' | 'evidence' | 'settings'
  activeResultType: 'outline' | 'character' | 'setting' | 'relation'
  
  // Actions - Selection
  setSelectedEdition: (editionId: number | null) => void
  setSelectedWork: (workId: number | null) => void
  setRangeSelection: (selection: TextRangeSelection | null) => void
  resetRangeSelection: () => void
  
  // Actions - Data Loading
  loadStats: (editionId: number) => Promise<void>
  loadTasks: (editionId: number) => Promise<void>
  loadEvidences: (editionId: number) => Promise<void>
  
  // Actions - Range Preview
  previewRange: (selection: TextRangeSelection) => Promise<void>
  clearRangePreview: () => void
  
  // Actions - Evidence
  createEvidence: (evidence: Omit<TextEvidence, 'id' | 'created_at'>) => Promise<void>
  deleteEvidence: (evidenceId: string) => Promise<void>
  
  // Actions - UI
  setActivePanel: (panel: AnalysisState['activePanel']) => void
  setActiveResultType: (type: AnalysisState['activeResultType']) => void
  setError: (error: string | null) => void
  clearError: () => void
  
  // Actions - Reset
  reset: () => void
}

// ============================================================================
// Initial State
// ============================================================================

const initialState = {
  selectedEditionId: null,
  selectedWorkId: null,
  stats: null,
  tasks: [],
  evidences: [],
  rangeSelection: null,
  rangePreview: null,
  isLoading: false,
  isPreviewLoading: false,
  error: null,
  activePanel: 'tasks' as const,
  activeResultType: 'outline' as const,
}

// ============================================================================
// Store
// ============================================================================

export const useAnalysisStore = create<AnalysisState>()(
  devtools(
    persist(
      (set, get) => ({
        ...initialState,

        // --------------------------------------------------------------------------
        // Selection Actions
        // --------------------------------------------------------------------------

        setSelectedEdition: (editionId) => {
          set({ 
            selectedEditionId: editionId,
            // Reset range selection when edition changes
            rangeSelection: editionId ? getDefaultRangeSelection(editionId) : null,
            rangePreview: null,
          })
          
          if (editionId) {
            get().loadStats(editionId)
            get().loadTasks(editionId)
          }
        },

        setSelectedWork: (workId) => {
          set({ 
            selectedWorkId: workId,
            selectedEditionId: null,
            rangeSelection: null,
            rangePreview: null,
          })
        },

        setRangeSelection: (selection) => {
          set({ rangeSelection: selection })
          
          if (selection) {
            get().previewRange(selection)
          }
        },

        resetRangeSelection: () => {
          const { selectedEditionId } = get()
          set({
            rangeSelection: selectedEditionId ? getDefaultRangeSelection(selectedEditionId) : null,
            rangePreview: null,
          })
        },

        // --------------------------------------------------------------------------
        // Data Loading Actions
        // --------------------------------------------------------------------------

        loadStats: async (editionId) => {
          set({ isLoading: true, error: null })
          try {
            const stats = await api_get_analysis_stats(editionId)
            set({ stats, isLoading: false })
          } catch (error) {
            set({
              error: error instanceof Error ? error.message : 'Failed to load stats',
              isLoading: false,
            })
          }
        },

        loadTasks: async (editionId) => {
          // TODO: Implement when API is available
          set({ tasks: [] })
        },

        loadEvidences: async (editionId) => {
          // TODO: Implement when API is available
          set({ evidences: [] })
        },

        // --------------------------------------------------------------------------
        // Range Preview Actions
        // --------------------------------------------------------------------------

        previewRange: async (selection) => {
          set({ isPreviewLoading: true, error: null })
          try {
            const preview = await api_preview_range(selection)
            console.log('[Debug Store] previewRange result:', preview)
            console.log('[Debug Store] selected_chapters:', preview.selected_chapters)
            set({
              rangePreview: {
                chapterCount: preview.chapter_count,
                totalChars: preview.total_chars,
                totalWords: preview.total_words,
                estimatedTokens: preview.estimated_tokens,
                selectedChapters: preview.selected_chapters,
                warnings: preview.warnings,
              },
              isPreviewLoading: false,
            })
          } catch (error) {
            console.error('[Debug Store] previewRange error:', error)
            set({
              error: error instanceof Error ? error.message : 'Failed to preview range',
              isPreviewLoading: false,
            })
          }
        },

        clearRangePreview: () => {
          set({ rangePreview: null })
        },

        // --------------------------------------------------------------------------
        // Evidence Actions
        // --------------------------------------------------------------------------

        createEvidence: async (evidence) => {
          set({ isLoading: true, error: null })
          try {
            // TODO: Implement when API is available
            set({ isLoading: false })
          } catch (error) {
            set({
              error: error instanceof Error ? error.message : 'Failed to create evidence',
              isLoading: false,
            })
          }
        },

        deleteEvidence: async (evidenceId) => {
          set({ isLoading: true, error: null })
          try {
            await api_delete_evidence(evidenceId)
            set((state) => ({
              evidences: state.evidences.filter((e) => e.id !== evidenceId),
              isLoading: false,
            }))
          } catch (error) {
            set({
              error: error instanceof Error ? error.message : 'Failed to delete evidence',
              isLoading: false,
            })
          }
        },

        // --------------------------------------------------------------------------
        // UI Actions
        // --------------------------------------------------------------------------

        setActivePanel: (panel) => {
          set({ activePanel: panel })
        },

        setActiveResultType: (type) => {
          set({ activeResultType: type })
        },

        setError: (error) => {
          set({ error })
        },

        clearError: () => {
          set({ error: null })
        },

        // --------------------------------------------------------------------------
        // Reset Actions
        // --------------------------------------------------------------------------

        reset: () => {
          set(initialState)
        },
      }),
      {
        name: 'analysis-store',
        partialize: (state) => ({
          selectedWorkId: state.selectedWorkId,
          selectedEditionId: state.selectedEditionId,
          activePanel: state.activePanel,
          activeResultType: state.activeResultType,
        }),
      }
    ),
    { name: 'AnalysisStore' }
  )
)

export default useAnalysisStore

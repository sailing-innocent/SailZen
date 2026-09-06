/**
 * @file history.ts
 * @brief The History Events Data Types
 * @author sailing-innocent
 * @date 2025-10-27
 */

export interface HistoryEventCreateProps {
  title: string
  description: string
  rar_tags?: string[]
  tags?: string[]
  start_time?: string
  end_time?: string
  parent_event?: number
  related_events?: number[]
  details?: Record<string, any>
}

export interface HistoryEventData extends HistoryEventCreateProps {
  id: number
  receive_time: string
}

export interface HistoryEventUpdateProps {
  title?: string
  description?: string
  rar_tags?: string[]
  tags?: string[]
  start_time?: string
  end_time?: string
  parent_event?: number
  related_events?: number[]
  details?: Record<string, any>
}


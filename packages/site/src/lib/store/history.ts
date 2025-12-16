/**
 * @file history.ts
 * @brief Store for History Events
 * @author sailing-innocent
 * @date 2025-10-27
 */

import { create, type StoreApi, type UseBoundStore } from 'zustand'
import {
  type HistoryEventCreateProps,
  type HistoryEventData,
  type HistoryEventUpdateProps,
} from '@lib/data/history'

import {
  api_get_history_events,
  api_get_history_event,
  api_get_history_event_children,
  api_get_history_event_related,
  api_search_history_events,
  api_create_history_event,
  api_update_history_event,
  api_delete_history_event,
} from '@lib/api/history'

export interface HistoryEventsState {
  events: HistoryEventData[]
  isLoading: boolean
  fetchEvents: (skip?: number, limit?: number, parentId?: number, tags?: string) => Promise<void>
  fetchEvent: (id: number) => Promise<HistoryEventData>
  fetchEventChildren: (id: number) => Promise<HistoryEventData[]>
  fetchEventRelated: (id: number) => Promise<HistoryEventData[]>
  searchEvents: (keyword: string, skip?: number, limit?: number) => Promise<HistoryEventData[]>
  createEvent: (event: HistoryEventCreateProps) => Promise<HistoryEventData>
  updateEvent: (id: number, event: HistoryEventUpdateProps) => Promise<HistoryEventData>
  deleteEvent: (id: number) => Promise<boolean>
}

export const useHistoryEventsStore: UseBoundStore<StoreApi<HistoryEventsState>> = create<HistoryEventsState>((set) => ({
  events: [],
  isLoading: false,
  fetchEvents: async (skip = 0, limit = 100, parentId?: number, tags?: string): Promise<void> => {
    set({ isLoading: true })
    try {
      const events = await api_get_history_events(skip, limit, parentId, tags)
      set({ events: events, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },
  fetchEvent: async (id: number): Promise<HistoryEventData> => {
    const event = await api_get_history_event(id)
    set((state: HistoryEventsState): HistoryEventsState => {
      const index = state.events.findIndex((e: HistoryEventData) => e.id === event.id)
      const nextState: HistoryEventsState = {
        ...state,
        events: [...state.events],
      }
      if (index !== -1) {
        nextState.events[index] = event
      } else {
        nextState.events.push(event)
      }
      return nextState
    })
    return event
  },
  fetchEventChildren: async (id: number): Promise<HistoryEventData[]> => {
    const children = await api_get_history_event_children(id)
    return children
  },
  fetchEventRelated: async (id: number): Promise<HistoryEventData[]> => {
    const related = await api_get_history_event_related(id)
    return related
  },
  searchEvents: async (keyword: string, skip = 0, limit = 100): Promise<HistoryEventData[]> => {
    set({ isLoading: true })
    try {
      const events = await api_search_history_events(keyword, skip, limit)
      set({ events: events, isLoading: false })
      return events
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },
  createEvent: async (event: HistoryEventCreateProps): Promise<HistoryEventData> => {
    const newEvent = await api_create_history_event(event)
    set((state: HistoryEventsState): HistoryEventsState => ({
      ...state,
      events: [newEvent, ...state.events],
    }))
    return newEvent
  },
  updateEvent: async (id: number, event: HistoryEventUpdateProps): Promise<HistoryEventData> => {
    const updatedEvent = await api_update_history_event(id, event)
    set((state: HistoryEventsState): HistoryEventsState => {
      const index = state.events.findIndex((e: HistoryEventData) => e.id === updatedEvent.id)
      const nextState: HistoryEventsState = {
        ...state,
        events: [...state.events],
      }
      if (index !== -1) {
        nextState.events[index] = updatedEvent
        return nextState
      }
      return state
    })
    return updatedEvent
  },
  deleteEvent: async (id: number): Promise<boolean> => {
    const response = await api_delete_history_event(id)
    set((state: HistoryEventsState): HistoryEventsState => ({
      ...state,
      events: state.events.filter((e: HistoryEventData) => e.id !== id),
    }))
    return response.status === 'success'
  },
}))


/**
 * @file history.ts
 * @brief The History Events API
 * @author sailing-innocent
 * @date 2025-10-27
 */

import {
  type HistoryEventCreateProps,
  type HistoryEventData,
  type HistoryEventUpdateProps,
} from '@lib/data/history'

import { SERVER_URL, API_BASE } from './config'
const HISTORY_API_BASE = API_BASE + '/history/event'

// Get events list
const api_get_history_events = async (
  skip: number = 0,
  limit: number = 10,
  parentId?: number,
  tags?: string
): Promise<HistoryEventData[]> => {
  let url = `${SERVER_URL}/${HISTORY_API_BASE}?skip=${skip}&limit=${limit}`
  if (parentId !== undefined) {
    url += `&parent_id=${parentId}`
  }
  if (tags) {
    url += `&tags=${tags}`
  }
  const response = await fetch(url)
  return response.json()
}

// Get single event
const api_get_history_event = async (id: number): Promise<HistoryEventData> => {
  const response = await fetch(`${SERVER_URL}/${HISTORY_API_BASE}/${id}`)
  return response.json()
}

// Get children events
const api_get_history_event_children = async (id: number): Promise<HistoryEventData[]> => {
  const response = await fetch(`${SERVER_URL}/${HISTORY_API_BASE}/${id}/children`)
  return response.json()
}

// Get related events
const api_get_history_event_related = async (id: number): Promise<HistoryEventData[]> => {
  const response = await fetch(`${SERVER_URL}/${HISTORY_API_BASE}/${id}/related`)
  return response.json()
}

// Search events
const api_search_history_events = async (
  keyword: string,
  skip: number = 0,
  limit: number = 10
): Promise<HistoryEventData[]> => {
  const response = await fetch(
    `${SERVER_URL}/${HISTORY_API_BASE}/search?keyword=${encodeURIComponent(keyword)}&skip=${skip}&limit=${limit}`
  )
  return response.json()
}

// Create event
const api_create_history_event = async (event: HistoryEventCreateProps): Promise<HistoryEventData> => {
  const response = await fetch(`${SERVER_URL}/${HISTORY_API_BASE}/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(event),
  })
  return response.json()
}

// Update event
const api_update_history_event = async (
  id: number,
  event: HistoryEventUpdateProps
): Promise<HistoryEventData> => {
  const response = await fetch(`${SERVER_URL}/${HISTORY_API_BASE}/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(event),
  })
  return response.json()
}

// Delete event
const api_delete_history_event = async (id: number): Promise<{ id: number; status: string; message?: string }> => {
  const response = await fetch(`${SERVER_URL}/${HISTORY_API_BASE}/${id}`, {
    method: 'DELETE',
  })
  return response.json()
}

export {
  api_get_history_events,
  api_get_history_event,
  api_get_history_event_children,
  api_get_history_event_related,
  api_search_history_events,
  api_create_history_event,
  api_update_history_event,
  api_delete_history_event,
}


/**
 * @file analysis.ts
 * @brief Novel Analysis API
 * @author sailing-innocent
 * @date 2025-02-01
 */

import type {
  Character,
  CharacterAlias,
  CharacterAttribute,
  CharacterArc,
  CharacterRelation,
  CharacterProfile,
  Setting,
  SettingAttribute,
  SettingRelation,
  CharacterSettingLink,
  SettingDetail,
  Outline,
  OutlineNode,
  OutlineEvent,
  OutlineTree,
  TextEvidence,
  AnalysisTask,
  AnalysisResult,
  RelationGraphData,
  CreateCharacterRequest,
  UpdateCharacterRequest,
  CreateSettingRequest,
  CreateOutlineRequest,
  AddOutlineNodeRequest,
  CreateRelationRequest,
  CreateTaskRequest,
  AnalysisStats,
  ChapterAnnotation,
} from '@lib/data/analysis'
import { SERVER_URL, API_BASE } from './config'

const ANALYSIS_API_BASE = `${API_BASE}/analysis`

// ============================================================================
// Character API
// ============================================================================

export async function api_create_character(data: CreateCharacterRequest): Promise<Character> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to create character: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_character(character_id: number): Promise<Character | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/${character_id}`)
  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`Failed to get character: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_characters_by_edition(
  edition_id: number,
  role_type?: string,
  skip = 0,
  limit = 100
): Promise<Character[]> {
  let url = `${SERVER_URL}/${ANALYSIS_API_BASE}/character/edition/${edition_id}?skip=${skip}&limit=${limit}`
  if (role_type) {
    url += `&role_type=${encodeURIComponent(role_type)}`
  }
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to get characters: ${response.statusText}`)
  }
  return response.json()
}

export async function api_update_character(
  character_id: number,
  data: UpdateCharacterRequest
): Promise<Character | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/${character_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`Failed to update character: ${response.statusText}`)
  }
  return response.json()
}

export async function api_delete_character(character_id: number): Promise<boolean> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/${character_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete character: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

export async function api_search_characters(
  edition_id: number,
  keyword: string,
  skip = 0,
  limit = 50
): Promise<Character[]> {
  const url = `${SERVER_URL}/${ANALYSIS_API_BASE}/character/search?edition_id=${edition_id}&keyword=${encodeURIComponent(keyword)}&skip=${skip}&limit=${limit}`
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to search characters: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_character_profile(character_id: number): Promise<CharacterProfile | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/${character_id}/profile`)
  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`Failed to get character profile: ${response.statusText}`)
  }
  return response.json()
}

// Character Alias
export async function api_add_character_alias(
  character_id: number,
  alias: string,
  alias_type = 'nickname',
  usage_context?: string,
  is_preferred = false
): Promise<CharacterAlias | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/${character_id}/alias`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alias, alias_type, usage_context, is_preferred }),
  })
  if (!response.ok) {
    throw new Error(`Failed to add alias: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_character_aliases(character_id: number): Promise<CharacterAlias[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/${character_id}/aliases`)
  if (!response.ok) {
    throw new Error(`Failed to get aliases: ${response.statusText}`)
  }
  return response.json()
}

export async function api_remove_character_alias(alias_id: number): Promise<boolean> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/alias/${alias_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to remove alias: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

// Character Attribute
export async function api_add_character_attribute(
  character_id: number,
  category: string,
  attr_key: string,
  attr_value: unknown,
  confidence?: number,
  source_node_id?: number
): Promise<CharacterAttribute | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/${character_id}/attribute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ category, attr_key, attr_value, confidence, source_node_id }),
  })
  if (!response.ok) {
    throw new Error(`Failed to add attribute: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_character_attributes(
  character_id: number,
  category?: string
): Promise<CharacterAttribute[]> {
  let url = `${SERVER_URL}/${ANALYSIS_API_BASE}/character/${character_id}/attributes`
  if (category) {
    url += `?category=${encodeURIComponent(category)}`
  }
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to get attributes: ${response.statusText}`)
  }
  return response.json()
}

export async function api_delete_character_attribute(attr_id: number): Promise<boolean> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/attribute/${attr_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete attribute: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

// Character Arc
export async function api_add_character_arc(
  character_id: number,
  arc_type: string,
  title: string,
  description?: string,
  start_node_id?: number,
  end_node_id?: number
): Promise<CharacterArc | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/${character_id}/arc`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ arc_type, title, description, start_node_id, end_node_id }),
  })
  if (!response.ok) {
    throw new Error(`Failed to add arc: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_character_arcs(character_id: number): Promise<CharacterArc[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/${character_id}/arcs`)
  if (!response.ok) {
    throw new Error(`Failed to get arcs: ${response.statusText}`)
  }
  return response.json()
}

export async function api_delete_character_arc(arc_id: number): Promise<boolean> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character/arc/${arc_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete arc: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

// ============================================================================
// Character Relation API
// ============================================================================

export async function api_create_relation(data: CreateRelationRequest): Promise<CharacterRelation> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/relation/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to create relation: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_edition_relations(edition_id: number): Promise<CharacterRelation[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/relation/edition/${edition_id}`)
  if (!response.ok) {
    throw new Error(`Failed to get relations: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_character_relations(character_id: number): Promise<CharacterRelation[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/relation/character/${character_id}`)
  if (!response.ok) {
    throw new Error(`Failed to get character relations: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_relation_graph(edition_id: number): Promise<RelationGraphData> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/relation/graph/${edition_id}`)
  if (!response.ok) {
    throw new Error(`Failed to get relation graph: ${response.statusText}`)
  }
  return response.json()
}

export async function api_delete_relation(relation_id: number): Promise<boolean> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/relation/${relation_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete relation: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

// ============================================================================
// Setting API
// ============================================================================

export async function api_create_setting(data: CreateSettingRequest): Promise<Setting> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to create setting: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_setting(setting_id: number): Promise<Setting | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/${setting_id}`)
  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`Failed to get setting: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_settings_by_edition(
  edition_id: number,
  setting_type?: string,
  category?: string,
  skip = 0,
  limit = 100
): Promise<Setting[]> {
  let url = `${SERVER_URL}/${ANALYSIS_API_BASE}/setting/edition/${edition_id}?skip=${skip}&limit=${limit}`
  if (setting_type) {
    url += `&setting_type=${encodeURIComponent(setting_type)}`
  }
  if (category) {
    url += `&category=${encodeURIComponent(category)}`
  }
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to get settings: ${response.statusText}`)
  }
  return response.json()
}

export async function api_delete_setting(setting_id: number): Promise<boolean> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/${setting_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete setting: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

export async function api_update_setting(
  setting_id: number,
  data: Partial<{
    setting_type: string
    canonical_name: string
    category: string | null
    description: string
    first_appearance_node_id: number | null
    importance: string
    status: string
    meta_data: Record<string, unknown>
  }>
): Promise<Setting | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/${setting_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`Failed to update setting: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_setting_detail(setting_id: number): Promise<SettingDetail | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/${setting_id}/detail`)
  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`Failed to get setting detail: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_setting_types(edition_id: number): Promise<{ type: string; count: number }[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/types/${edition_id}`)
  if (!response.ok) {
    throw new Error(`Failed to get setting types: ${response.statusText}`)
  }
  return response.json()
}

// Setting Attribute
export async function api_add_setting_attribute(
  setting_id: number,
  attr_key: string,
  attr_value: unknown,
  source_node_id?: number
): Promise<SettingAttribute | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/${setting_id}/attribute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ attr_key, attr_value, source_node_id }),
  })
  if (!response.ok) {
    throw new Error(`Failed to add setting attribute: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_setting_attributes(setting_id: number): Promise<SettingAttribute[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/${setting_id}/attributes`)
  if (!response.ok) {
    throw new Error(`Failed to get setting attributes: ${response.statusText}`)
  }
  return response.json()
}

export async function api_delete_setting_attribute(attr_id: number): Promise<boolean> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting/attribute/${attr_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete setting attribute: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

// Setting Relation
export async function api_create_setting_relation(
  edition_id: number,
  source_setting_id: number,
  target_setting_id: number,
  relation_type: string,
  description?: string
): Promise<SettingRelation> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting-relation/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ edition_id, source_setting_id, target_setting_id, relation_type, description }),
  })
  if (!response.ok) {
    throw new Error(`Failed to create setting relation: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_setting_relations(setting_id: number): Promise<SettingRelation[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/setting-relation/${setting_id}`)
  if (!response.ok) {
    throw new Error(`Failed to get setting relations: ${response.statusText}`)
  }
  return response.json()
}

// Character-Setting Link
export async function api_create_character_setting_link(
  character_id: number,
  setting_id: number,
  link_type: string,
  description?: string
): Promise<CharacterSettingLink | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character-setting-link/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ character_id, setting_id, link_type, description }),
  })
  if (!response.ok) {
    throw new Error(`Failed to create link: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_character_settings(character_id: number): Promise<Setting[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character-setting-link/character/${character_id}`)
  if (!response.ok) {
    throw new Error(`Failed to get character settings: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_setting_characters(
  setting_id: number
): Promise<{ character_id: number; canonical_name: string; role_type: string; link_type: string; description: string | null }[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/character-setting-link/setting/${setting_id}`)
  if (!response.ok) {
    throw new Error(`Failed to get setting characters: ${response.statusText}`)
  }
  return response.json()
}

// ============================================================================
// Outline API
// ============================================================================

export async function api_create_outline(data: CreateOutlineRequest): Promise<Outline> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to create outline: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_outline(outline_id: number): Promise<Outline | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/${outline_id}`)
  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`Failed to get outline: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_outlines_by_edition(edition_id: number): Promise<Outline[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/edition/${edition_id}`)
  if (!response.ok) {
    throw new Error(`Failed to get outlines: ${response.statusText}`)
  }
  return response.json()
}

export async function api_delete_outline(outline_id: number): Promise<boolean> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/${outline_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete outline: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

export async function api_get_outline_tree(outline_id: number): Promise<OutlineTree | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/${outline_id}/tree`)
  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`Failed to get outline tree: ${response.statusText}`)
  }
  return response.json()
}

// Outline Node
export async function api_add_outline_node(
  outline_id: number,
  data: AddOutlineNodeRequest
): Promise<OutlineNode | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/${outline_id}/node`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to add outline node: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_outline_node(node_id: number): Promise<OutlineNode | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/node/${node_id}`)
  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`Failed to get outline node: ${response.statusText}`)
  }
  return response.json()
}

export async function api_update_outline_node(
  node_id: number,
  data: Partial<{
    title: string
    summary: string
    significance: string
    chapter_start_id: number
    chapter_end_id: number
    status: string
  }>
): Promise<OutlineNode | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/node/${node_id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`Failed to update outline node: ${response.statusText}`)
  }
  return response.json()
}

export async function api_delete_outline_node(node_id: number): Promise<boolean> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/node/${node_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete outline node: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

// Outline Event
export async function api_add_outline_event(
  node_id: number,
  event_type: string,
  title: string,
  description?: string,
  chronology_order?: number,
  narrative_order?: number,
  importance = 'normal'
): Promise<OutlineEvent | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/node/${node_id}/event`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event_type, title, description, chronology_order, narrative_order, importance }),
  })
  if (!response.ok) {
    throw new Error(`Failed to add event: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_node_events(node_id: number): Promise<OutlineEvent[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/node/${node_id}/events`)
  if (!response.ok) {
    throw new Error(`Failed to get events: ${response.statusText}`)
  }
  return response.json()
}

export async function api_delete_outline_event(event_id: number): Promise<boolean> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/outline/event/${event_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete event: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

// ============================================================================
// Evidence API
// ============================================================================

export async function api_add_evidence(
  edition_id: number,
  node_id: number,
  target_type: string,
  target_id: number,
  start_char?: number,
  end_char?: number,
  text_snippet?: string,
  evidence_type = 'explicit',
  confidence?: number
): Promise<TextEvidence> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/evidence/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      edition_id,
      node_id,
      target_type,
      target_id,
      start_char,
      end_char,
      text_snippet,
      evidence_type,
      confidence,
    }),
  })
  if (!response.ok) {
    throw new Error(`Failed to add evidence: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_evidence_for_target(target_type: string, target_id: number): Promise<TextEvidence[]> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/evidence/target/${target_type}/${target_id}`)
  if (!response.ok) {
    throw new Error(`Failed to get evidence: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_chapter_annotations(node_id: number): Promise<Record<string, ChapterAnnotation[]>> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/evidence/chapter/${node_id}`)
  if (!response.ok) {
    throw new Error(`Failed to get annotations: ${response.statusText}`)
  }
  return response.json()
}

export async function api_delete_evidence(evidence_id: number): Promise<boolean> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/evidence/${evidence_id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete evidence: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

// ============================================================================
// Analysis Task API
// ============================================================================

export async function api_create_analysis_task(data: CreateTaskRequest): Promise<AnalysisTask> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to create task: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_analysis_task(task_id: number): Promise<AnalysisTask | null> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task/${task_id}`)
  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`Failed to get task: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_tasks_by_edition(
  edition_id: number,
  status?: string,
  task_type?: string,
  skip = 0,
  limit = 50
): Promise<AnalysisTask[]> {
  let url = `${SERVER_URL}/${ANALYSIS_API_BASE}/task/edition/${edition_id}?skip=${skip}&limit=${limit}`
  if (status) {
    url += `&status=${encodeURIComponent(status)}`
  }
  if (task_type) {
    url += `&task_type=${encodeURIComponent(task_type)}`
  }
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to get tasks: ${response.statusText}`)
  }
  return response.json()
}

export async function api_cancel_task(task_id: number): Promise<boolean> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task/${task_id}/cancel`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`Failed to cancel task: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

export async function api_get_task_results(
  task_id: number,
  review_status?: string
): Promise<AnalysisResult[]> {
  let url = `${SERVER_URL}/${ANALYSIS_API_BASE}/task/${task_id}/results`
  if (review_status) {
    url += `?review_status=${encodeURIComponent(review_status)}`
  }
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to get results: ${response.statusText}`)
  }
  return response.json()
}

export async function api_approve_result(result_id: number, reviewer = 'user'): Promise<boolean> {
  const response = await fetch(
    `${SERVER_URL}/${ANALYSIS_API_BASE}/task/result/${result_id}/approve?reviewer=${encodeURIComponent(reviewer)}`,
    { method: 'POST' }
  )
  if (!response.ok) {
    throw new Error(`Failed to approve result: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

export async function api_reject_result(result_id: number, reviewer = 'user', notes?: string): Promise<boolean> {
  let url = `${SERVER_URL}/${ANALYSIS_API_BASE}/task/result/${result_id}/reject?reviewer=${encodeURIComponent(reviewer)}`
  if (notes) {
    url += `&notes=${encodeURIComponent(notes)}`
  }
  const response = await fetch(url, { method: 'POST' })
  if (!response.ok) {
    throw new Error(`Failed to reject result: ${response.statusText}`)
  }
  const result = await response.json()
  return result.success
}

export async function api_modify_result(
  result_id: number,
  result_data: Record<string, unknown>,
  reviewer = 'user'
): Promise<AnalysisResult | null> {
  const response = await fetch(
    `${SERVER_URL}/${ANALYSIS_API_BASE}/task/result/${result_id}/modify?reviewer=${encodeURIComponent(reviewer)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ result_data }),
    }
  )
  if (!response.ok) {
    throw new Error(`Failed to modify result: ${response.statusText}`)
  }
  return response.json()
}

export async function api_apply_all_results(task_id: number): Promise<{ applied: number; failed: number; total: number }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task/${task_id}/apply-all`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`Failed to apply results: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_analysis_stats(edition_id: number): Promise<AnalysisStats> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task/stats/${edition_id}`)
  if (!response.ok) {
    throw new Error(`Failed to get stats: ${response.statusText}`)
  }
  return response.json()
}

// ============================================================================
// Task Execution API - 任务执行相关
// ============================================================================

export interface TaskExecutionPlan {
  task_id: number
  mode: string
  chunks: {
    index: number
    node_ids: number[]
    chapter_range: string
    token_estimate: number
  }[]
  total_estimated_tokens: number
  estimated_cost_usd: number
  prompt_template_id: string
}

export interface TaskProgress {
  task_id: number
  status: string
  current_step: string
  total_chunks: number
  completed_chunks: number
  current_chunk_info?: string
  started_at?: string
  estimated_remaining_seconds?: number
  error?: string
}

export interface TaskExecuteRequest {
  mode: 'llm_direct' | 'prompt_only'
  llm_provider?: string
  llm_model?: string
  llm_api_key?: string
  temperature?: number
}

export interface LLMProvider {
  id: string
  name: string
  description?: string
  requires_api_key: boolean
  models: {
    id: string
    name: string
    context_length: number
  }[]
}

export async function api_create_task_plan(
  task_id: number,
  mode: 'llm_direct' | 'prompt_only'
): Promise<{ success: boolean; plan?: TaskExecutionPlan; error?: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task-execution/${task_id}/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  })
  if (!response.ok) {
    throw new Error(`Failed to create plan: ${response.statusText}`)
  }
  return response.json()
}

export async function api_execute_task(
  task_id: number,
  data: TaskExecuteRequest
): Promise<{ success: boolean; result?: { task_id: number; success: boolean; results_count: number; error_message?: string }; error?: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task-execution/${task_id}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to execute task: ${response.statusText}`)
  }
  return response.json()
}

export async function api_execute_task_async(
  task_id: number,
  data: TaskExecuteRequest
): Promise<{ success: boolean; message?: string; task_id?: number; error?: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task-execution/${task_id}/execute-async`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to start task: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_task_progress(
  task_id: number
): Promise<{ success: boolean; is_running?: boolean; completed?: boolean; progress?: TaskProgress; result?: unknown; error?: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task-execution/${task_id}/progress`)
  if (!response.ok) {
    throw new Error(`Failed to get progress: ${response.statusText}`)
  }
  return response.json()
}

export async function api_cancel_running_task(task_id: number): Promise<{ success: boolean; message?: string; error?: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task-execution/${task_id}/cancel`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`Failed to cancel task: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_llm_providers(): Promise<{ success: boolean; providers: LLMProvider[] }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/llm/providers`)
  if (!response.ok) {
    throw new Error(`Failed to get providers: ${response.statusText}`)
  }
  return response.json()
}

export async function api_get_task_prompts(
  task_id: number,
  format: 'json' | 'plain' | 'openai' | 'anthropic' | 'markdown' = 'json'
): Promise<{
  success: boolean
  task_id: number
  format: string
  prompts: {
    result_id: number
    chunk_index: number
    chunk_range: string
    awaiting_result: boolean
    content: unknown
  }[]
}> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/export/task/${task_id}/prompts?format=${format}`)
  if (!response.ok) {
    throw new Error(`Failed to get prompts: ${response.statusText}`)
  }
  return response.json()
}

export async function api_import_external_result(
  task_id: number,
  chunk_index: number,
  result_text: string
): Promise<{ success: boolean; result?: { id: number; result_type: string; review_status: string }; error?: string }> {
  const response = await fetch(`${SERVER_URL}/${ANALYSIS_API_BASE}/task-execution/${task_id}/import-result`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chunk_index, result_text }),
  })
  if (!response.ok) {
    throw new Error(`Failed to import result: ${response.statusText}`)
  }
  return response.json()
}

// SSE 连接用于任务状态实时更新
export function createTaskStatusEventSource(task_id: number): EventSource {
  return new EventSource(`${SERVER_URL}/${ANALYSIS_API_BASE}/task-execution/${task_id}/status-stream`)
}

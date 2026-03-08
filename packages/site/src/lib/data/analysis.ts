/**
 * @file analysis.ts
 * @brief Analysis Data Types
 * @author sailing-innocent
 * @date 2025-02-28
 */

// ============================================================================
// Text Range Selection Types
// ============================================================================

export type RangeSelectionMode =
  | 'single_chapter'
  | 'chapter_range'
  | 'multi_chapter'
  | 'full_edition'
  | 'current_to_end'
  | 'custom_range'

export interface RangeSelectionModeInfo {
  value: RangeSelectionMode
  label: string
  description: string
  params: string[]
}

export interface TextRangeSelection {
  edition_id: number
  mode: RangeSelectionMode
  chapter_index?: number
  start_index?: number
  end_index?: number
  chapter_indices?: number[]
  node_ids?: number[]
  meta_data?: Record<string, unknown>
}

export interface SelectedChapterInfo {
  id: number
  sort_index: number
  label?: string
  title?: string
  char_count?: number
  word_count?: number
}

export interface TextRangePreview {
  edition_id: number
  mode: RangeSelectionMode
  chapter_count: number
  total_chars: number
  total_words: number
  estimated_tokens: number
  selected_chapters: SelectedChapterInfo[]
  preview_text?: string
  warnings: string[]
  meta_data?: Record<string, unknown>
}

export interface ChapterContent {
  id: number
  sort_index: number
  label?: string
  title?: string
  char_count?: number
  word_count?: number
  content: string
}

export interface TextRangeContent {
  edition_id: number
  mode: RangeSelectionMode
  full_text: string
  chapters: ChapterContent[]
  chapter_count: number
  total_chars: number
  total_words: number
  estimated_tokens: number
  meta_data?: Record<string, unknown>
}

// ============================================================================
// Evidence Types
// ============================================================================

export interface TextEvidence {
  id: string
  edition_id: number
  node_id: number
  start_offset: number
  end_offset: number
  selected_text: string
  evidence_type: string
  target_type?: string
  target_id?: string
  content: string
  context?: string
  created_at: string
  updated_at?: string
  meta_data?: Record<string, unknown>
}

export interface EvidenceCreateRequest {
  edition_id: number
  node_id: number
  start_offset: number
  end_offset: number
  selected_text: string
  evidence_type: string
  content: string
  target_type?: string
  target_id?: string
  context?: string
  meta_data?: Record<string, unknown>
}

export interface EvidenceUpdateRequest {
  content?: string
  evidence_type?: string
  target_type?: string
  target_id?: string
  context?: string
  meta_data?: Record<string, unknown>
}

// ============================================================================
// Outline Extraction Types
// ============================================================================

export type OutlineGranularity = 'act' | 'arc' | 'scene' | 'beat'
export type OutlineExtractionType = 'main' | 'subplot' | 'character_arc' | 'theme'

export interface OutlineExtractionConfig {
  granularity: OutlineGranularity
  outline_type: OutlineExtractionType
  extract_turning_points: boolean
  extract_characters: boolean
  max_nodes: number
  llm_provider?: string
  llm_model?: string
  temperature: number
  prompt_template_id: string
}

export interface OutlineExtractionRequest {
  edition_id: number
  range_selection: TextRangeSelection
  config: OutlineExtractionConfig
  work_title?: string
  known_characters?: string[]
}

export interface ExtractedOutlineNode {
  id: string
  node_type: OutlineNodeType
  title: string
  summary: string
  significance: 'critical' | 'major' | 'normal' | 'minor'
  sort_index: number
  parent_id?: string
  characters?: string[]
  evidence?: {
    text: string
    start_offset: number
    end_offset: number
  }
  review_status?: 'pending' | 'approved' | 'rejected'
}

export interface OutlineExtractionResult {
  nodes: ExtractedOutlineNode[]
  metadata: Record<string, unknown>
  turning_points?: Array<{
    node_id: string
    turning_point_type: string
    description: string
  }>
}

export interface OutlineExtractionResponse {
  success: boolean
  task_id?: string
  result?: OutlineExtractionResult
  message: string
  error?: string
}

export interface OutlineExtractionTask {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  message: string
  created_at: string
}

export interface RateLimitInfo {
  limit_type: string
  current_usage: number
  limit: number
  usage_percent: number
  reset_time?: string
  retry_after?: number
  detected_at: string
}

export interface ExtractionErrorInfo {
  type: string
  message: string
  is_retryable: boolean
  retry_count: number
  rate_limit_info?: RateLimitInfo
  suggestion: string
}

export interface OutlineExtractionProgress {
  task_id: string
  current_step: string
  progress_percent: number
  message: string
  chunk_index?: number
  total_chunks?: number
  batch_index?: number
  total_batches?: number
  // 新增：重试和错误信息
  is_retrying?: boolean
  retry_attempt?: number
  retry_delay?: number
  rate_limit_info?: RateLimitInfo
  error_info?: ExtractionErrorInfo
}

export interface OutlineExtractionDetailedStatus {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused'
  phase: string
  progress_percent: number
  current_step: string
  message: string
  // 批次信息
  total_batches: number
  completed_batches: number[]
  failed_batches: number[]
  current_batch: number
  // 结果统计
  total_nodes: number
  total_turning_points: number
  // 错误信息
  last_error?: string
  last_error_type?: string
  retry_count: number
  // 恢复信息
  is_recovered: boolean
  recovered_from?: string
  // 时间戳
  created_at?: string
  started_at?: string
  completed_at?: string
  updated_at?: string
}

export interface ResumeTaskResponse {
  success: boolean
  task_id: string
  message: string
  resumed_from_batch: number
  total_batches: number
}

/** 大纲提取任务摘要（用于任务列表） */
export interface OutlineExtractionTaskSummary {
  task_id: string
  edition_id: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  phase: string
  progress: number
  current_step: string
  config?: OutlineExtractionConfig
  error?: string
  is_recovered?: boolean
  created_at?: string
  started_at?: string
  completed_at?: string
  // 检查点信息（如果有）
  checkpoint_progress?: number
  total_nodes?: number
  total_turning_points?: number
  total_batches?: number
  completed_batches?: number
}

/** 恢复任务查看的响应 */
export interface RecoverTaskViewResponse {
  success: boolean
  task_id?: string
  result?: OutlineExtractionResult
  message: string
  error?: string
}

export interface OutlinePreviewResponse {
  preview_nodes: Array<{
    id: string
    node_type: string
    title: string
    summary: string
    significance: string
    parent_id?: string
  }>
  total_nodes: number
  estimated_tokens: number
  sample_evidence: string[]
}

// ============================================================================
// Analysis Task Types
// ============================================================================

export type AnalysisTaskType =
  | 'outline_extraction'
  | 'character_detection'
  | 'setting_extraction'
  | 'relation_analysis'
  | 'consistency_check'
  | 'custom_analysis'

export type AnalysisTaskStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface AnalysisTask {
  id: string
  edition_id: number
  task_type: AnalysisTaskType
  status: AnalysisTaskStatus
  range_selection: TextRangeSelection
  config?: Record<string, unknown>
  progress: number
  current_step?: string
  created_at: string
  started_at?: string
  completed_at?: string
  result?: Record<string, unknown>
  error_message?: string
  meta_data?: Record<string, unknown>
}

export interface AnalysisTaskRequest {
  edition_id: number
  task_type: AnalysisTaskType
  range_selection: TextRangeSelection
  config?: Record<string, unknown>
  priority?: number
  meta_data?: Record<string, unknown>
}

// ============================================================================
// Stats Types
// ============================================================================

export interface AnalysisStats {
  edition_id: number
  tasks: {
    pending: number
    running: number
    completed: number
    failed: number
    cancelled: number
  }
  evidence: {
    character: number
    setting: number
    outline_node: number
    relation: number
  }
  last_updated?: string
}

// ============================================================================
// Character Types
// ============================================================================

export type CharacterRoleType = 'protagonist' | 'antagonist' | 'deuteragonist' | 'supporting' | 'minor' | 'mentioned'

export interface Character {
  id: string
  edition_id: number
  canonical_name: string
  role_type: CharacterRoleType
  description?: string
  aliases: CharacterAlias[]
  attributes: CharacterAttribute[]
  created_at: string
  updated_at?: string
}

export interface CharacterAlias {
  id: string
  character_id: string
  alias: string
  alias_type: 'nickname' | 'title' | 'courtesy_name' | 'other'
  created_at: string
}

export type CharacterAttributeCategory = 'appearance' | 'personality' | 'ability' | 'background' | 'relationship' | 'other'

export interface CharacterAttribute {
  id: string
  character_id: string
  category: CharacterAttributeCategory
  key: string
  value: string
  confidence?: number
  evidence_ids: string[]
  created_at: string
  updated_at?: string
}

export interface CharacterProfile {
  character: Character
  stats: {
    mention_count: number
    first_appearance?: string
    last_appearance?: string
  }
  relations: CharacterRelation[]
}

export interface CharacterRelation {
  id: string
  source_id: string
  target_id: string
  relation_type: string
  description?: string
  strength?: number
}

// ============================================================================
// Relation Graph Types
// ============================================================================

export interface RelationGraphData {
  nodes: RelationNode[]
  edges: RelationEdge[]
}

export interface RelationNode {
  id: string
  type: 'character' | 'setting' | 'outline_node'
  label: string
  data?: Record<string, unknown>
}

export interface RelationEdge {
  id: string
  source: string
  target: string
  type: string
  label?: string
  strength?: number
}

// ============================================================================
// Setting Types
// ============================================================================

export type SettingType = 'item' | 'location' | 'organization' | 'concept' | 'magic_system' | 'creature' | 'event_type'

export interface Setting {
  id: string
  edition_id: number
  name: string
  setting_type: SettingType
  description?: string
  importance: 'critical' | 'major' | 'minor' | 'background'
  first_appearance?: string
  attributes: SettingAttribute[]
  created_at: string
  updated_at?: string
}

export interface SettingAttribute {
  id: string
  setting_id: string
  key: string
  value: string
  description?: string
  created_at: string
  updated_at?: string
}

export interface SettingDetail {
  setting: Setting
  stats: {
    mention_count: number
    related_characters: string[]
    related_settings: string[]
  }
}

// ============================================================================
// Outline Types
// ============================================================================

export type OutlineType = 'main' | 'subplot' | 'character_arc'
export type OutlineNodeType = 'act' | 'chapter' | 'scene' | 'event' | 'beat'

export interface Outline {
  id: string
  edition_id: number
  title: string
  outline_type: OutlineType
  description?: string
  root_node_id?: string
  created_at: string
  updated_at?: string
}

export interface OutlineTreeNode {
  id: string
  outline_id: string
  parent_id?: string
  node_type: OutlineNodeType
  title: string
  content?: string
  sort_index: number
  children: OutlineTreeNode[]
  evidence_ids: string[]
  created_at: string
  updated_at?: string
}

export interface OutlineTree {
  outline: Outline
  nodes: OutlineTreeNode[]
}

export interface OutlineEvent {
  id: string
  node_id: string
  event_type: string
  description: string
  characters_involved: string[]
  settings_involved: string[]
  created_at: string
}

// ============================================================================
// Paginated Outline Types (Performance Optimization)
// ============================================================================

export interface OutlineNodeListItem {
  id: string
  outline_id: string
  parent_id?: string
  node_type: OutlineNodeType
  title: string
  summary?: string
  significance?: string
  sort_index: number
  depth: number
  path?: string
  chapter_start_id?: string
  chapter_end_id?: string
  has_children: boolean
  evidence_preview?: string
  evidence_full_available: boolean
  events_count: number
}

export interface PaginatedOutlineNodesResponse {
  nodes: OutlineNodeListItem[]
  next_cursor?: string
  has_more: boolean
  total_count?: number
}

export interface NodeEvidence {
  text: string
  chapter_title?: string
  start_fragment?: string
  end_fragment?: string
}

export interface NodeEvidenceResponse {
  node_id: string
  evidence_list: NodeEvidence[]
  total_count: number
}

export interface NodeEvent {
  id: string
  event_type: string
  title?: string
  description?: string
  importance?: string
}

export interface NodeDetailResponse {
  id: string
  outline_id: string
  parent_id?: string
  node_type: string
  title: string
  summary?: string
  significance?: string
  sort_index: number
  depth: number
  path?: string
  chapter_start_id?: string
  chapter_end_id?: string
  meta_data: Record<string, unknown>
  events: NodeEvent[]
  child_count: number
}

// ============================================================================
// Task Types (for task_panel.tsx)
// ============================================================================

export interface CreateTaskRequest {
  edition_id: number
  task_type: string
  target_scope: string
  target_node_ids: number[]
  parameters?: Record<string, unknown>
  priority?: number
}

export interface AnalysisResult {
  id: number
  task_id: string
  result_type: string
  result_data: Record<string, unknown>
  confidence?: number
  review_status: 'pending' | 'approved' | 'rejected'
  created_at: string
  updated_at?: string
}

export interface TaskProgress {
  task_id: string
  status: string
  current_step: string
  total_chunks: number
  completed_chunks: number
  current_chunk_info?: string
  error?: string
}

export interface TaskExecutionPlan {
  chunks: Array<{
    index: number
    node_ids: number[]
    estimated_tokens: number
  }>
  total_estimated_tokens: number
  estimated_cost_usd: number
  prompt_template_id: string
}

export interface LLMProvider {
  id: string
  name: string
  display_name: string
  description?: string
  models: string[]
  default_model: string
  requires_api_key: boolean
}

/** LLM Providers API 响应 */
export interface LLMProvidersResponse {
  success: boolean
  providers: LLMProvider[]
  default_provider: string | null
  default_priority: string[]
  fallback_chain: string[]
  task_fallback_chains: Record<string, string[]>
}

// ============================================================================
// Setting Extraction Types
// ============================================================================

export interface SettingExtractionConfig {
  setting_types: string[]
  min_importance: 'critical' | 'major' | 'minor' | 'background'
  extract_relations: boolean
  extract_attributes: boolean
  max_settings: number
  llm_provider?: string
  llm_model?: string
  temperature: number
  prompt_template_id: string
}

export interface ExtractedSettingAttribute {
  key: string
  value: string
  description?: string
}

export interface ExtractedSettingRelation {
  target_name: string
  relation_type: 'contains' | 'belongs_to' | 'produces' | 'requires' | 'opposes'
  description?: string
}

export interface ExtractedSetting {
  canonical_name: string
  setting_type: SettingType
  category: string
  importance: 'critical' | 'major' | 'minor' | 'background'
  first_appearance?: {
    chapter: string
    text: string
    context: string
  }
  description: string
  attributes: ExtractedSettingAttribute[]
  relations: ExtractedSettingRelation[]
  key_scenes: string[]
  mention_count: number
}

export interface SettingExtractionResult {
  settings: ExtractedSetting[]
  metadata: {
    total_settings: number
    by_type: Record<string, number>
    by_importance: Record<string, number>
  }
  raw_response?: string
}

export interface SettingExtractionResponse {
  success: boolean
  task_id?: string
  result?: SettingExtractionResult
  message: string
  error?: string
}

// ============================================================================
// Character Detection Types
// ============================================================================

export interface CharacterDetectionConfig {
  detect_aliases: boolean
  detect_attributes: boolean
  detect_relations: boolean
  min_confidence: number
  max_characters: number
  llm_provider?: string
  llm_model?: string
  temperature: number
  prompt_template_id: string
}

export interface CharacterDetectionRequest {
  edition_id: number
  range_selection: TextRangeSelection
  config: CharacterDetectionConfig
  work_title?: string
  known_characters?: string[]
}

export interface DetectedCharacterAlias {
  alias: string
  alias_type: 'nickname' | 'title' | 'courtesy_name' | 'other'
}

export interface DetectedCharacterAttribute {
  category: 'appearance' | 'personality' | 'ability' | 'background' | 'relationship'
  key: string
  value: string
  confidence?: number
  source_text?: string
}

export interface DetectedCharacterRelation {
  target_name: string
  relation_type: 'family' | 'friend' | 'enemy' | 'romantic' | 'professional' | 'other'
  description?: string
  evidence?: string
}

export interface DetectedCharacter {
  canonical_name: string
  aliases: DetectedCharacterAlias[]
  role_type: CharacterRoleType
  role_confidence: number
  first_appearance?: {
    chapter: string
    text: string
    context: string
  }
  description: string
  attributes: DetectedCharacterAttribute[]
  relations: DetectedCharacterRelation[]
  key_actions: string[]
  mention_count: number
}

export interface CharacterDetectionResult {
  characters: DetectedCharacter[]
  metadata: {
    total_characters: number
    protagonist_count: number
    deuteragonist_count: number
    supporting_count: number
    minor_count: number
    mentioned_count: number
  }
  raw_response?: string
}

export interface CharacterDetectionResponse {
  success: boolean
  task_id?: string
  result?: CharacterDetectionResult
  message: string
  error?: string
}

export interface CharacterMergeCandidate {
  character1_id: number
  character2_id: number
  character1_name: string
  character2_name: string
  similarity_score: number
  merge_reason: string
  suggested_action: 'merge' | 'review' | 'ignore'
}

export interface CharacterDeduplicationResult {
  merged_groups: number[][]
  merge_candidates: CharacterMergeCandidate[]
  statistics: {
    total_characters: number
    high_confidence_duplicates: number
    medium_confidence_duplicates: number
    total_candidates: number
  }
}

// ============================================================================
// Helper Functions
// ============================================================================

export function formatTokenCount(count: number): string {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}万`
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K`
  }
  return `${count}`
}

export function formatCharCount(count: number): string {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(1)}万字`
  }
  return `${count}字`
}

export function getRangeModeLabel(mode: RangeSelectionMode): string {
  const labels: Record<RangeSelectionMode, string> = {
    single_chapter: '单章选择',
    chapter_range: '连续章节',
    multi_chapter: '多章选择',
    full_edition: '整部作品',
    current_to_end: '到结尾',
    custom_range: '自定义范围',
  }
  return labels[mode] || mode
}

export function getTaskStatusLabel(status: AnalysisTaskStatus): string {
  const labels: Record<AnalysisTaskStatus, string> = {
    pending: '待处理',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return labels[status] || status
}

export function getTaskStatusColor(status: AnalysisTaskStatus): string {
  const colors: Record<AnalysisTaskStatus, string> = {
    pending: 'bg-yellow-500',
    running: 'bg-blue-500',
    completed: 'bg-green-500',
    failed: 'bg-red-500',
    cancelled: 'bg-gray-500',
  }
  return colors[status] || 'bg-gray-500'
}

export function getTaskTypeLabel(type: AnalysisTaskType): string {
  const labels: Record<AnalysisTaskType, string> = {
    outline_extraction: '大纲提取',
    character_detection: '人物检测',
    setting_extraction: '设定提取',
    relation_analysis: '关系分析',
    consistency_check: '一致性检查',
    custom_analysis: '自定义分析',
  }
  return labels[type] || type
}

/**
 * 创建范围选择对象
 */
export function createRangeSelection(
  editionId: number,
  mode: RangeSelectionMode,
  params: Partial<Omit<TextRangeSelection, 'edition_id' | 'mode'>> = {}
): TextRangeSelection {
  return {
    edition_id: editionId,
    mode,
    ...params,
  }
}

/**
 * 获取默认的范围选择
 */
export function getDefaultRangeSelection(editionId: number): TextRangeSelection {
  return {
    edition_id: editionId,
    mode: 'full_edition',
  }
}

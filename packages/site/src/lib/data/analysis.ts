// Novel Analysis Data Types
// @file analysis.ts
// @author sailing-innocent
// @date 2025-02-01

// ============================================================================
// Character Types
// ============================================================================

export type CharacterRoleType = 
  | 'protagonist' 
  | 'antagonist' 
  | 'deuteragonist' 
  | 'supporting' 
  | 'minor' 
  | 'mentioned';

export interface Character {
  id: number;
  edition_id: number;
  canonical_name: string;
  role_type: CharacterRoleType;
  description: string | null;
  first_appearance_node_id: number | null;
  status: string;
  source: string;
  importance_score: number | null;
  meta_data: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  alias_count: number;
  attribute_count: number;
  relation_count: number;
}

export interface CharacterAlias {
  id: number;
  character_id: number;
  alias: string;
  alias_type: string;
  usage_context: string | null;
  is_preferred: boolean;
  source: string;
  created_at: string | null;
}

export type CharacterAttributeCategory = 
  | 'basic' 
  | 'appearance' 
  | 'personality' 
  | 'ability' 
  | 'background' 
  | 'goal';

export interface CharacterAttribute {
  id: number;
  character_id: number;
  category: CharacterAttributeCategory;
  attr_key: string;
  attr_value: unknown;
  confidence: number | null;
  source: string;
  source_node_id: number | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface CharacterArc {
  id: number;
  character_id: number;
  arc_type: string;
  title: string;
  description: string | null;
  start_node_id: number | null;
  end_node_id: number | null;
  status: string;
  meta_data: Record<string, unknown>;
  created_at: string | null;
}

export type CharacterRelationType = 
  | 'family' 
  | 'romance' 
  | 'friendship' 
  | 'rivalry' 
  | 'mentor' 
  | 'alliance' 
  | 'enemy';

export interface CharacterRelation {
  id: number;
  edition_id: number;
  source_character_id: number;
  target_character_id: number;
  relation_type: CharacterRelationType;
  relation_subtype: string | null;
  description: string | null;
  strength: number | null;
  is_mutual: boolean;
  start_node_id: number | null;
  end_node_id: number | null;
  status: string;
  meta_data: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  source_character_name: string | null;
  target_character_name: string | null;
}

export interface CharacterProfile {
  character: Character;
  aliases: CharacterAlias[];
  attributes: Record<string, CharacterAttribute[]>;
  arcs: CharacterArc[];
  relations: CharacterRelation[];
  setting_links: CharacterSettingLink[];
}

// ============================================================================
// Setting Types
// ============================================================================

export type SettingType = 
  | 'item' 
  | 'location' 
  | 'organization' 
  | 'concept' 
  | 'magic_system' 
  | 'creature' 
  | 'event_type';

export interface Setting {
  id: number;
  edition_id: number;
  setting_type: SettingType;
  canonical_name: string;
  category: string | null;
  description: string | null;
  first_appearance_node_id: number | null;
  importance: string;
  status: string;
  source: string;
  meta_data: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  attribute_count: number;
  character_link_count: number;
}

export interface SettingAttribute {
  id: number;
  setting_id: number;
  attr_key: string;
  attr_value: unknown;
  source: string;
  source_node_id: number | null;
  status: string;
  created_at: string | null;
}

export interface SettingRelation {
  id: number;
  edition_id: number;
  source_setting_id: number;
  target_setting_id: number;
  relation_type: string;
  description: string | null;
  meta_data: Record<string, unknown>;
  created_at: string | null;
  source_setting_name: string | null;
  target_setting_name: string | null;
}

export interface CharacterSettingLink {
  id: number;
  character_id: number;
  setting_id: number;
  link_type: string;
  description: string | null;
  start_node_id: number | null;
  end_node_id: number | null;
  meta_data: Record<string, unknown>;
  created_at: string | null;
  character_name: string | null;
  setting_name: string | null;
}

export interface SettingDetail {
  setting: Setting;
  attributes: SettingAttribute[];
  character_links: CharacterSettingLink[];
  related_settings: SettingRelation[];
}

// ============================================================================
// Outline Types
// ============================================================================

export type OutlineType = 'main' | 'subplot' | 'character_arc';

export interface Outline {
  id: number;
  edition_id: number;
  outline_type: OutlineType;
  title: string;
  description: string | null;
  status: string;
  source: string;
  meta_data: Record<string, unknown>;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
  node_count: number;
}

export type OutlineNodeType = 'act' | 'arc' | 'beat' | 'scene' | 'turning_point';

export interface OutlineNode {
  id: number;
  outline_id: number;
  parent_id: number | null;
  node_type: OutlineNodeType;
  sort_index: number;
  depth: number;
  title: string;
  summary: string | null;
  significance: string;
  chapter_start_id: number | null;
  chapter_end_id: number | null;
  path: string;
  status: string;
  meta_data: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  children_count: number;
  events_count: number;
}

export type OutlineEventType = 'plot' | 'conflict' | 'revelation' | 'resolution' | 'climax';

export interface OutlineEvent {
  id: number;
  outline_node_id: number;
  event_type: OutlineEventType;
  title: string;
  description: string | null;
  chronology_order: number | null;
  narrative_order: number | null;
  importance: string;
  meta_data: Record<string, unknown>;
  created_at: string | null;
}

export interface OutlineTreeNode {
  id: number;
  node_type: string;
  title: string;
  summary: string | null;
  significance: string;
  chapter_start_id: number | null;
  chapter_end_id: number | null;
  path: string;
  depth: number;
  sort_index: number;
  status: string;
  events: OutlineEvent[];
  children: OutlineTreeNode[];
}

export interface OutlineTree {
  outline: Outline;
  nodes: OutlineTreeNode[];
}

// ============================================================================
// Evidence Types
// ============================================================================

export type EvidenceType = 'explicit' | 'implicit' | 'inferred';

export interface TextEvidence {
  id: number;
  edition_id: number;
  node_id: number;
  target_type: string;
  target_id: number;
  start_char: number | null;
  end_char: number | null;
  text_snippet: string | null;
  context_before: string | null;
  context_after: string | null;
  evidence_type: EvidenceType;
  confidence: number | null;
  source: string;
  created_at: string | null;
}

export interface ChapterAnnotation {
  id: number;
  target_id: number;
  start_char: number | null;
  end_char: number | null;
  text_snippet: string | null;
  evidence_type: string;
  confidence: number | null;
}

// ============================================================================
// Analysis Task Types
// ============================================================================

export type AnalysisTaskType = 
  | 'outline_extraction' 
  | 'character_detection' 
  | 'setting_extraction' 
  | 'relation_analysis' 
  | 'attribute_extraction';

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface AnalysisTask {
  id: number;
  edition_id: number;
  task_type: AnalysisTaskType;
  target_scope: string;
  target_node_ids: number[];
  parameters: Record<string, unknown>;
  llm_model: string | null;
  llm_prompt_template: string | null;
  status: TaskStatus;
  priority: number;
  scheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  result_summary: Record<string, unknown> | null;
  created_by: string | null;
  created_at: string | null;
  result_count: number;
}

export type ReviewStatus = 'pending' | 'approved' | 'rejected' | 'modified';

export interface AnalysisResult {
  id: number;
  task_id: number;
  result_type: string;
  result_data: Record<string, unknown>;
  confidence: number | null;
  review_status: ReviewStatus;
  reviewer: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  applied: boolean;
  applied_at: string | null;
  created_at: string | null;
}

// ============================================================================
// Relation Graph Types (for visualization)
// ============================================================================

export interface RelationGraphNode {
  id: number;
  name: string;
  role_type: string;
  importance_score: number;
}

export interface RelationGraphEdge {
  source: number;
  target: number;
  relation_type: string;
  relation_subtype: string | null;
  strength: number;
  is_mutual: boolean;
}

export interface RelationGraphData {
  nodes: RelationGraphNode[];
  edges: RelationGraphEdge[];
}

// ============================================================================
// Request Types
// ============================================================================

export interface CreateCharacterRequest {
  edition_id: number;
  canonical_name: string;
  role_type?: CharacterRoleType;
  description?: string;
  first_appearance_node_id?: number;
  meta_data?: Record<string, unknown>;
}

export interface UpdateCharacterRequest {
  canonical_name?: string;
  role_type?: CharacterRoleType;
  description?: string;
  first_appearance_node_id?: number;
  status?: string;
  importance_score?: number;
  meta_data?: Record<string, unknown>;
}

export interface CreateSettingRequest {
  edition_id: number;
  setting_type: SettingType;
  canonical_name: string;
  category?: string;
  description?: string;
  first_appearance_node_id?: number;
  importance?: string;
  meta_data?: Record<string, unknown>;
}

export interface CreateOutlineRequest {
  edition_id: number;
  title: string;
  outline_type?: OutlineType;
  description?: string;
}

export interface AddOutlineNodeRequest {
  node_type: OutlineNodeType;
  title: string;
  parent_id?: number;
  summary?: string;
  significance?: string;
  chapter_start_id?: number;
  chapter_end_id?: number;
}

export interface CreateRelationRequest {
  edition_id: number;
  source_character_id: number;
  target_character_id: number;
  relation_type: CharacterRelationType;
  relation_subtype?: string;
  description?: string;
  strength?: number;
  is_mutual?: boolean;
}

export interface CreateTaskRequest {
  edition_id: number;
  task_type: AnalysisTaskType;
  target_scope: string;
  target_node_ids?: number[];
  parameters?: Record<string, unknown>;
  llm_model?: string;
  llm_prompt_template?: string;
  priority?: number;
}

// ============================================================================
// Analysis Stats
// ============================================================================

export interface AnalysisStats {
  tasks: Record<string, number>;
  results: Record<string, number>;
  evidence: Record<string, number>;
}

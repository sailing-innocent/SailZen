export type ProjectArchetype =
  | "novel"
  | "game"
  | "research"
  | "engineering"
  | "general";

export type BlockStatus = "PLANNED" | "DOING" | "DONE" | "SKIPPED" | "MOVED";

export interface TimeBlockDTO {
  id: number;
  day_id: number;
  affair_id: number | null;
  affair_title: string | null;
  affair_kind: string | null;
  affair_domain: string | null;
  block_type: string;
  start_time: string;
  end_time: string;
  status: BlockStatus;
  pinned: boolean;
  plan_version: number;
  ref: Record<string, unknown>;
}

export interface DayTimelineDTO {
  date: string;
  day_id: number;
  plan_version: number;
  ai_rationale: string;
  blocks: TimeBlockDTO[];
  completed_minutes: number;
  planned_minutes: number;
}

export interface AffairDTO {
  id: number;
  title: string;
  description: string;
  domain: string | null;
  kind: string;
  state: string;
  urgency_ddl: string | null;
  est_minutes: number;
  parent_id: number | null;
}

export interface VentureProgressDTO {
  affair_id: number;
  title: string;
  description: string;
  state: string;
  target_date: string | null;
  days_left: number | null;
  weeks_left: number | null;
  recent_14d_hours: number;
  milestones: AffairDTO[];
  completion_ratio: number;
}

export interface WorkbenchProjectMetaDTO {
  slug: string;
  archetype: ProjectArchetype;
  vault_namespace: string;
  repo_hints: string[];
  topic_id: number | null;
  original_work_id: number | null;
}

export interface WorkbenchProjectItemDTO {
  progress: VentureProgressDTO;
  workbench: WorkbenchProjectMetaDTO;
}

export interface ContentTopicDTO {
  id: number;
  title: string;
  slug: string;
  description: string | null;
  pillar: string;
  status: string;
  rhythm_venture_id: number | null;
  vault_prefix?: string | null;
  work_count?: number;
  avg_progress_pct?: number;
  venture_title?: string | null;
}

export interface TicketDTO {
  id: number;
  tick_id: string;
  type: string;
  priority: string;
  status: string;
  title: string;
  body: string;
}

export interface WorkbenchBootstrapDTO {
  date: string;
  timeline: DayTimelineDTO;
  projects: WorkbenchProjectItemDTO[];
  focus_affairs: AffairDTO[];
  overdue_affairs: AffairDTO[];
  topics: ContentTopicDTO[];
  pending_tickets: TicketDTO[];
  degraded: string[];
}

export interface WorkbenchContextPackDTO {
  venture_id: number;
  slug: string;
  title: string;
  archetype: ProjectArchetype;
  markdown: string;
  generated_at: string;
}

export interface QuickChatResponseDTO {
  reply?: string;
  message?: string;
  mode?: string;
  actions?: unknown[];
  degraded?: boolean;
  [key: string]: unknown;
}

// ============================================================================
// Content 2.0 DTOs (/api/v1/text/*)
// ============================================================================

export interface WorkDTO {
  id: number;
  slug: string;
  title: string;
  original_title?: string | null;
  author?: string | null;
  language_primary: string;
  work_type: string;
  status: string;
  synopsis?: string | null;
  pillar: string;
  reading_status: string;
  reading_track: string;
  priority?: number;
  source_url?: string | null;
  vault_slug?: string | null;
  is_original?: boolean;
  progress_pct?: number | null;
  topic_ids?: number[];
  asset_count?: number;
}

export interface EditionDTO {
  id: number;
  work_id: number;
  edition_name?: string | null;
  language: string;
  source_format: string;
  canonical: boolean;
  word_count?: number | null;
  char_count?: number | null;
  status: string;
}

export interface TocChapterDTO {
  id: number;
  parent_id: number | null;
  sort_index: number;
  label: string | null;
  title: string | null;
  char_count: number | null;
  path: string;
  node_type: string;
}

export interface TocVolumeDTO {
  id: number;
  sort_index: number;
  label: string | null;
  title: string;
  summary: string;
  chapter_count: number;
  total_chars: number;
  chapters: TocChapterDTO[];
}

export interface EditionTocDTO {
  edition_id: number;
  total_chapters: number;
  volume_count: number;
  volumes: TocVolumeDTO[];
  ungrouped_chapters: TocChapterDTO[];
}

export interface DocumentNodeDTO {
  id: number;
  edition_id: number;
  parent_id: number | null;
  node_type: string;
  label: string | null;
  title: string | null;
  raw_text: string | null;
  path: string | null;
  sort_index: number;
  word_count: number | null;
  char_count: number | null;
  meta_data: Record<string, unknown>;
}

export interface NoteItemDTO {
  id: number;
  category: string;
  setting_file: string;
  work_id: number | null;
  edition_id: number | null;
  title: string | null;
  slug: string | null;
  meta_data: Record<string, unknown>;
}

export interface NoteItemListDTO {
  notes: NoteItemDTO[];
  total: number;
}

export interface NoteItemContentDTO {
  id: number;
  setting_file: string;
  content: string;
}

export interface ContentTopicWorkItemDTO {
  id: number;
  topic_id: number;
  work_id: number;
  role: string;
  sort_index: number;
  note: string;
  work: WorkDTO;
}

export interface TopicRhythmTaskSummaryDTO {
  id: number;
  title: string;
  kind: string;
  state: string;
  est_minutes: number;
  urgency_ddl: string | null;
}

export interface ContentTopicDetailDTO {
  topic: ContentTopicDTO;
  works: ContentTopicWorkItemDTO[];
  venture: TopicRhythmTaskSummaryDTO | null;
  rhythm_tasks: TopicRhythmTaskSummaryDTO[];
}

export interface WorkClipsExportDTO {
  work_id: number;
  work_title: string;
  vault_slug: string;
  clips_filename: string;
  card_filename: string;
  annotation_count: number;
  clips_markdown: string;
  card_markdown: string;
}

export interface VaultNoteIndexItemDTO {
  fname: string;
  namespace: string;
  title: string;
  summary: string;
  tags: string[];
  links: string[];
  pillar?: string | null;
  content_hash: string;
  source_vault: string;
}

export interface VaultNoteIndexSyncResponseDTO {
  created: number;
  updated: number;
  skipped: number;
  total_processed: number;
}

export interface ChapterSyncRequestDTO {
  node_id?: number;
  source_slug?: string;
  label?: string;
  title: string;
  content: string;
  parent_id?: number | null;
  sort_index?: number;
  meta_data?: Record<string, unknown>;
}

export interface ChapterSyncResponseDTO {
  action: "created" | "updated";
  edition_id: number;
  node: DocumentNodeDTO;
  edition_char_count: number;
  edition_word_count: number;
}

export interface WorkbenchReleaseInfoDTO {
  version: string;
  file_name: string;
  size: number;
  sha256: string;
  release_notes: string;
  published_at: string;
  download_path: string;
}

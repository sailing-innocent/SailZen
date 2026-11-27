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

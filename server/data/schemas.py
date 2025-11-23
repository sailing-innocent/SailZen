from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# ============ Base Response Models ============


class APIResponse(BaseModel):
    """Standard API response wrapper"""

    data: Optional[dict] = None
    meta: Optional[dict] = None
    error: Optional[dict] = None


class PaginationMeta(BaseModel):
    """Pagination metadata"""

    page: int = 1
    page_size: int = 20
    total: int = 0


# ============ Universe Schemas ============


class UniverseBase(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    meta_data: Optional[dict] = Field(default_factory=dict)


class UniverseCreate(UniverseBase):
    pass


class UniverseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    meta_data: Optional[dict] = None


class UniverseResponse(UniverseBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


# ============ Work Schemas ============


class WorkBase(BaseModel):
    slug: str
    title: str
    original_title: Optional[str] = None
    author: Optional[str] = None
    language_primary: str
    work_type: str = "web_novel"
    status: str = "ongoing"
    synopsis: Optional[str] = None


class WorkCreate(WorkBase):
    pass


class WorkUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    status: Optional[str] = None
    synopsis: Optional[str] = None


class WorkResponse(WorkBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


# ============ Edition Schemas ============


class EditionBase(BaseModel):
    edition_name: Optional[str] = None
    language: str
    source_format: str = "txt"
    canonical: bool = False
    source_path: Optional[str] = None
    source_checksum: Optional[str] = None
    ingest_version: int = 1
    publication_year: Optional[int] = None
    word_count: Optional[int] = None
    description: Optional[str] = None
    status: str = "draft"


class EditionCreate(EditionBase):
    work_id: UUID


class EditionUpdate(BaseModel):
    edition_name: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    word_count: Optional[int] = None


class EditionResponse(EditionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_id: UUID
    created_at: datetime
    updated_at: datetime


# ============ DocumentNode Schemas ============


class DocumentNodeBase(BaseModel):
    node_type: str
    sort_index: int
    depth: int
    label: Optional[str] = None
    title: Optional[str] = None
    raw_text: Optional[str] = None
    word_count: Optional[int] = None
    char_count: Optional[int] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    path: str
    status: str = "active"


class DocumentNodeCreate(BaseModel):
    edition_id: UUID
    parent_id: Optional[UUID] = None
    node_type: str
    sort_index: int
    depth: int
    label: Optional[str] = None
    title: Optional[str] = None
    raw_text: Optional[str] = None
    path: str


class DocumentNodeUpdate(BaseModel):
    label: Optional[str] = None
    title: Optional[str] = None
    raw_text: Optional[str] = None
    status: Optional[str] = None


class DocumentNodeResponse(DocumentNodeBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    edition_id: UUID
    parent_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class DocumentNodeTree(DocumentNodeResponse):
    """Document node with children for tree view"""

    children: Optional[List["DocumentNodeTree"]] = None


# ============ TextSpan Schemas ============


class TextSpanBase(BaseModel):
    span_type: str = "explicit"
    start_char: int
    end_char: int
    text_snippet: Optional[str] = None
    created_by: str = "system"


class TextSpanCreate(BaseModel):
    node_id: UUID
    span_type: str = "explicit"
    start_char: int
    end_char: int
    text_snippet: Optional[str] = None
    created_by: str = "system"


class TextSpanResponse(TextSpanBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    node_id: UUID
    created_at: datetime


# ============ Entity Schemas ============


class EntityBase(BaseModel):
    entity_type: str
    canonical_name: str
    description: Optional[str] = None
    scope: str = "edition"
    status: str = "draft"


class EntityCreate(BaseModel):
    entity_type: str
    canonical_name: str
    description: Optional[str] = None
    edition_id: Optional[UUID] = None
    work_id: Optional[UUID] = None
    universe_id: Optional[UUID] = None
    origin_span_id: Optional[UUID] = None
    scope: str = "edition"


class EntityUpdate(BaseModel):
    canonical_name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class EntityResponse(EntityBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    universe_id: Optional[UUID] = None
    work_id: Optional[UUID] = None
    edition_id: Optional[UUID] = None
    origin_span_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


# ============ EntityAlias Schemas ============


class EntityAliasCreate(BaseModel):
    entity_id: UUID
    alias: str
    language: Optional[str] = None
    alias_type: str = "nickname"
    is_preferred: bool = False


class EntityAliasResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_id: UUID
    alias: str
    language: Optional[str] = None
    alias_type: str
    is_preferred: bool


# ============ EntityMention Schemas ============


class EntityMentionCreate(BaseModel):
    entity_id: UUID
    span_id: UUID
    mention_type: str = "explicit"
    confidence: Optional[float] = None


class EntityMentionUpdate(BaseModel):
    is_verified: bool = True
    verified_by: Optional[str] = None


class EntityMentionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_id: UUID
    span_id: UUID
    mention_type: str
    confidence: Optional[float] = None
    is_verified: bool
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None


# ============ EntityRelation Schemas ============


class EntityRelationBase(BaseModel):
    relation_type: str
    direction: str = "directed"
    description: Optional[str] = None
    status: str = "draft"


class EntityRelationCreate(BaseModel):
    source_entity_id: UUID
    target_entity_id: UUID
    relation_type: str
    direction: str = "directed"
    description: Optional[str] = None
    edition_id: Optional[UUID] = None
    work_id: Optional[UUID] = None
    universe_id: Optional[UUID] = None


class EntityRelationUpdate(BaseModel):
    description: Optional[str] = None
    status: Optional[str] = None


class EntityRelationResponse(EntityRelationBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    universe_id: Optional[UUID] = None
    work_id: Optional[UUID] = None
    edition_id: Optional[UUID] = None
    source_entity_id: UUID
    target_entity_id: UUID
    created_at: datetime
    updated_at: datetime


# ============ Text Import Schemas ============


class TextImportRequest(BaseModel):
    """Request for importing text file"""

    edition_id: UUID
    file_path: str
    encoding: str = "utf-8"
    parse_chapters: bool = True


class TextImportResponse(BaseModel):
    """Response for text import"""

    edition_id: UUID
    nodes_created: int
    spans_created: int
    total_chars: int
    total_words: int
    status: str


# ============ Ingest-by-Text (MVP Simplified) ============


class IngestTextBody(BaseModel):
    """Body for POST /editions/{edition_id}/ingest (MVP simplified)"""

    text: str
    parse_mode: str = "simple"


# ============ Mock Extract / Accept (MVP Simplified) ============


class ExtractEntitySuggestion(BaseModel):
    canonical_name: str
    entity_type: str
    aliases: List[str] = []
    first_mention_text: str | None = None
    start_char: int | None = None
    end_char: int | None = None


class ExtractEntitiesRequest(BaseModel):
    edition_id: UUID
    node_id: UUID
    text: str


class ExtractEntitiesResponse(BaseModel):
    suggestions: List[ExtractEntitySuggestion]


class AcceptEntitiesRequest(BaseModel):
    edition_id: UUID
    node_id: UUID
    suggestions: List[ExtractEntitySuggestion]


class AcceptEntitiesResponse(BaseModel):
    created_entities: int
    created_mentions: int


# ============ Collaborative Session Schemas ============


class SessionCreate(BaseModel):
    edition_id: UUID
    target_type: str  # node | entity | relation | event
    target_id: UUID
    lock_scope: str = "node"
    created_by: str
    meta_data: Optional[dict] = Field(default_factory=dict)


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    edition_id: UUID
    target_type: str
    target_id: UUID
    lock_scope: str
    state: str
    state_reason: Optional[str] = None
    meta_data: dict
    created_by: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None


class SessionStateUpdate(BaseModel):
    state: str
    state_reason: Optional[str] = None


# ============ Annotation Batch Schemas ============


class AnnotationBatchCreate(BaseModel):
    edition_id: UUID
    batch_type: str  # llm_suggestion | human_draft | merged
    source: str
    session_id: Optional[UUID] = None
    created_by: Optional[str] = None
    notes: Optional[str] = None


class AnnotationBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    edition_id: UUID
    session_id: Optional[UUID] = None
    batch_type: str
    source: str
    status: str
    confidence: dict
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AnnotationItemCreate(BaseModel):
    batch_id: UUID
    target_type: str
    payload: dict
    target_id: Optional[UUID] = None
    span_id: Optional[UUID] = None
    confidence: Optional[float] = None


class AnnotationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    target_type: str
    target_id: Optional[UUID] = None
    span_id: Optional[UUID] = None
    payload: dict
    confidence: Optional[float] = None
    status: str
    created_at: datetime


class AnnotationItemStatusUpdate(BaseModel):
    status: str  # pending | approved | rejected


# ============ LLM Suggestion Schemas ============


class LLMSuggestionRequest(BaseModel):
    text: str
    context: Optional[str] = None
    node_id: Optional[UUID] = None


class LLMSuggestionResponse(BaseModel):
    batch_id: UUID
    suggestions: List[AnnotationItemResponse]
    meta: dict = Field(default_factory=dict)


# ============ Change Set Schemas ============


class ChangeSetCreate(BaseModel):
    edition_id: UUID
    source: str
    session_id: Optional[UUID] = None
    created_by: Optional[str] = None
    reason: Optional[str] = None


class ChangeSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    edition_id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    source: str
    reason: Optional[str] = None
    status: str
    created_by: Optional[str] = None
    created_at: datetime
    applied_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ChangeItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    change_set_id: UUID
    target_table: str
    target_id: Optional[UUID] = None
    operation: str
    column_name: Optional[str] = None
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    span_id: Optional[UUID] = None
    notes: Optional[str] = None


class CommitRequest(BaseModel):
    """Request to commit a session (generate change set from approved items)"""

    batch_ids: List[UUID]
    reason: Optional[str] = None


# ============ Review Task Schemas ============


class ReviewTaskCreate(BaseModel):
    change_set_id: UUID
    reviewer: str
    comments: Optional[str] = None


class ReviewTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    change_set_id: UUID
    reviewer: str
    status: str
    decided_at: Optional[datetime] = None
    decision: Optional[str] = None
    comments: Optional[str] = None
    created_at: datetime


class ReviewDecision(BaseModel):
    comments: Optional[str] = None


# ============ Diff View Schemas ============


class DiffEntity(BaseModel):
    """Represents an entity in diff view"""

    annotation_item_id: UUID
    canonical_name: str
    entity_type: str
    aliases: List[str]
    first_mention_text: str
    confidence: float
    status: str  # pending | approved | rejected
    span_id: Optional[UUID] = None


class SessionDiffResponse(BaseModel):
    """Diff view for a session showing all suggestions"""

    session_id: UUID
    session_state: str
    batches: List[AnnotationBatchResponse]
    suggestions: List[DiffEntity]
    approved_count: int
    rejected_count: int
    pending_count: int


# ============ Narrative Event Schemas ============


class NarrativeEventBase(BaseModel):
    work_id: UUID
    edition_id: Optional[UUID] = None
    title: str
    event_type: str = "plot_point"
    summary: Optional[str] = None
    start_span_id: Optional[UUID] = None
    end_span_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    chronology_order: Optional[float] = None
    importance: str = "major"
    status: str = "draft"
    meta_data: Optional[dict] = Field(default_factory=dict)


class NarrativeEventCreate(NarrativeEventBase):
    pass


class NarrativeEventUpdate(BaseModel):
    title: Optional[str] = None
    event_type: Optional[str] = None
    summary: Optional[str] = None
    start_span_id: Optional[UUID] = None
    end_span_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    chronology_order: Optional[float] = None
    importance: Optional[str] = None
    status: Optional[str] = None
    meta_data: Optional[dict] = None


class NarrativeEventResponse(NarrativeEventBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


# ============ Event Participant Schemas ============


class EventParticipantBase(BaseModel):
    event_id: UUID
    entity_id: UUID
    role: str = "participant"
    contribution: Optional[str] = None
    span_id: Optional[UUID] = None


class EventParticipantCreate(EventParticipantBase):
    pass


class EventParticipantUpdate(BaseModel):
    role: Optional[str] = None
    contribution: Optional[str] = None
    span_id: Optional[UUID] = None


class EventParticipantResponse(EventParticipantBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


# ============ Knowledge Collection Schemas ============


class KnowledgeCollectionBase(BaseModel):
    work_id: UUID
    name: str
    collection_type: str
    description: Optional[str] = None
    meta_data: Optional[dict] = Field(default_factory=dict)


class KnowledgeCollectionCreate(KnowledgeCollectionBase):
    pass


class KnowledgeCollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    meta_data: Optional[dict] = None


class KnowledgeCollectionResponse(KnowledgeCollectionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


# ============ Collection Item Schemas ============


class CollectionItemBase(BaseModel):
    collection_id: UUID
    target_type: str
    target_id: UUID
    sort_order: Optional[int] = None
    role_in_collection: Optional[str] = None
    notes: Optional[str] = None


class CollectionItemCreate(CollectionItemBase):
    pass


class CollectionItemUpdate(BaseModel):
    sort_order: Optional[int] = None
    role_in_collection: Optional[str] = None
    notes: Optional[str] = None


class CollectionItemResponse(CollectionItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime

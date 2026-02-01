# -*- coding: utf-8 -*-
# @file analysis.py
# @brief Novel Analysis API Controllers
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------

from litestar import Controller, get, post, put, delete
from litestar.di import Provide
from litestar.params import Parameter
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from sail_server.db import provide_db_session
from sail_server.data.analysis import (
    CharacterData, CharacterAliasData, CharacterAttributeData, CharacterArcData, CharacterRelationData,
    SettingData, SettingAttributeData, SettingRelationData, CharacterSettingLinkData,
    OutlineData, OutlineNodeData, OutlineEventData,
    TextEvidenceData, AnalysisTaskData, AnalysisResultData,
    CharacterProfile, SettingDetail, OutlineTree, RelationGraphData,
)


# ============================================================================
# Request/Response Models
# ============================================================================

@dataclass
class CreateCharacterRequest:
    edition_id: int
    canonical_name: str
    role_type: str = "supporting"
    description: Optional[str] = None
    first_appearance_node_id: Optional[int] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UpdateCharacterRequest:
    canonical_name: Optional[str] = None
    role_type: Optional[str] = None
    description: Optional[str] = None
    first_appearance_node_id: Optional[int] = None
    status: Optional[str] = None
    importance_score: Optional[float] = None
    meta_data: Optional[Dict[str, Any]] = None


@dataclass
class AddAliasRequest:
    alias: str
    alias_type: str = "nickname"
    usage_context: Optional[str] = None
    is_preferred: bool = False


@dataclass
class AddAttributeRequest:
    category: str
    attr_key: str
    attr_value: Any
    confidence: Optional[float] = None
    source_node_id: Optional[int] = None


@dataclass
class AddArcRequest:
    arc_type: str
    title: str
    description: Optional[str] = None
    start_node_id: Optional[int] = None
    end_node_id: Optional[int] = None


@dataclass
class CreateRelationRequest:
    edition_id: int
    source_character_id: int
    target_character_id: int
    relation_type: str
    relation_subtype: Optional[str] = None
    description: Optional[str] = None
    strength: Optional[float] = None
    is_mutual: bool = True


@dataclass
class CreateSettingRequest:
    edition_id: int
    setting_type: str
    canonical_name: str
    category: Optional[str] = None
    description: Optional[str] = None
    first_appearance_node_id: Optional[int] = None
    importance: str = "normal"
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UpdateSettingRequest:
    setting_type: Optional[str] = None
    canonical_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    importance: Optional[str] = None
    status: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None


@dataclass
class AddSettingAttributeRequest:
    attr_key: str
    attr_value: Any
    source_node_id: Optional[int] = None


@dataclass
class CreateSettingRelationRequest:
    edition_id: int
    source_setting_id: int
    target_setting_id: int
    relation_type: str
    description: Optional[str] = None


@dataclass
class CreateCharacterSettingLinkRequest:
    character_id: int
    setting_id: int
    link_type: str
    description: Optional[str] = None


@dataclass
class CreateOutlineRequest:
    edition_id: int
    title: str
    outline_type: str = "main"
    description: Optional[str] = None


@dataclass
class AddOutlineNodeRequest:
    node_type: str
    title: str
    parent_id: Optional[int] = None
    summary: Optional[str] = None
    significance: str = "normal"
    chapter_start_id: Optional[int] = None
    chapter_end_id: Optional[int] = None


@dataclass
class UpdateOutlineNodeRequest:
    title: Optional[str] = None
    summary: Optional[str] = None
    significance: Optional[str] = None
    chapter_start_id: Optional[int] = None
    chapter_end_id: Optional[int] = None
    status: Optional[str] = None


@dataclass
class AddEventRequest:
    event_type: str
    title: str
    description: Optional[str] = None
    chronology_order: Optional[float] = None
    narrative_order: Optional[int] = None
    importance: str = "normal"


@dataclass
class AddEvidenceRequest:
    edition_id: int
    node_id: int
    target_type: str
    target_id: int
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    text_snippet: Optional[str] = None
    evidence_type: str = "explicit"
    confidence: Optional[float] = None


@dataclass
class CreateTaskRequest:
    edition_id: int
    task_type: str
    target_scope: str
    target_node_ids: List[int] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    llm_model: Optional[str] = None
    llm_prompt_template: Optional[str] = None
    priority: int = 0


@dataclass
class ModifyResultRequest:
    result_data: Dict[str, Any]


# ============================================================================
# Character Controller
# ============================================================================

class CharacterController(Controller):
    path = "/character"
    dependencies = {"db": Provide(provide_db_session)}

    @post("/")
    async def create_character(self, db: Session, data: CreateCharacterRequest) -> CharacterData:
        from sail_server.model.analysis.character import create_character_impl
        char_data = CharacterData(
            edition_id=data.edition_id,
            canonical_name=data.canonical_name,
            role_type=data.role_type,
            description=data.description,
            first_appearance_node_id=data.first_appearance_node_id,
            meta_data=data.meta_data,
        )
        return create_character_impl(db, char_data)

    @get("/{character_id:int}")
    async def get_character(self, db: Session, character_id: int) -> Optional[CharacterData]:
        from sail_server.model.analysis.character import get_character_impl
        return get_character_impl(db, character_id)

    @get("/edition/{edition_id:int}")
    async def get_characters_by_edition(
        self, 
        db: Session, 
        edition_id: int,
        role_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[CharacterData]:
        from sail_server.model.analysis.character import get_characters_by_edition_impl
        return get_characters_by_edition_impl(db, edition_id, role_type, skip, limit)

    @put("/{character_id:int}")
    async def update_character(self, db: Session, character_id: int, data: UpdateCharacterRequest) -> Optional[CharacterData]:
        from sail_server.model.analysis.character import get_character_impl, update_character_impl
        existing = get_character_impl(db, character_id)
        if not existing:
            return None
        
        char_data = CharacterData(
            id=character_id,
            edition_id=existing.edition_id,
            canonical_name=data.canonical_name or existing.canonical_name,
            role_type=data.role_type or existing.role_type,
            description=data.description if data.description is not None else existing.description,
            first_appearance_node_id=data.first_appearance_node_id if data.first_appearance_node_id is not None else existing.first_appearance_node_id,
            status=data.status or existing.status,
            importance_score=data.importance_score if data.importance_score is not None else existing.importance_score,
            meta_data=data.meta_data if data.meta_data is not None else existing.meta_data,
        )
        return update_character_impl(db, character_id, char_data)

    @delete("/{character_id:int}", status_code=200)
    async def delete_character(self, db: Session, character_id: int) -> dict:
        from sail_server.model.analysis.character import delete_character_impl
        success = delete_character_impl(db, character_id)
        return {"success": success}

    @get("/search")
    async def search_characters(
        self, 
        db: Session, 
        edition_id: int,
        keyword: str,
        skip: int = 0,
        limit: int = 50
    ) -> List[CharacterData]:
        from sail_server.model.analysis.character import search_characters_impl
        return search_characters_impl(db, edition_id, keyword, skip, limit)

    @get("/{character_id:int}/profile")
    async def get_character_profile(self, db: Session, character_id: int) -> Optional[CharacterProfile]:
        from sail_server.model.analysis.character import get_character_profile_impl
        return get_character_profile_impl(db, character_id)

    # Alias endpoints
    @post("/{character_id:int}/alias")
    async def add_alias(self, db: Session, character_id: int, data: AddAliasRequest) -> Optional[CharacterAliasData]:
        from sail_server.model.analysis.character import add_character_alias_impl
        return add_character_alias_impl(
            db, character_id, data.alias, data.alias_type, data.usage_context, data.is_preferred
        )

    @get("/{character_id:int}/aliases")
    async def get_aliases(self, db: Session, character_id: int) -> List[CharacterAliasData]:
        from sail_server.model.analysis.character import get_character_aliases_impl
        return get_character_aliases_impl(db, character_id)

    @delete("/alias/{alias_id:int}", status_code=200)
    async def remove_alias(self, db: Session, alias_id: int) -> dict:
        from sail_server.model.analysis.character import remove_character_alias_impl
        success = remove_character_alias_impl(db, alias_id)
        return {"success": success}

    # Attribute endpoints
    @post("/{character_id:int}/attribute")
    async def add_attribute(self, db: Session, character_id: int, data: AddAttributeRequest) -> Optional[CharacterAttributeData]:
        from sail_server.model.analysis.character import add_character_attribute_impl
        return add_character_attribute_impl(
            db, character_id, data.category, data.attr_key, data.attr_value, 
            data.confidence, data.source_node_id
        )

    @get("/{character_id:int}/attributes")
    async def get_attributes(self, db: Session, character_id: int, category: Optional[str] = None) -> List[CharacterAttributeData]:
        from sail_server.model.analysis.character import get_character_attributes_impl
        return get_character_attributes_impl(db, character_id, category)

    @delete("/attribute/{attr_id:int}", status_code=200)
    async def delete_attribute(self, db: Session, attr_id: int) -> dict:
        from sail_server.model.analysis.character import delete_character_attribute_impl
        success = delete_character_attribute_impl(db, attr_id)
        return {"success": success}

    # Arc endpoints
    @post("/{character_id:int}/arc")
    async def add_arc(self, db: Session, character_id: int, data: AddArcRequest) -> Optional[CharacterArcData]:
        from sail_server.model.analysis.character import add_character_arc_impl
        return add_character_arc_impl(
            db, character_id, data.arc_type, data.title, data.description,
            data.start_node_id, data.end_node_id
        )

    @get("/{character_id:int}/arcs")
    async def get_arcs(self, db: Session, character_id: int) -> List[CharacterArcData]:
        from sail_server.model.analysis.character import get_character_arcs_impl
        return get_character_arcs_impl(db, character_id)

    @delete("/arc/{arc_id:int}", status_code=200)
    async def delete_arc(self, db: Session, arc_id: int) -> dict:
        from sail_server.model.analysis.character import delete_character_arc_impl
        success = delete_character_arc_impl(db, arc_id)
        return {"success": success}


# ============================================================================
# Relation Controller
# ============================================================================

class RelationController(Controller):
    path = "/relation"
    dependencies = {"db": Provide(provide_db_session)}

    @post("/")
    async def create_relation(self, db: Session, data: CreateRelationRequest) -> CharacterRelationData:
        from sail_server.model.analysis.character import create_character_relation_impl
        rel_data = CharacterRelationData(
            edition_id=data.edition_id,
            source_character_id=data.source_character_id,
            target_character_id=data.target_character_id,
            relation_type=data.relation_type,
            relation_subtype=data.relation_subtype,
            description=data.description,
            strength=data.strength,
            is_mutual=data.is_mutual,
        )
        return create_character_relation_impl(db, rel_data)

    @get("/edition/{edition_id:int}")
    async def get_edition_relations(self, db: Session, edition_id: int) -> List[CharacterRelationData]:
        from sail_server.model.analysis.character import get_edition_relations_impl
        return get_edition_relations_impl(db, edition_id)

    @get("/character/{character_id:int}")
    async def get_character_relations(self, db: Session, character_id: int) -> List[CharacterRelationData]:
        from sail_server.model.analysis.character import get_character_relations_impl
        return get_character_relations_impl(db, character_id)

    @get("/graph/{edition_id:int}")
    async def get_relation_graph(self, db: Session, edition_id: int) -> RelationGraphData:
        from sail_server.model.analysis.character import get_relation_graph_impl
        return get_relation_graph_impl(db, edition_id)

    @delete("/{relation_id:int}", status_code=200)
    async def delete_relation(self, db: Session, relation_id: int) -> dict:
        from sail_server.model.analysis.character import delete_character_relation_impl
        success = delete_character_relation_impl(db, relation_id)
        return {"success": success}


# ============================================================================
# Setting Controller
# ============================================================================

class SettingController(Controller):
    path = "/setting"
    dependencies = {"db": Provide(provide_db_session)}

    @post("/")
    async def create_setting(self, db: Session, data: CreateSettingRequest) -> SettingData:
        from sail_server.model.analysis.setting import create_setting_impl
        setting_data = SettingData(
            edition_id=data.edition_id,
            setting_type=data.setting_type,
            canonical_name=data.canonical_name,
            category=data.category,
            description=data.description,
            first_appearance_node_id=data.first_appearance_node_id,
            importance=data.importance,
            meta_data=data.meta_data,
        )
        return create_setting_impl(db, setting_data)

    @get("/{setting_id:int}")
    async def get_setting(self, db: Session, setting_id: int) -> Optional[SettingData]:
        from sail_server.model.analysis.setting import get_setting_impl
        return get_setting_impl(db, setting_id)

    @get("/edition/{edition_id:int}")
    async def get_settings_by_edition(
        self, 
        db: Session, 
        edition_id: int,
        setting_type: Optional[str] = None,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[SettingData]:
        from sail_server.model.analysis.setting import get_settings_by_edition_impl
        return get_settings_by_edition_impl(db, edition_id, setting_type, category, skip, limit)

    @put("/{setting_id:int}")
    async def update_setting(self, db: Session, setting_id: int, data: UpdateSettingRequest) -> Optional[SettingData]:
        from sail_server.model.analysis.setting import get_setting_impl, update_setting_impl
        existing = get_setting_impl(db, setting_id)
        if not existing:
            return None
        
        setting_data = SettingData(
            id=setting_id,
            edition_id=existing.edition_id,
            setting_type=data.setting_type or existing.setting_type,
            canonical_name=data.canonical_name or existing.canonical_name,
            category=data.category if data.category is not None else existing.category,
            description=data.description if data.description is not None else existing.description,
            importance=data.importance or existing.importance,
            status=data.status or existing.status,
            meta_data=data.meta_data if data.meta_data is not None else existing.meta_data,
        )
        return update_setting_impl(db, setting_id, setting_data)

    @delete("/{setting_id:int}", status_code=200)
    async def delete_setting(self, db: Session, setting_id: int) -> dict:
        from sail_server.model.analysis.setting import delete_setting_impl
        success = delete_setting_impl(db, setting_id)
        return {"success": success}

    @get("/{setting_id:int}/detail")
    async def get_setting_detail(self, db: Session, setting_id: int) -> Optional[SettingDetail]:
        from sail_server.model.analysis.setting import get_setting_detail_impl
        return get_setting_detail_impl(db, setting_id)

    @get("/types/{edition_id:int}")
    async def get_setting_types(self, db: Session, edition_id: int) -> List[dict]:
        from sail_server.model.analysis.setting import get_setting_types_impl
        return get_setting_types_impl(db, edition_id)

    # Attribute endpoints
    @post("/{setting_id:int}/attribute")
    async def add_attribute(self, db: Session, setting_id: int, data: AddSettingAttributeRequest) -> Optional[SettingAttributeData]:
        from sail_server.model.analysis.setting import add_setting_attribute_impl
        return add_setting_attribute_impl(db, setting_id, data.attr_key, data.attr_value, data.source_node_id)

    @get("/{setting_id:int}/attributes")
    async def get_attributes(self, db: Session, setting_id: int) -> List[SettingAttributeData]:
        from sail_server.model.analysis.setting import get_setting_attributes_impl
        return get_setting_attributes_impl(db, setting_id)

    @delete("/attribute/{attr_id:int}", status_code=200)
    async def delete_attribute(self, db: Session, attr_id: int) -> dict:
        from sail_server.model.analysis.setting import delete_setting_attribute_impl
        success = delete_setting_attribute_impl(db, attr_id)
        return {"success": success}


# ============================================================================
# Setting Relation Controller
# ============================================================================

class SettingRelationController(Controller):
    path = "/setting-relation"
    dependencies = {"db": Provide(provide_db_session)}

    @post("/")
    async def create_relation(self, db: Session, data: CreateSettingRelationRequest) -> SettingRelationData:
        from sail_server.model.analysis.setting import create_setting_relation_impl
        rel_data = SettingRelationData(
            edition_id=data.edition_id,
            source_setting_id=data.source_setting_id,
            target_setting_id=data.target_setting_id,
            relation_type=data.relation_type,
            description=data.description,
        )
        return create_setting_relation_impl(db, rel_data)

    @get("/{setting_id:int}")
    async def get_setting_relations(self, db: Session, setting_id: int) -> List[SettingRelationData]:
        from sail_server.model.analysis.setting import get_setting_relations_impl
        return get_setting_relations_impl(db, setting_id)

    @delete("/{relation_id:int}", status_code=200)
    async def delete_relation(self, db: Session, relation_id: int) -> dict:
        from sail_server.model.analysis.setting import delete_setting_relation_impl
        success = delete_setting_relation_impl(db, relation_id)
        return {"success": success}


# ============================================================================
# Character-Setting Link Controller
# ============================================================================

class CharacterSettingLinkController(Controller):
    path = "/character-setting-link"
    dependencies = {"db": Provide(provide_db_session)}

    @post("/")
    async def create_link(self, db: Session, data: CreateCharacterSettingLinkRequest) -> Optional[CharacterSettingLinkData]:
        from sail_server.model.analysis.setting import create_character_setting_link_impl
        return create_character_setting_link_impl(
            db, data.character_id, data.setting_id, data.link_type, data.description
        )

    @get("/character/{character_id:int}")
    async def get_character_settings(self, db: Session, character_id: int) -> List[SettingData]:
        from sail_server.model.analysis.setting import get_character_settings_impl
        return get_character_settings_impl(db, character_id)

    @get("/setting/{setting_id:int}")
    async def get_setting_characters(self, db: Session, setting_id: int) -> List[dict]:
        from sail_server.model.analysis.setting import get_setting_characters_impl
        return get_setting_characters_impl(db, setting_id)

    @delete("/{link_id:int}", status_code=200)
    async def delete_link(self, db: Session, link_id: int) -> dict:
        from sail_server.model.analysis.setting import delete_character_setting_link_impl
        success = delete_character_setting_link_impl(db, link_id)
        return {"success": success}


# ============================================================================
# Outline Controller
# ============================================================================

class OutlineController(Controller):
    path = "/outline"
    dependencies = {"db": Provide(provide_db_session)}

    @post("/")
    async def create_outline(self, db: Session, data: CreateOutlineRequest) -> OutlineData:
        from sail_server.model.analysis.outline import create_outline_impl
        outline_data = OutlineData(
            edition_id=data.edition_id,
            title=data.title,
            outline_type=data.outline_type,
            description=data.description,
        )
        return create_outline_impl(db, outline_data)

    @get("/{outline_id:int}")
    async def get_outline(self, db: Session, outline_id: int) -> Optional[OutlineData]:
        from sail_server.model.analysis.outline import get_outline_impl
        return get_outline_impl(db, outline_id)

    @get("/edition/{edition_id:int}")
    async def get_outlines_by_edition(self, db: Session, edition_id: int) -> List[OutlineData]:
        from sail_server.model.analysis.outline import get_outlines_by_edition_impl
        return get_outlines_by_edition_impl(db, edition_id)

    @delete("/{outline_id:int}", status_code=200)
    async def delete_outline(self, db: Session, outline_id: int) -> dict:
        from sail_server.model.analysis.outline import delete_outline_impl
        success = delete_outline_impl(db, outline_id)
        return {"success": success}

    @get("/{outline_id:int}/tree")
    async def get_outline_tree(self, db: Session, outline_id: int) -> Optional[OutlineTree]:
        from sail_server.model.analysis.outline import get_outline_tree_impl
        return get_outline_tree_impl(db, outline_id)

    # Node endpoints
    @post("/{outline_id:int}/node")
    async def add_node(self, db: Session, outline_id: int, data: AddOutlineNodeRequest) -> Optional[OutlineNodeData]:
        from sail_server.model.analysis.outline import add_outline_node_impl
        return add_outline_node_impl(
            db, outline_id, data.node_type, data.title, data.parent_id,
            data.summary, data.significance, data.chapter_start_id, data.chapter_end_id
        )

    @get("/node/{node_id:int}")
    async def get_node(self, db: Session, node_id: int) -> Optional[OutlineNodeData]:
        from sail_server.model.analysis.outline import get_outline_node_impl
        return get_outline_node_impl(db, node_id)

    @put("/node/{node_id:int}")
    async def update_node(self, db: Session, node_id: int, data: UpdateOutlineNodeRequest) -> Optional[OutlineNodeData]:
        from sail_server.model.analysis.outline import get_outline_node_impl, update_outline_node_impl
        existing = get_outline_node_impl(db, node_id)
        if not existing:
            return None
        
        node_data = OutlineNodeData(
            id=node_id,
            outline_id=existing.outline_id,
            node_type=existing.node_type,
            sort_index=existing.sort_index,
            path=existing.path,
            title=data.title or existing.title,
            summary=data.summary if data.summary is not None else existing.summary,
            significance=data.significance or existing.significance,
            chapter_start_id=data.chapter_start_id if data.chapter_start_id is not None else existing.chapter_start_id,
            chapter_end_id=data.chapter_end_id if data.chapter_end_id is not None else existing.chapter_end_id,
            status=data.status or existing.status,
        )
        return update_outline_node_impl(db, node_id, node_data)

    @delete("/node/{node_id:int}", status_code=200)
    async def delete_node(self, db: Session, node_id: int) -> dict:
        from sail_server.model.analysis.outline import delete_outline_node_impl
        success = delete_outline_node_impl(db, node_id)
        return {"success": success}

    # Event endpoints
    @post("/node/{node_id:int}/event")
    async def add_event(self, db: Session, node_id: int, data: AddEventRequest) -> Optional[OutlineEventData]:
        from sail_server.model.analysis.outline import add_outline_event_impl
        return add_outline_event_impl(
            db, node_id, data.event_type, data.title, data.description,
            data.chronology_order, data.narrative_order, data.importance
        )

    @get("/node/{node_id:int}/events")
    async def get_events(self, db: Session, node_id: int) -> List[OutlineEventData]:
        from sail_server.model.analysis.outline import get_node_events_impl
        return get_node_events_impl(db, node_id)

    @delete("/event/{event_id:int}", status_code=200)
    async def delete_event(self, db: Session, event_id: int) -> dict:
        from sail_server.model.analysis.outline import delete_outline_event_impl
        success = delete_outline_event_impl(db, event_id)
        return {"success": success}


# ============================================================================
# Evidence Controller
# ============================================================================

class EvidenceController(Controller):
    path = "/evidence"
    dependencies = {"db": Provide(provide_db_session)}

    @post("/")
    async def add_evidence(self, db: Session, data: AddEvidenceRequest) -> TextEvidenceData:
        from sail_server.model.analysis.evidence import add_text_evidence_impl
        return add_text_evidence_impl(
            db, data.edition_id, data.node_id, data.target_type, data.target_id,
            data.start_char, data.end_char, data.text_snippet, None, None,
            data.evidence_type, data.confidence
        )

    @get("/target/{target_type:str}/{target_id:int}")
    async def get_evidence_for_target(self, db: Session, target_type: str, target_id: int) -> List[TextEvidenceData]:
        from sail_server.model.analysis.evidence import get_evidence_for_target_impl
        return get_evidence_for_target_impl(db, target_type, target_id)

    @get("/chapter/{node_id:int}")
    async def get_chapter_annotations(self, db: Session, node_id: int) -> Dict[str, List[Dict[str, Any]]]:
        from sail_server.model.analysis.evidence import get_chapter_annotations_impl
        return get_chapter_annotations_impl(db, node_id)

    @delete("/{evidence_id:int}", status_code=200)
    async def delete_evidence(self, db: Session, evidence_id: int) -> dict:
        from sail_server.model.analysis.evidence import delete_text_evidence_impl
        success = delete_text_evidence_impl(db, evidence_id)
        return {"success": success}


# ============================================================================
# Analysis Task Controller
# ============================================================================

class AnalysisTaskController(Controller):
    path = "/task"
    dependencies = {"db": Provide(provide_db_session)}

    @post("/")
    async def create_task(self, db: Session, data: CreateTaskRequest) -> AnalysisTaskData:
        from sail_server.model.analysis.evidence import create_analysis_task_impl
        task_data = AnalysisTaskData(
            edition_id=data.edition_id,
            task_type=data.task_type,
            target_scope=data.target_scope,
            target_node_ids=data.target_node_ids,
            parameters=data.parameters,
            llm_model=data.llm_model,
            llm_prompt_template=data.llm_prompt_template,
            priority=data.priority,
        )
        return create_analysis_task_impl(db, task_data)

    @get("/{task_id:int}")
    async def get_task(self, db: Session, task_id: int) -> Optional[AnalysisTaskData]:
        from sail_server.model.analysis.evidence import get_analysis_task_impl
        return get_analysis_task_impl(db, task_id)

    @get("/edition/{edition_id:int}")
    async def get_tasks_by_edition(
        self, 
        db: Session, 
        edition_id: int,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[AnalysisTaskData]:
        from sail_server.model.analysis.evidence import get_tasks_by_edition_impl
        return get_tasks_by_edition_impl(db, edition_id, status, task_type, skip, limit)

    @post("/{task_id:int}/cancel")
    async def cancel_task(self, db: Session, task_id: int) -> dict:
        from sail_server.model.analysis.evidence import cancel_task_impl
        success = cancel_task_impl(db, task_id)
        return {"success": success}

    @get("/{task_id:int}/results")
    async def get_task_results(
        self, 
        db: Session, 
        task_id: int,
        review_status: Optional[str] = None
    ) -> List[AnalysisResultData]:
        from sail_server.model.analysis.evidence import get_task_results_impl
        return get_task_results_impl(db, task_id, review_status)

    @post("/result/{result_id:int}/approve")
    async def approve_result(self, db: Session, result_id: int, reviewer: str = "system") -> dict:
        from sail_server.model.analysis.evidence import approve_result_impl
        success = approve_result_impl(db, result_id, reviewer)
        return {"success": success}

    @post("/result/{result_id:int}/reject")
    async def reject_result(self, db: Session, result_id: int, reviewer: str = "system", notes: Optional[str] = None) -> dict:
        from sail_server.model.analysis.evidence import reject_result_impl
        success = reject_result_impl(db, result_id, reviewer, notes)
        return {"success": success}

    @post("/result/{result_id:int}/modify")
    async def modify_result(self, db: Session, result_id: int, data: ModifyResultRequest, reviewer: str = "system") -> Optional[AnalysisResultData]:
        from sail_server.model.analysis.evidence import modify_result_impl
        return modify_result_impl(db, result_id, data.result_data, reviewer)

    @post("/{task_id:int}/apply-all")
    async def apply_all_results(self, db: Session, task_id: int) -> Dict[str, int]:
        from sail_server.model.analysis.evidence import apply_all_approved_impl
        return apply_all_approved_impl(db, task_id)

    @get("/stats/{edition_id:int}")
    async def get_analysis_stats(self, db: Session, edition_id: int) -> Dict[str, Any]:
        from sail_server.model.analysis.evidence import get_analysis_stats_impl
        return get_analysis_stats_impl(db, edition_id)

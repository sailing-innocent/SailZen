# -*- coding: utf-8 -*-
# @file llm_brainstorm_service.py
# @brief LLM-powered brainstorming service for creative content generation
# @author sailing-innocent
# @date 2025-11-09

import json
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from server.service.llm_service import get_llm_service
from server.service.work_service import WorkService
from server.service.entity_service import EntityService
from server.service.event_service import EventService

logger = logging.getLogger(__name__)


class BrainstormService:
    """Service for LLM-powered creative brainstorming"""

    def __init__(self, db):
        self.db = db
        self.work_service = WorkService(db)
        self.entity_service = EntityService(db)
        self.event_service = EventService(db)
        self.llm_service = get_llm_service()

    async def brainstorm_characters(
        self,
        work_id: UUID,
        existing_knowledge: Optional[List[str]] = None,
        constraints: Optional[str] = None,
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        """Generate character ideas using LLM

        Args:
            work_id: Work context
            existing_knowledge: Existing entity/event IDs for context
            constraints: User-specified requirements
            count: Number of suggestions to generate

        Returns:
            List of character suggestions with properties
        """
        if not self.llm_service:
            logger.warning("LLM service not available")
            return []

        # Get work context
        work = self.work_service.get_work(work_id)
        if not work:
            raise ValueError(f"Work {work_id} not found")

        # Collect existing entities for context
        existing_entities = self.work_service.list_work_entities(work_id, limit=50)
        existing_events = self.work_service.list_work_events(work_id, limit=30)

        # Build context string
        context_parts = [
            f"作品标题：{work.title}",
            f"作品类型：{work.work_type}",
        ]

        if work.synopsis:
            context_parts.append(f"作品简介：{work.synopsis}")

        if existing_entities:
            entity_list = "\n".join([
                f"- {e.canonical_name} ({e.entity_type}): {e.description or '无描述'}"
                for e in existing_entities[:10]
            ])
            context_parts.append(f"\n现有人物：\n{entity_list}")

        if existing_events:
            event_list = "\n".join([
                f"- {ev.title} ({ev.event_type}): {ev.summary or '无描述'}"
                for ev in existing_events[:10]
            ])
            context_parts.append(f"\n现有情节：\n{event_list}")

        if constraints:
            context_parts.append(f"\n用户要求：{constraints}")

        context = "\n".join(context_parts)

        # Create prompt
        system_message = """你是一个创意写作助手，擅长构思小说人物。
请根据提供的作品背景和现有设定，生成新的人物创意。
每个人物应该有：
1. 姓名（canonical_name）
2. 类型（entity_type: character/organization/concept）
3. 描述（description）：包含外貌、性格、背景等
4. 创意说明（rationale）：为什么这个人物适合这个故事

请以JSON数组格式输出，每个元素包含：name, type, description, rationale
"""

        user_message = f"""请为以下作品生成 {count} 个新人物创意：

{context}

要求：
- 人物应该与现有设定协调
- 避免与现有人物重复
- 提供丰富的背景和特点
- 考虑人物在故事中的作用

请输出JSON数组。"""

        try:
            response = await self.llm_service.call_llm(
                system_message=system_message,
                user_message=user_message,
                temperature=0.8,  # Higher for creativity
                max_tokens=2000,
            )

            # Parse response
            suggestions = self._parse_json_response(response)
            
            # Format suggestions
            formatted = []
            for i, s in enumerate(suggestions[:count]):
                formatted.append({
                    "id": f"char_{i}",
                    "type": "entity",
                    "title": s.get("name", f"新角色{i+1}"),
                    "description": s.get("description", ""),
                    "rationale": s.get("rationale", ""),
                    "suggested_properties": {
                        "entity_type": s.get("type", "character"),
                        "canonical_name": s.get("name", f"新角色{i+1}"),
                    }
                })

            return formatted

        except Exception as e:
            logger.error(f"Failed to generate character ideas: {e}")
            return []

    async def brainstorm_plot_points(
        self,
        work_id: UUID,
        existing_knowledge: Optional[List[str]] = None,
        constraints: Optional[str] = None,
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        """Generate plot point ideas using LLM"""
        if not self.llm_service:
            logger.warning("LLM service not available")
            return []

        work = self.work_service.get_work(work_id)
        if not work:
            raise ValueError(f"Work {work_id} not found")

        # Get context
        existing_entities = self.work_service.list_work_entities(work_id, limit=30)
        existing_events = self.work_service.list_work_events(work_id, limit=50)

        context_parts = [
            f"作品标题：{work.title}",
            f"作品类型：{work.work_type}",
        ]

        if work.synopsis:
            context_parts.append(f"作品简介：{work.synopsis}")

        if existing_entities:
            entity_list = ", ".join([e.canonical_name for e in existing_entities[:15]])
            context_parts.append(f"\n主要人物：{entity_list}")

        if existing_events:
            event_list = "\n".join([
                f"- {ev.title}: {ev.summary or '无描述'}"
                for ev in existing_events[:10]
            ])
            context_parts.append(f"\n现有情节：\n{event_list}")

        if constraints:
            context_parts.append(f"\n用户要求：{constraints}")

        context = "\n".join(context_parts)

        system_message = """你是一个创意写作助手，擅长构思故事情节。
请根据提供的作品背景和现有情节，生成新的情节点创意。
每个情节应该有：
1. 标题（title）
2. 类型（event_type: plot_point/backstory/foreshadow/climax/resolution）
3. 摘要（summary）：情节的详细描述
4. 重要性（importance: major/minor/background）
5. 创意说明（rationale）：为什么这个情节适合这个故事

请以JSON数组格式输出。"""

        user_message = f"""请为以下作品生成 {count} 个新情节创意：

{context}

要求：
- 情节应该推动故事发展
- 与现有情节协调
- 考虑人物成长和冲突
- 提供转折或悬念

请输出JSON数组。"""

        try:
            response = await self.llm_service.call_llm(
                system_message=system_message,
                user_message=user_message,
                temperature=0.8,
                max_tokens=2000,
            )

            suggestions = self._parse_json_response(response)
            
            formatted = []
            for i, s in enumerate(suggestions[:count]):
                formatted.append({
                    "id": f"plot_{i}",
                    "type": "event",
                    "title": s.get("title", f"新情节{i+1}"),
                    "description": s.get("summary", ""),
                    "rationale": s.get("rationale", ""),
                    "suggested_properties": {
                        "event_type": s.get("event_type", "plot_point"),
                        "importance": s.get("importance", "major"),
                    }
                })

            return formatted

        except Exception as e:
            logger.error(f"Failed to generate plot ideas: {e}")
            return []

    async def brainstorm_world_elements(
        self,
        work_id: UUID,
        element_type: str = "location",  # location, item, concept
        existing_knowledge: Optional[List[str]] = None,
        constraints: Optional[str] = None,
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        """Generate world-building elements (locations, items, concepts)"""
        if not self.llm_service:
            logger.warning("LLM service not available")
            return []

        work = self.work_service.get_work(work_id)
        if not work:
            raise ValueError(f"Work {work_id} not found")

        # Get context
        existing_entities = self.work_service.list_work_entities(work_id, limit=50)
        
        # Filter by type for context
        same_type = [e for e in existing_entities if e.entity_type == element_type]

        context_parts = [
            f"作品标题：{work.title}",
            f"作品类型：{work.work_type}",
        ]

        if work.synopsis:
            context_parts.append(f"作品简介：{work.synopsis}")

        if same_type:
            element_list = "\n".join([
                f"- {e.canonical_name}: {e.description or '无描述'}"
                for e in same_type[:10]
            ])
            context_parts.append(f"\n现有{element_type}：\n{element_list}")

        if constraints:
            context_parts.append(f"\n用户要求：{constraints}")

        context = "\n".join(context_parts)

        type_names = {
            "location": "地点/场景",
            "item": "物品/道具",
            "concept": "概念/设定",
        }

        system_message = f"""你是一个创意写作助手，擅长构思世界观元素。
请根据提供的作品背景，生成新的{type_names.get(element_type, element_type)}创意。
每个元素应该有：
1. 名称（name）
2. 描述（description）：详细的设定
3. 创意说明（rationale）：为什么适合这个世界

请以JSON数组格式输出。"""

        user_message = f"""请为以下作品生成 {count} 个新{type_names.get(element_type, element_type)}创意：

{context}

要求：
- 元素应该丰富世界观
- 与现有设定协调
- 具有独特性和记忆点
- 可以在情节中发挥作用

请输出JSON数组。"""

        try:
            response = await self.llm_service.call_llm(
                system_message=system_message,
                user_message=user_message,
                temperature=0.8,
                max_tokens=2000,
            )

            suggestions = self._parse_json_response(response)
            
            formatted = []
            for i, s in enumerate(suggestions[:count]):
                formatted.append({
                    "id": f"{element_type}_{i}",
                    "type": "entity",
                    "title": s.get("name", f"新{type_names[element_type]}{i+1}"),
                    "description": s.get("description", ""),
                    "rationale": s.get("rationale", ""),
                    "suggested_properties": {
                        "entity_type": element_type,
                        "canonical_name": s.get("name", f"新{type_names[element_type]}{i+1}"),
                    }
                })

            return formatted

        except Exception as e:
            logger.error(f"Failed to generate world elements: {e}")
            return []

    async def elaborate_idea(
        self,
        work_id: UUID,
        idea: str,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Elaborate on a seed idea with details"""
        if not self.llm_service:
            logger.warning("LLM service not available")
            return {"elaboration": idea}

        work = self.work_service.get_work(work_id)
        if not work:
            raise ValueError(f"Work {work_id} not found")

        context_parts = [
            f"作品标题：{work.title}",
            f"作品类型：{work.work_type}",
        ]

        if work.synopsis:
            context_parts.append(f"作品简介：{work.synopsis}")

        if context:
            context_parts.append(f"\n补充背景：{context}")

        work_context = "\n".join(context_parts)

        system_message = """你是一个创意写作助手，擅长扩展和细化创意。
请根据提供的简单创意，扩展成详细的设定。
包括：
- 详细描述
- 背景故事
- 特点和特征
- 在故事中的作用
- 相关元素的联系

输出应该丰富而具体。"""

        user_message = f"""作品背景：
{work_context}

简单创意：
{idea}

请将这个创意扩展成详细的设定描述。"""

        try:
            response = await self.llm_service.call_llm(
                system_message=system_message,
                user_message=user_message,
                temperature=0.7,
                max_tokens=1500,
            )

            return {
                "elaboration": response,
                "original_idea": idea,
            }

        except Exception as e:
            logger.error(f"Failed to elaborate idea: {e}")
            return {"elaboration": idea, "error": str(e)}

    async def find_connections(
        self,
        work_id: UUID,
        entity_ids: List[UUID],
    ) -> List[Dict[str, Any]]:
        """Suggest relationships between existing elements"""
        if not self.llm_service:
            logger.warning("LLM service not available")
            return []

        if len(entity_ids) < 2:
            return []

        work = self.work_service.get_work(work_id)
        if not work:
            raise ValueError(f"Work {work_id} not found")

        # Get entities
        entities = []
        for eid in entity_ids:
            entity = self.entity_service.get_entity(eid)
            if entity:
                entities.append(entity)

        if len(entities) < 2:
            return []

        # Build entity descriptions
        entity_desc = "\n".join([
            f"- {e.canonical_name} ({e.entity_type}): {e.description or '无描述'}"
            for e in entities
        ])

        system_message = """你是一个创意写作助手，擅长发现元素之间的关联。
请分析给定的人物/元素，建议可能的关系和互动。
每个关系应该有：
1. 源实体和目标实体
2. 关系类型（family/alliance/conflict/ownership/mentorship等）
3. 关系描述
4. 创意说明

请以JSON数组格式输出，每个元素包含：
source_id, target_id, relation_type, description, rationale"""

        user_message = f"""作品：{work.title}

分析以下元素之间可能的关系：
{entity_desc}

请建议 2-3 个有趣的关系连接。"""

        try:
            response = await self.llm_service.call_llm(
                system_message=system_message,
                user_message=user_message,
                temperature=0.7,
                max_tokens=1500,
            )

            suggestions = self._parse_json_response(response)
            
            formatted = []
            for i, s in enumerate(suggestions[:5]):
                # Map indices to entity IDs
                source_idx = s.get("source_id", 0)
                target_idx = s.get("target_id", 1)
                
                if isinstance(source_idx, int) and 0 <= source_idx < len(entities):
                    source_id = str(entities[source_idx].id)
                else:
                    source_id = str(entities[0].id)
                    
                if isinstance(target_idx, int) and 0 <= target_idx < len(entities):
                    target_id = str(entities[target_idx].id)
                else:
                    target_id = str(entities[1].id) if len(entities) > 1 else str(entities[0].id)

                formatted.append({
                    "id": f"conn_{i}",
                    "type": "relation",
                    "title": f"{s.get('relation_type', 'relation')}",
                    "description": s.get("description", ""),
                    "rationale": s.get("rationale", ""),
                    "suggested_properties": {
                        "source_entity_id": source_id,
                        "target_entity_id": target_id,
                        "relation_type": s.get("relation_type", "connection"),
                    }
                })

            return formatted

        except Exception as e:
            logger.error(f"Failed to find connections: {e}")
            return []

    def _parse_json_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse JSON from LLM response, handling markdown code blocks"""
        # Try to extract JSON from markdown code blocks
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            response = response[start:end].strip()

        try:
            data = json.loads(response)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response[:500]}")
            return []


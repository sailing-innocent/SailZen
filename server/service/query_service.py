# -*- coding: utf-8 -*-
# @file query_service.py
# @brief Service layer for complex cross-table queries
# @author sailing-innocent
# @date 2025-04-21

from sqlalchemy.orm import Session, joinedload, aliased
from typing import List, Dict, Any, Optional
from uuid import UUID

from server.model.entity import Entity, EntityMention
from server.model.relation import EntityRelation
from server.model.document_node import DocumentNode, TextSpan


class QueryService:
    """Service for complex cross-table queries"""

    def __init__(self, db: Session):
        self.db = db

    def get_entity_mention_locations(self, entity_id: UUID) -> List[Dict[str, Any]]:
        """Get all locations where an entity is mentioned with context"""
        mentions = (
            self.db.query(EntityMention, TextSpan, DocumentNode)
            .join(TextSpan, EntityMention.span_id == TextSpan.id)
            .join(DocumentNode, TextSpan.node_id == DocumentNode.id)
            .filter(EntityMention.entity_id == entity_id)
            .order_by(DocumentNode.path)
            .all()
        )

        results = []
        for mention, span, node in mentions:
            results.append(
                {
                    "mention_id": str(mention.id),
                    "node_id": str(node.id),
                    "node_path": node.path,
                    "node_title": node.title,
                    "node_type": node.node_type,
                    "span_start": span.start_char,
                    "span_end": span.end_char,
                    "text_snippet": span.text_snippet,
                    "mention_type": mention.mention_type,
                    "confidence": float(mention.confidence)
                    if mention.confidence
                    else None,
                    "is_verified": mention.is_verified,
                }
            )

        return results

    def get_entity_relations_network(
        self, entity_id: UUID, max_depth: int = 1
    ) -> Dict[str, Any]:
        """Get relationship network for an entity"""
        # Create aliases for source and target entities
        SourceEntity = aliased(Entity)
        TargetEntity = aliased(Entity)
        
        # Get direct relations
        relations = (
            self.db.query(EntityRelation, SourceEntity, TargetEntity)
            .join(SourceEntity, EntityRelation.source_entity_id == SourceEntity.id)
            .join(TargetEntity, EntityRelation.target_entity_id == TargetEntity.id, isouter=True)
            .filter(
                (EntityRelation.source_entity_id == entity_id)
                | (EntityRelation.target_entity_id == entity_id)
            )
            .all()
        )

        nodes = {}
        edges = []

        # Add center entity
        center_entity = self.db.query(Entity).filter(Entity.id == entity_id).first()
        if center_entity:
            nodes[str(entity_id)] = {
                "id": str(entity_id),
                "name": center_entity.canonical_name,
                "type": center_entity.entity_type,
                "is_center": True,
            }

        # Build network
        for relation, source_entity, target_entity in relations:
            # Add source entity
            if str(source_entity.id) not in nodes:
                nodes[str(source_entity.id)] = {
                    "id": str(source_entity.id),
                    "name": source_entity.canonical_name,
                    "type": source_entity.entity_type,
                    "is_center": source_entity.id == entity_id,
                }

            # Add target entity
            if target_entity and str(target_entity.id) not in nodes:
                nodes[str(target_entity.id)] = {
                    "id": str(target_entity.id),
                    "name": target_entity.canonical_name,
                    "type": target_entity.entity_type,
                    "is_center": target_entity.id == entity_id,
                }

            # Add edge
            edges.append(
                {
                    "id": str(relation.id),
                    "source": str(relation.source_entity_id),
                    "target": str(relation.target_entity_id),
                    "relation_type": relation.relation_type,
                    "direction": relation.direction,
                    "description": relation.description,
                }
            )

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
        }

    def get_chapter_entities(self, node_id: UUID) -> List[Dict[str, Any]]:
        """Get all entities mentioned in a chapter/node and its children"""
        # Get node and all descendants
        node = self.db.query(DocumentNode).filter(DocumentNode.id == node_id).first()
        if not node:
            return []

        # Query all nodes in the subtree (using path prefix)
        path_prefix = node.path + "."
        descendant_nodes = (
            self.db.query(DocumentNode)
            .filter(
                (DocumentNode.id == node_id)
                | (DocumentNode.path.startswith(path_prefix))
            )
            .all()
        )

        node_ids = [n.id for n in descendant_nodes]

        # Get all entities mentioned in these nodes
        entity_mentions = (
            self.db.query(Entity, EntityMention, TextSpan)
            .join(EntityMention, Entity.id == EntityMention.entity_id)
            .join(TextSpan, EntityMention.span_id == TextSpan.id)
            .filter(TextSpan.node_id.in_(node_ids))
            .all()
        )

        # Group by entity
        entity_map = {}
        for entity, mention, span in entity_mentions:
            entity_id_str = str(entity.id)
            if entity_id_str not in entity_map:
                entity_map[entity_id_str] = {
                    "entity_id": entity_id_str,
                    "canonical_name": entity.canonical_name,
                    "entity_type": entity.entity_type,
                    "mention_count": 0,
                    "mentions": [],
                }

            entity_map[entity_id_str]["mention_count"] += 1
            entity_map[entity_id_str]["mentions"].append(
                {
                    "span_id": str(span.id),
                    "start_char": span.start_char,
                    "end_char": span.end_char,
                    "text_snippet": span.text_snippet,
                }
            )

        return list(entity_map.values())

    def search_text_in_edition(
        self, edition_id: UUID, search_query: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search for text within an edition's nodes"""
        nodes = (
            self.db.query(DocumentNode)
            .filter(
                DocumentNode.edition_id == edition_id,
                DocumentNode.raw_text.ilike(f"%{search_query}%"),
            )
            .limit(limit)
            .all()
        )

        results = []
        for node in nodes:
            # Find occurrences in text
            if node.raw_text:
                text_lower = node.raw_text.lower()
                query_lower = search_query.lower()
                start_pos = 0

                while True:
                    pos = text_lower.find(query_lower, start_pos)
                    if pos == -1:
                        break

                    # Extract context (50 chars before and after)
                    context_start = max(0, pos - 50)
                    context_end = min(len(node.raw_text), pos + len(search_query) + 50)
                    context = node.raw_text[context_start:context_end]

                    results.append(
                        {
                            "node_id": str(node.id),
                            "node_title": node.title,
                            "node_path": node.path,
                            "position": pos,
                            "context": context,
                        }
                    )

                    start_pos = pos + 1
                    if len(results) >= limit:
                        break

                if len(results) >= limit:
                    break

        return results

    def get_edition_statistics(self, edition_id: UUID) -> Dict[str, Any]:
        """Get comprehensive statistics for an edition"""
        # Node counts by type
        node_stats = (
            self.db.query(
                DocumentNode.node_type,
                self.db.func.count(DocumentNode.id),
                self.db.func.sum(DocumentNode.word_count),
                self.db.func.sum(DocumentNode.char_count),
            )
            .filter(DocumentNode.edition_id == edition_id)
            .group_by(DocumentNode.node_type)
            .all()
        )

        # Entity counts by type
        entity_stats = (
            self.db.query(Entity.entity_type, self.db.func.count(Entity.id))
            .filter(Entity.edition_id == edition_id)
            .group_by(Entity.entity_type)
            .all()
        )

        # Relation counts by type
        relation_stats = (
            self.db.query(
                EntityRelation.relation_type, self.db.func.count(EntityRelation.id)
            )
            .filter(EntityRelation.edition_id == edition_id)
            .group_by(EntityRelation.relation_type)
            .all()
        )

        return {
            "nodes": [
                {
                    "type": node_type,
                    "count": count,
                    "total_words": int(words or 0),
                    "total_chars": int(chars or 0),
                }
                for node_type, count, words, chars in node_stats
            ],
            "entities": [
                {"type": entity_type, "count": count}
                for entity_type, count in entity_stats
            ],
            "relations": [
                {"type": relation_type, "count": count}
                for relation_type, count in relation_stats
            ],
        }

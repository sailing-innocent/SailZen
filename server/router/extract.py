# -*- coding: utf-8 -*-
# @file extract.py
# @brief MVP mock extract and accept endpoints (no session/batch)

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from server.db import g_db_func
from server.data.schemas import (
    ExtractEntitiesRequest,
    ExtractEntitiesResponse,
    ExtractEntitySuggestion,
    AcceptEntitiesRequest,
    AcceptEntitiesResponse,
)
from server.service.llm_mock_service import extract_entities_mock
from server.model.document_node import DocumentNode, TextSpan
from server.model.entity import Entity, EntityAlias, EntityMention


router = APIRouter(prefix="/api/v1", tags=["extract"])


def get_db(db: Session = Depends(g_db_func)):
    return db


@router.post("/extract/entities", response_model=ExtractEntitiesResponse)
def extract_entities(payload: ExtractEntitiesRequest) -> ExtractEntitiesResponse:
    """Return mock entity suggestions for given text (MVP)."""
    suggestions = extract_entities_mock(payload.text)
    return ExtractEntitiesResponse(
        suggestions=[ExtractEntitySuggestion(**s) for s in suggestions]
    )


@router.post("/accept/entities", response_model=AcceptEntitiesResponse)
def accept_entities(
    payload: AcceptEntitiesRequest, db: Session = Depends(get_db)
) -> AcceptEntitiesResponse:
    """Accept suggestions: upsert entities, aliases, and mentions (creating spans when needed)."""
    # Validate node
    node: DocumentNode | None = (
        db.query(DocumentNode).filter(DocumentNode.id == payload.node_id).first()
    )
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    created_entities = 0
    created_mentions = 0

    for sug in payload.suggestions:
        # Upsert entity
        entity: Entity | None = (
            db.query(Entity)
            .filter(
                Entity.canonical_name == sug.canonical_name,
                Entity.entity_type == sug.entity_type,
                Entity.edition_id == payload.edition_id,
            )
            .first()
        )
        if not entity:
            entity = Entity(
                canonical_name=sug.canonical_name,
                entity_type=sug.entity_type,
                edition_id=payload.edition_id,
                scope="edition",
                status="draft",
            )
            db.add(entity)
            db.flush()
            created_entities += 1

        # Upsert aliases
        for alias in sug.aliases or []:
            exists = (
                db.query(EntityAlias)
                .filter(EntityAlias.entity_id == entity.id, EntityAlias.alias == alias)
                .first()
            )
            if not exists:
                db.add(EntityAlias(entity_id=entity.id, alias=alias))

        # Ensure span exists
        start = sug.start_char
        end = sug.end_char
        if (start is None or end is None) and node.raw_text and sug.first_mention_text:
            idx = node.raw_text.find(sug.first_mention_text)
            if idx >= 0:
                start = idx
                end = idx + len(sug.first_mention_text)

        span: TextSpan | None = None
        if start is not None and end is not None:
            span = (
                db.query(TextSpan)
                .filter(
                    TextSpan.node_id == node.id,
                    TextSpan.start_char == start,
                    TextSpan.end_char == end,
                )
                .first()
            )
            if not span:
                span = TextSpan(
                    node_id=node.id,
                    span_type="paragraph",
                    start_char=int(start),
                    end_char=int(end),
                    text_snippet=(node.raw_text[start:end] if node.raw_text else None),
                )
                db.add(span)
                db.flush()

        # Create mention if we have a span
        if span is not None:
            exists_m = (
                db.query(EntityMention)
                .filter(
                    EntityMention.entity_id == entity.id,
                    EntityMention.span_id == span.id,
                )
                .first()
            )
            if not exists_m:
                db.add(
                    EntityMention(
                        entity_id=entity.id,
                        span_id=span.id,
                        mention_type="explicit",
                    )
                )
                created_mentions += 1

    db.commit()

    return AcceptEntitiesResponse(
        created_entities=created_entities,
        created_mentions=created_mentions,
    )

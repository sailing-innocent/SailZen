# -*- coding: utf-8 -*-
# @file nodes.py
# @brief API routes for document nodes and text spans
# @author sailing-innocent
# @date 2025-04-21

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from server.db import g_db_func
from server.service.text_service import TextService
from server.service.query_service import QueryService
from server.data.schemas import (
    DocumentNodeCreate,
    DocumentNodeResponse,
    DocumentNodeTree,
    TextSpanCreate,
    TextSpanResponse,
    TextImportRequest,
    TextImportResponse,
    IngestTextBody,
)

router = APIRouter(prefix="/api/v1", tags=["nodes"])


def get_text_service(db: Session = Depends(g_db_func)):
    return TextService(db)


def get_query_service(db: Session = Depends(g_db_func)):
    return QueryService(db)


# ============ Document Node Endpoints ============


@router.post(
    "/nodes", response_model=DocumentNodeResponse, status_code=status.HTTP_201_CREATED
)
def create_node(
    node: DocumentNodeCreate, service: TextService = Depends(get_text_service)
):
    """Create a new document node"""
    try:
        return service.create_node(node)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/editions/{edition_id}/nodes", response_model=List[DocumentNodeResponse])
def list_edition_nodes(
    edition_id: UUID,
    node_type: Optional[str] = None,
    parent_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100,
    service: TextService = Depends(get_text_service),
):
    """List all nodes for an edition"""
    return service.list_nodes(
        edition_id=edition_id,
        node_type=node_type,
        parent_id=parent_id,
        skip=skip,
        limit=limit,
    )


@router.get("/editions/{edition_id}/tree", response_model=List[DocumentNodeTree])
def get_edition_tree(
    edition_id: UUID,
    max_depth: int = 3,
    service: TextService = Depends(get_text_service),
):
    """Get document tree structure for an edition"""
    return service.get_node_tree(edition_id, max_depth=max_depth)


@router.get("/nodes/{node_id}", response_model=DocumentNodeResponse)
def get_node(node_id: UUID, service: TextService = Depends(get_text_service)):
    """Get document node by ID"""
    node = service.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.get("/nodes/{node_id}/children", response_model=List[DocumentNodeResponse])
def get_node_children(node_id: UUID, service: TextService = Depends(get_text_service)):
    """Get all children of a node"""
    return service.get_node_children(node_id)


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(node_id: UUID, service: TextService = Depends(get_text_service)):
    """Delete a document node"""
    if not service.delete_node(node_id):
        raise HTTPException(status_code=404, detail="Node not found")


# ============ Text Span Endpoints ============


@router.post(
    "/spans", response_model=TextSpanResponse, status_code=status.HTTP_201_CREATED
)
def create_span(span: TextSpanCreate, service: TextService = Depends(get_text_service)):
    """Create a new text span"""
    try:
        return service.create_span(span)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/nodes/{node_id}/spans", response_model=List[TextSpanResponse])
def get_node_spans(node_id: UUID, service: TextService = Depends(get_text_service)):
    """Get all spans for a node"""
    return service.get_node_spans(node_id)


# ============ Text Import Endpoint ============


@router.post("/import-text", response_model=TextImportResponse)
def import_text(
    request: TextImportRequest, service: TextService = Depends(get_text_service)
):
    """Import a text file and create document structure"""
    try:
        return service.import_text_file(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/editions/{edition_id}/ingest", response_model=TextImportResponse)
def ingest_text_content(
    edition_id: UUID,
    body: IngestTextBody,
    service: TextService = Depends(get_text_service),
):
    """Ingest raw text content into nodes/spans (MVP simplified)."""
    try:
        return service.import_text_content(edition_id, body.text, body.parse_mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")


# ============ Query Endpoints ============


@router.get("/editions/{edition_id}/search")
def search_text(
    edition_id: UUID,
    q: str,
    limit: int = 50,
    service: QueryService = Depends(get_query_service),
):
    """Search for text within an edition"""
    if not q or len(q) < 2:
        raise HTTPException(
            status_code=400, detail="Query must be at least 2 characters"
        )
    return service.search_text_in_edition(edition_id, q, limit=limit)


@router.get("/editions/{edition_id}/statistics")
def get_edition_statistics(
    edition_id: UUID, service: QueryService = Depends(get_query_service)
):
    """Get comprehensive statistics for an edition"""
    return service.get_edition_statistics(edition_id)


@router.get("/nodes/{node_id}/entities")
def get_chapter_entities(
    node_id: UUID, service: QueryService = Depends(get_query_service)
):
    """Get all entities mentioned in a chapter/node"""
    return service.get_chapter_entities(node_id)

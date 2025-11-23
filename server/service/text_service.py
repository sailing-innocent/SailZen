# -*- coding: utf-8 -*-
# @file text_service.py
# @brief Service layer for text import and document node management
# @author sailing-innocent
# @date 2025-04-21

from sqlalchemy.orm import Session
from typing import List, Optional, Tuple
from uuid import UUID
import re
import hashlib

from server.model.document_node import DocumentNode, TextSpan
from server.model.work import Edition
from server.data.schemas import (
    DocumentNodeCreate,
    DocumentNodeResponse,
    DocumentNodeTree,
    TextSpanCreate,
    TextSpanResponse,
    TextImportRequest,
    TextImportResponse,
)


class TextService:
    """Service for text import and document node management"""

    def __init__(self, db: Session):
        self.db = db

    # ============ Document Node Methods ============

    def create_node(self, node_data: DocumentNodeCreate) -> DocumentNodeResponse:
        """Create a new document node"""
        # Calculate checksums and counts if raw_text is provided
        extra_data = {}
        if node_data.raw_text:
            extra_data["text_checksum"] = hashlib.sha256(
                node_data.raw_text.encode()
            ).hexdigest()[:16]
            extra_data["char_count"] = len(node_data.raw_text)
            extra_data["word_count"] = len(node_data.raw_text.split())

        db_node = DocumentNode(**node_data.model_dump(), **extra_data)
        self.db.add(db_node)
        self.db.commit()
        self.db.refresh(db_node)
        return DocumentNodeResponse.model_validate(db_node)

    def get_node(self, node_id: UUID) -> Optional[DocumentNodeResponse]:
        """Get document node by ID"""
        node = self.db.query(DocumentNode).filter(DocumentNode.id == node_id).first()
        if node:
            return DocumentNodeResponse.model_validate(node)
        return None

    def list_nodes(
        self,
        edition_id: UUID,
        node_type: Optional[str] = None,
        parent_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[DocumentNodeResponse]:
        """List document nodes with filters"""
        query = self.db.query(DocumentNode).filter(
            DocumentNode.edition_id == edition_id
        )
        if node_type:
            query = query.filter(DocumentNode.node_type == node_type)
        if parent_id:
            query = query.filter(DocumentNode.parent_id == parent_id)

        nodes = query.order_by(DocumentNode.path).offset(skip).limit(limit).all()
        return [DocumentNodeResponse.model_validate(n) for n in nodes]

    def get_node_tree(
        self, edition_id: UUID, max_depth: int = 3
    ) -> List[DocumentNodeTree]:
        """Get document node tree structure"""
        # Get all nodes up to max_depth
        nodes = (
            self.db.query(DocumentNode)
            .filter(
                DocumentNode.edition_id == edition_id, DocumentNode.depth <= max_depth
            )
            .order_by(DocumentNode.path)
            .all()
        )

        # Build tree structure
        node_map = {
            str(node.id): DocumentNodeTree.model_validate(node) for node in nodes
        }
        root_nodes = []

        for node_data in node_map.values():
            if node_data.parent_id:
                parent_id_str = str(node_data.parent_id)
                if parent_id_str in node_map:
                    parent = node_map[parent_id_str]
                    if parent.children is None:
                        parent.children = []
                    parent.children.append(node_data)
            else:
                root_nodes.append(node_data)

        return root_nodes

    def get_node_children(self, node_id: UUID) -> List[DocumentNodeResponse]:
        """Get all children of a node"""
        children = (
            self.db.query(DocumentNode)
            .filter(DocumentNode.parent_id == node_id)
            .order_by(DocumentNode.sort_index)
            .all()
        )
        return [DocumentNodeResponse.model_validate(c) for c in children]

    def delete_node(self, node_id: UUID) -> bool:
        """Delete a document node"""
        node = self.db.query(DocumentNode).filter(DocumentNode.id == node_id).first()
        if not node:
            return False
        self.db.delete(node)
        self.db.commit()
        return True

    # ============ Text Span Methods ============

    def create_span(self, span_data: TextSpanCreate) -> TextSpanResponse:
        """Create a new text span"""
        db_span = TextSpan(**span_data.model_dump())
        self.db.add(db_span)
        self.db.commit()
        self.db.refresh(db_span)
        return TextSpanResponse.model_validate(db_span)

    def get_node_spans(self, node_id: UUID) -> List[TextSpanResponse]:
        """Get all spans for a node"""
        spans = self.db.query(TextSpan).filter(TextSpan.node_id == node_id).all()
        return [TextSpanResponse.model_validate(s) for s in spans]

    # ============ Text Import Methods ============

    def import_text_content(
        self, edition_id: UUID, text: str, parse_mode: str = "simple"
    ) -> TextImportResponse:
        """Import raw text content and create document structure (MVP simplified)."""
        if not text:
            raise ValueError("Empty text content")

        nodes_created = 0
        spans_created = 0

        full_text = text

        if parse_mode == "simple":
            nodes_created, spans_created = self._parse_and_create_chapters(
                edition_id, full_text
            )
        else:
            # fallback to single document
            node_data = DocumentNodeCreate(
                edition_id=edition_id,
                parent_id=None,
                node_type="document",
                sort_index=0,
                depth=0,
                title="Full Document",
                raw_text=full_text,
                path="0000",
            )
            self.create_node(node_data)
            nodes_created = 1

        # Update edition statistics
        edition = self.db.query(Edition).filter(Edition.id == edition_id).first()
        if edition:
            edition.word_count = len(full_text.split())
            self.db.commit()

        return TextImportResponse(
            edition_id=edition_id,
            nodes_created=nodes_created,
            spans_created=spans_created,
            total_chars=len(full_text),
            total_words=len(full_text.split()),
            status="completed",
        )

    def import_text_file(self, import_request: TextImportRequest) -> TextImportResponse:
        """Import text file and create document structure"""
        edition = (
            self.db.query(Edition)
            .filter(Edition.id == import_request.edition_id)
            .first()
        )
        if not edition:
            raise ValueError(f"Edition {import_request.edition_id} not found")

        # Read file
        try:
            with open(
                import_request.file_path, "r", encoding=import_request.encoding
            ) as f:
                full_text = f.read()
        except Exception as e:
            raise ValueError(f"Failed to read file: {str(e)}")

        # Parse chapters if requested
        nodes_created = 0
        spans_created = 0

        if import_request.parse_chapters:
            nodes_created, spans_created = self._parse_and_create_chapters(
                edition_id=import_request.edition_id, full_text=full_text
            )
        else:
            # Create single document node
            node_data = DocumentNodeCreate(
                edition_id=import_request.edition_id,
                parent_id=None,
                node_type="document",
                sort_index=0,
                depth=0,
                title="Full Document",
                raw_text=full_text,
                path="0000",
            )
            self.create_node(node_data)
            nodes_created = 1

        # Update edition statistics
        edition.word_count = len(full_text.split())
        self.db.commit()

        return TextImportResponse(
            edition_id=import_request.edition_id,
            nodes_created=nodes_created,
            spans_created=spans_created,
            total_chars=len(full_text),
            total_words=len(full_text.split()),
            status="completed",
        )

    def _parse_and_create_chapters(
        self, edition_id: UUID, full_text: str
    ) -> Tuple[int, int]:
        """Parse text into chapters and create nodes"""
        # Simple chapter detection using common patterns
        chapter_pattern = re.compile(
            r"(?:^|\n)(?:第[一二三四五六七八九十百千\d]+[章回节]|Chapter\s+\d+|CHAPTER\s+\d+)[：:\s]*([^\n]*)",
            re.MULTILINE | re.IGNORECASE,
        )

        chapters = list(chapter_pattern.finditer(full_text))
        nodes_created = 0
        spans_created = 0

        if not chapters:
            # No chapters found, create paragraphs instead
            return self._parse_and_create_paragraphs(edition_id, full_text)

        for idx, match in enumerate(chapters):
            chapter_title = match.group(0).strip()
            chapter_start = match.start()
            chapter_end = (
                chapters[idx + 1].start() if idx + 1 < len(chapters) else len(full_text)
            )
            chapter_text = full_text[chapter_start:chapter_end].strip()

            # Create chapter node
            path = f"{idx:04d}"
            node_data = DocumentNodeCreate(
                edition_id=edition_id,
                parent_id=None,
                node_type="chapter",
                sort_index=idx,
                depth=0,
                title=chapter_title,
                raw_text=chapter_text,
                path=path,
            )
            node_response = self.create_node(node_data)
            nodes_created += 1

            # Create paragraph spans
            paragraphs = [p.strip() for p in chapter_text.split("\n\n") if p.strip()]
            char_offset = 0
            for para_idx, para_text in enumerate(paragraphs):
                start_pos = chapter_text.find(para_text, char_offset)
                if start_pos == -1:
                    continue
                end_pos = start_pos + len(para_text)

                span_data = TextSpanCreate(
                    node_id=node_response.id,
                    span_type="paragraph",
                    start_char=start_pos,
                    end_char=end_pos,
                    text_snippet=para_text[:200],  # Store first 200 chars
                )
                self.create_span(span_data)
                spans_created += 1
                char_offset = end_pos

        return nodes_created, spans_created

    def _parse_and_create_paragraphs(
        self, edition_id: UUID, full_text: str
    ) -> Tuple[int, int]:
        """Parse text into paragraphs when no chapters are detected"""
        # Create a root document node
        root_data = DocumentNodeCreate(
            edition_id=edition_id,
            parent_id=None,
            node_type="document",
            sort_index=0,
            depth=0,
            title="Full Text",
            raw_text=full_text,
            path="0000",
        )
        root_response = self.create_node(root_data)
        nodes_created = 1
        spans_created = 0

        # Split into paragraphs
        paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
        char_offset = 0

        for para_idx, para_text in enumerate(paragraphs):
            start_pos = full_text.find(para_text, char_offset)
            if start_pos == -1:
                continue
            end_pos = start_pos + len(para_text)

            span_data = TextSpanCreate(
                node_id=root_response.id,
                span_type="paragraph",
                start_char=start_pos,
                end_char=end_pos,
                text_snippet=para_text[:200],
            )
            self.create_span(span_data)
            spans_created += 1
            char_offset = end_pos

        return nodes_created, spans_created

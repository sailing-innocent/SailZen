# -*- coding: utf-8 -*-
# @file work.py
# @brief ORM models for works, editions, and universes
# @author sailing-innocent
# @date 2025-04-21

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    Text,
    TIMESTAMP,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from server.data.orm import ORMBase


class Universe(ORMBase):
    __tablename__ = "universes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    memberships = relationship(
        "UniverseMembership", back_populates="universe", cascade="all, delete-orphan"
    )


class Work(ORMBase):
    __tablename__ = "works"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    original_title = Column(String)
    author = Column(String)
    language_primary = Column(String, nullable=False)
    work_type = Column(String, default="web_novel")
    status = Column(String, default="ongoing")  # ongoing | completed | hiatus
    synopsis = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    memberships = relationship(
        "UniverseMembership", back_populates="work", cascade="all, delete-orphan"
    )
    aliases = relationship(
        "WorkAlias", back_populates="work", cascade="all, delete-orphan"
    )
    editions = relationship(
        "Edition", back_populates="work", cascade="all, delete-orphan"
    )
    narrative_events = relationship(
        "NarrativeEvent", back_populates="work", cascade="all, delete-orphan"
    )
    knowledge_collections = relationship(
        "KnowledgeCollection", back_populates="work", cascade="all, delete-orphan"
    )


class UniverseMembership(ORMBase):
    __tablename__ = "universe_memberships"

    universe_id = Column(
        UUID(as_uuid=True),
        ForeignKey("universes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    work_id = Column(
        UUID(as_uuid=True), ForeignKey("works.id", ondelete="CASCADE"), primary_key=True
    )
    membership_role = Column(String, default="primary")  # primary | side_story | cameo
    notes = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    universe = relationship("Universe", back_populates="memberships")
    work = relationship("Work", back_populates="memberships")


class WorkAlias(ORMBase):
    __tablename__ = "work_aliases"
    __table_args__ = (UniqueConstraint("work_id", "alias", name="_work_alias_uc"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_id = Column(
        UUID(as_uuid=True), ForeignKey("works.id", ondelete="CASCADE"), nullable=False
    )
    alias = Column(String, nullable=False)
    language = Column(String)
    alias_type = Column(String, default="title")  # title | tag | abbreviation
    is_primary = Column(Boolean, default=False)

    # Relationships
    work = relationship("Work", back_populates="aliases")


class Edition(ORMBase):
    __tablename__ = "editions"
    __table_args__ = (
        UniqueConstraint(
            "work_id", "language", "ingest_version", name="_work_lang_version_uc"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_id = Column(
        UUID(as_uuid=True), ForeignKey("works.id", ondelete="CASCADE"), nullable=False
    )
    edition_name = Column(String)
    language = Column(String, nullable=False)
    source_format = Column(String, default="txt")
    canonical = Column(Boolean, default=False)
    source_path = Column(String)
    source_checksum = Column(String)
    ingest_version = Column(Integer, default=1)
    publication_year = Column(Integer)
    word_count = Column(Integer)
    description = Column(Text)
    status = Column(String, default="draft")  # draft | active | archived
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    work = relationship("Work", back_populates="editions")
    files = relationship(
        "EditionFile", back_populates="edition", cascade="all, delete-orphan"
    )
    tags = relationship(
        "EditionTag", back_populates="edition", cascade="all, delete-orphan"
    )
    nodes = relationship(
        "DocumentNode", back_populates="edition", cascade="all, delete-orphan"
    )
    annotation_batches = relationship(
        "AnnotationBatch", back_populates="edition", cascade="all, delete-orphan"
    )
    change_sets = relationship(
        "ChangeSet", back_populates="edition", cascade="all, delete-orphan"
    )
    collab_sessions = relationship(
        "CollabSession", back_populates="edition", cascade="all, delete-orphan"
    )
    narrative_events = relationship(
        "NarrativeEvent", back_populates="edition", cascade="all, delete-orphan"
    )


class EditionFile(ORMBase):
    __tablename__ = "edition_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edition_id = Column(
        UUID(as_uuid=True),
        ForeignKey("editions.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_role = Column(String, default="source")  # source | cleaned | tokenized
    storage_uri = Column(String, nullable=False)
    checksum = Column(String)
    byte_length = Column(Integer)
    encoding = Column(String)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    edition = relationship("Edition", back_populates="files")


class EditionTag(ORMBase):
    __tablename__ = "edition_tags"

    edition_id = Column(
        UUID(as_uuid=True),
        ForeignKey("editions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag = Column(String, primary_key=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    edition = relationship("Edition", back_populates="tags")

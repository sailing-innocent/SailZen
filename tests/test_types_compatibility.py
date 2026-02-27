# -*- coding: utf-8 -*-
# @file test_types_compatibility.py
# @brief Test database type compatibility layer
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------

import pytest
from typing import Generator

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from sqlalchemy.pool import StaticPool

from sail_server.data.types import JSONB, ARRAY


class TestBase(DeclarativeBase):
    pass


class TestModel(TestBase):
    """Test model for type compatibility"""
    __tablename__ = "test_model"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    data = Column(JSONB, nullable=True)
    tags = Column(ARRAY(String), nullable=True)


@pytest.fixture(scope="function")
def sqlite_session() -> Generator[Session, None, None]:
    """Create SQLite in-memory database session"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestJSONBType:
    """Test JSONB type compatibility"""
    
    def test_jsonb_store_and_retrieve(self, sqlite_session: Session):
        """Test storing and retrieving JSON data"""
        data = {"key": "value", "nested": {"a": 1, "b": 2}}
        obj = TestModel(name="test", data=data)
        sqlite_session.add(obj)
        sqlite_session.commit()
        
        fetched = sqlite_session.query(TestModel).first()
        assert fetched is not None
        assert fetched.data == data
        assert fetched.data["key"] == "value"
        assert fetched.data["nested"]["a"] == 1
    
    def test_jsonb_null(self, sqlite_session: Session):
        """Test JSONB with NULL value"""
        obj = TestModel(name="test", data=None)
        sqlite_session.add(obj)
        sqlite_session.commit()
        
        fetched = sqlite_session.query(TestModel).first()
        assert fetched is not None
        assert fetched.data is None
    
    def test_jsonb_complex(self, sqlite_session: Session):
        """Test JSONB with complex nested data"""
        data = {
            "outputs": [
                {"type": "outline", "data": {"title": "Test"}}
            ],
            "summary": "Test summary",
            "count": 42,
            "active": True
        }
        obj = TestModel(name="complex", data=data)
        sqlite_session.add(obj)
        sqlite_session.commit()
        
        fetched = sqlite_session.query(TestModel).filter_by(name="complex").first()
        assert fetched is not None
        assert fetched.data["outputs"][0]["type"] == "outline"
        assert fetched.data["summary"] == "Test summary"


class TestARRAYType:
    """Test ARRAY type compatibility"""
    
    def test_array_store_and_retrieve(self, sqlite_session: Session):
        """Test storing and retrieving array data"""
        tags = ["tag1", "tag2", "tag3"]
        obj = TestModel(name="test", tags=tags)
        sqlite_session.add(obj)
        sqlite_session.commit()
        
        fetched = sqlite_session.query(TestModel).first()
        assert fetched is not None
        assert fetched.tags == tags
        assert len(fetched.tags) == 3
    
    def test_array_null(self, sqlite_session: Session):
        """Test ARRAY with NULL value"""
        obj = TestModel(name="test", tags=None)
        sqlite_session.add(obj)
        sqlite_session.commit()
        
        fetched = sqlite_session.query(TestModel).first()
        assert fetched is not None
        assert fetched.tags is None
    
    def test_array_empty(self, sqlite_session: Session):
        """Test ARRAY with empty list"""
        obj = TestModel(name="test", tags=[])
        sqlite_session.add(obj)
        sqlite_session.commit()
        
        fetched = sqlite_session.query(TestModel).first()
        assert fetched is not None
        assert fetched.tags == []


class TestCombinedTypes:
    """Test using both JSONB and ARRAY together"""
    
    def test_both_types_together(self, sqlite_session: Session):
        """Test using both JSONB and ARRAY in same model"""
        data = {"config": {"enabled": True}}
        tags = ["important", "test"]
        obj = TestModel(name="combined", data=data, tags=tags)
        sqlite_session.add(obj)
        sqlite_session.commit()
        
        fetched = sqlite_session.query(TestModel).first()
        assert fetched is not None
        assert fetched.data == data
        assert fetched.tags == tags

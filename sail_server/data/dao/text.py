# -*- coding: utf-8 -*-
# @file text.py
# @brief Text DAO
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
文本模块 DAO

从 sail_server/data/text.py 迁移数据访问逻辑
"""

from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.text import Work, Edition, DocumentNode, NoteItem
from sail_server.data.dao.base import BaseDAO


class WorkDAO(BaseDAO[Work]):
    """作品 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, Work)

    def get_by_slug(self, slug: str) -> Optional[Work]:
        """通过 slug 获取作品"""
        return self.db.query(Work).filter(Work.slug == slug).first()

    def get_by_author(self, author: str) -> List[Work]:
        """获取指定作者的所有作品"""
        return self.db.query(Work).filter(Work.author == author).all()

    def get_by_status(self, status: str) -> List[Work]:
        """获取指定状态的所有作品"""
        return self.db.query(Work).filter(Work.status == status).all()

    def search_by_title(self, title_pattern: str) -> List[Work]:
        """通过标题模糊搜索作品"""
        return self.db.query(Work).filter(Work.title.ilike(f"%{title_pattern}%")).all()


class EditionDAO(BaseDAO[Edition]):
    """版本 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, Edition)

    def get_by_work(self, work_id: int) -> List[Edition]:
        """获取作品的所有版本"""
        return (
            self.db.query(Edition)
            .filter(Edition.work_id == work_id)
            .order_by(Edition.created_at.desc())
            .all()
        )

    def get_canonical_by_work(self, work_id: int) -> Optional[Edition]:
        """获取作品的规范版本"""
        return (
            self.db.query(Edition)
            .filter(Edition.work_id == work_id, Edition.canonical == True)
            .first()
        )

    def get_by_status(self, status: str) -> List[Edition]:
        """获取指定状态的所有版本"""
        return self.db.query(Edition).filter(Edition.status == status).all()

    def get_by_source_checksum(self, checksum: str) -> Optional[Edition]:
        """通过源文件校验和获取版本"""
        return (
            self.db.query(Edition).filter(Edition.source_checksum == checksum).first()
        )


class DocumentNodeDAO(BaseDAO[DocumentNode]):
    """文档节点 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, DocumentNode)

    def get_by_edition(self, edition_id: int) -> List[DocumentNode]:
        """获取版本的所有文档节点"""
        return (
            self.db.query(DocumentNode)
            .filter(DocumentNode.edition_id == edition_id)
            .order_by(DocumentNode.sort_index)
            .all()
        )

    def get_by_parent(self, parent_id: int) -> List[DocumentNode]:
        """获取父节点的所有子节点"""
        return (
            self.db.query(DocumentNode)
            .filter(DocumentNode.parent_id == parent_id)
            .order_by(DocumentNode.sort_index)
            .all()
        )

    def get_by_type(self, edition_id: int, node_type: str) -> List[DocumentNode]:
        """获取指定类型的所有节点"""
        return (
            self.db.query(DocumentNode)
            .filter(
                DocumentNode.edition_id == edition_id,
                DocumentNode.node_type == node_type,
            )
            .order_by(DocumentNode.sort_index)
            .all()
        )

    def get_root_nodes(self, edition_id: int) -> List[DocumentNode]:
        """获取版本的所有根节点（无父节点）"""
        return (
            self.db.query(DocumentNode)
            .filter(
                DocumentNode.edition_id == edition_id, DocumentNode.parent_id.is_(None)
            )
            .order_by(DocumentNode.sort_index)
            .all()
        )

    def get_by_path(self, edition_id: int, path: str) -> Optional[DocumentNode]:
        """通过路径获取节点"""
        return (
            self.db.query(DocumentNode)
            .filter(DocumentNode.edition_id == edition_id, DocumentNode.path == path)
            .first()
        )

    def get_chapters(self, edition_id: int) -> List[DocumentNode]:
        """获取版本的所有章节节点"""
        return (
            self.db.query(DocumentNode)
            .filter(
                DocumentNode.edition_id == edition_id,
                DocumentNode.node_type == "chapter",
            )
            .order_by(DocumentNode.sort_index)
            .all()
        )


class NoteItemDAO(BaseDAO[NoteItem]):
    """笔记索引 DAO"""

    def __init__(self, db: Session):
        super().__init__(db, NoteItem)

    def get_by_slug(self, slug: str) -> Optional[NoteItem]:
        """通过 slug 获取笔记索引"""
        return self.db.query(NoteItem).filter(NoteItem.slug == slug).first()

    def get_by_category(
        self, category: str, skip: int = 0, limit: int = 100
    ) -> List[NoteItem]:
        """按分类获取笔记索引"""
        return (
            self.db.query(NoteItem)
            .filter(NoteItem.category == category)
            .order_by(NoteItem.updated_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_work(self, work_id: int, skip: int = 0, limit: int = 100) -> List[NoteItem]:
        """获取关联作品的所有笔记索引"""
        return (
            self.db.query(NoteItem)
            .filter(NoteItem.work_id == work_id)
            .order_by(NoteItem.updated_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_edition(
        self, edition_id: int, skip: int = 0, limit: int = 100
    ) -> List[NoteItem]:
        """获取关联版本的所有笔记索引"""
        return (
            self.db.query(NoteItem)
            .filter(NoteItem.edition_id == edition_id)
            .order_by(NoteItem.updated_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_file(self, setting_file: str) -> Optional[NoteItem]:
        """通过文件路径获取笔记索引"""
        return self.db.query(NoteItem).filter(NoteItem.setting_file == setting_file).first()

    def filter_notes(
        self,
        category: Optional[str] = None,
        work_id: Optional[int] = None,
        edition_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[NoteItem]:
        """多条件过滤笔记索引"""
        query = self.db.query(NoteItem)
        if category is not None:
            query = query.filter(NoteItem.category == category)
        if work_id is not None:
            query = query.filter(NoteItem.work_id == work_id)
        if edition_id is not None:
            query = query.filter(NoteItem.edition_id == edition_id)
        return (
            query.order_by(NoteItem.updated_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

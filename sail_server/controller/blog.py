# -*- coding: utf-8 -*-
# @file blog.py
# @brief Blog Controller - Markdown report upload / preview / download / delete
# @author sailing-innocent
# @date 2026-05-05
# @version 1.0
# ---------------------------------
"""
博客（Markdown 快速审阅）控制器。

使用场景：运行在开发机/服务器上的 agent 产出一个 Markdown 报告后，
通过规范的上传 API 把文件传到云端，返回预览页面地址；
用户在前端（手机/桌面）审阅后可以直接删除或下载留档。

设计要点：
- 仅处理文本类 Markdown 文件（必须是合法 UTF-8 文本）
- 内部存储文件名规范化（时间戳 + 内容哈希 + uuid，固定 .md 后缀），
  原始文件名保留在元数据中，用于展示与下载
- 元数据保存在存储目录下的 .metadata.json
- 所有按文件名访问的端点都做严格的路径校验，杜绝路径遍历
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from typing import List

from litestar import Controller, delete, get, post
from litestar.datastructures import UploadFile
from litestar.exceptions import HTTPException, NotFoundException
from litestar.params import Body
from litestar.response import File
from pydantic import BaseModel, Field

from sail_server.config.paths import BLOG_STORAGE_DIR

STORAGE_DIR = BLOG_STORAGE_DIR
METADATA_FILE_NAME = ".metadata.json"
MAX_FILE_SIZE = 10485760  # 10MB

# 内部存储文件名格式: 20260505_120000_ab12cd34_e5f6a7b8.md
STORAGE_NAME_PATTERN = re.compile(r"^\d{8}_\d{6}_[0-9a-f]{8}_[0-9a-f]{8}\.md$")

# 从 Markdown 正文中提取标题（第一个 # 级标题）
TITLE_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)


def _metadata_file() -> "os.PathLike[str]":
    return STORAGE_DIR / METADATA_FILE_NAME


def ensure_storage_dir():
    """确保存储目录存在"""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def load_metadata() -> dict:
    """加载元数据文件"""
    meta_file = _metadata_file()
    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_metadata(metadata: dict):
    """保存元数据文件"""
    ensure_storage_dir()
    with open(_metadata_file(), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def add_file_mapping(storage_name: str, original_name: str, title: str | None):
    """添加文件名映射"""
    metadata = load_metadata()
    metadata[storage_name] = {
        "original_name": original_name,
        "title": title,
        "uploaded_at": datetime.now().isoformat(),
    }
    save_metadata(metadata)


def get_file_mapping(storage_name: str) -> dict | None:
    """获取单个文件的元数据映射"""
    return load_metadata().get(storage_name)


def remove_file_mapping(storage_name: str):
    """删除文件名映射"""
    metadata = load_metadata()
    if storage_name in metadata:
        del metadata[storage_name]
        save_metadata(metadata)


def extract_title(content: str, fallback: str) -> str:
    """从 Markdown 内容中提取第一个标题作为文章标题"""
    match = TITLE_PATTERN.search(content)
    if match:
        title = match.group(1).strip()
        if title:
            return title[:200]
    return fallback


def validate_storage_name(filename: str) -> str:
    """校验内部存储文件名，防止路径遍历；返回文件名"""
    if not STORAGE_NAME_PATTERN.match(filename):
        raise NotFoundException(detail=f"文章不存在: {filename}")
    return filename


def get_article_info(filename: str) -> dict | None:
    """获取文章信息（不存在返回 None）"""
    if not STORAGE_NAME_PATTERN.match(filename):
        return None
    file_path = STORAGE_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        return None
    stat = file_path.stat()
    mapping = get_file_mapping(filename) or {}
    original_name = mapping.get("original_name") or filename
    title = mapping.get("title") or original_name
    return {
        "filename": filename,
        "original_name": original_name,
        "title": title,
        "size": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


# ============================================================================
# Request/Response Models
# ============================================================================


class BlogUploadResponse(BaseModel):
    """文章上传响应"""

    filename: str = Field(description="内部存储文件名")
    original_name: str = Field(description="原始文件名")
    title: str = Field(description="文章标题")
    size: int = Field(description="文件大小(字节)")
    preview_url: str = Field(description="预览页面地址")
    message: str = Field(default="上传成功")


class BlogArticleInfo(BaseModel):
    """文章信息"""

    filename: str = Field(description="内部存储文件名")
    original_name: str = Field(description="原始文件名")
    title: str = Field(description="文章标题")
    size: int = Field(description="文件大小(字节)")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


class BlogListResponse(BaseModel):
    """文章列表响应"""

    articles: List[BlogArticleInfo]
    total: int = Field(description="文章总数")


class BlogDeleteResponse(BaseModel):
    """文章删除响应"""

    filename: str = Field(description="删除的文章文件名")
    message: str = Field(default="删除成功")


class BlogContentResponse(BaseModel):
    """文章内容响应"""

    filename: str = Field(description="内部存储文件名")
    original_name: str = Field(description="原始文件名")
    title: str = Field(description="文章标题")
    content: str = Field(description="Markdown 原文")
    size: int = Field(description="文件大小(字节)")


# ============================================================================
# Controller
# ============================================================================


class BlogController(Controller):
    """博客控制器 - Markdown 报告的快速上传、审阅与清理"""

    path = "/"

    @post(path="/upload")
    async def upload_article(
        self, data: UploadFile = Body(media_type="multipart/form-data")
    ) -> BlogUploadResponse:
        """上传 Markdown 文章 - 限制10MB以内的 UTF-8 文本文件"""
        ensure_storage_dir()
        content = await data.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"文件大小超过限制，最大允许 {MAX_FILE_SIZE} 字节",
            )
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="文件不是有效的UTF-8文本，仅支持 Markdown 文本文件")

        original_name = data.filename or "unnamed.md"
        title = extract_title(text, original_name)
        file_hash = hashlib.md5(content).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{timestamp}_{file_hash}_{uuid.uuid4().hex[:8]}.md"

        file_path = STORAGE_DIR / safe_name
        with open(file_path, "wb") as f:
            f.write(content)
        add_file_mapping(safe_name, original_name, title)

        return BlogUploadResponse(
            filename=safe_name,
            original_name=original_name,
            title=title,
            size=len(content),
            preview_url=f"/blog?content={safe_name}",
            message="上传成功",
        )

    @get(path="/list")
    async def list_articles(self) -> BlogListResponse:
        """获取所有文章列表（按创建时间倒序）"""
        ensure_storage_dir()
        articles = []
        for filename in sorted(os.listdir(STORAGE_DIR)):
            if filename.startswith("."):
                continue
            info = get_article_info(filename)
            if info:
                articles.append(BlogArticleInfo(**info))
        articles.sort(key=lambda x: x.created_at, reverse=True)
        return BlogListResponse(articles=articles, total=len(articles))

    @get(path="/content/{filename:str}")
    async def get_article_content(self, filename: str) -> BlogContentResponse:
        """获取文章 Markdown 原文（用于前端渲染）"""
        filename = validate_storage_name(filename)
        file_path = STORAGE_DIR / filename
        if not file_path.exists():
            raise NotFoundException(detail=f"文章不存在: {filename}")
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="文章不是有效的UTF-8文本")
        mapping = get_file_mapping(filename) or {}
        original_name = mapping.get("original_name") or filename
        title = mapping.get("title") or original_name
        return BlogContentResponse(
            filename=filename,
            original_name=original_name,
            title=title,
            content=content,
            size=len(content.encode("utf-8")),
        )

    @get(path="/download/{filename:str}")
    async def download_article(self, filename: str) -> File:
        """下载 Markdown 原文件"""
        filename = validate_storage_name(filename)
        file_path = STORAGE_DIR / filename
        if not file_path.exists():
            raise NotFoundException(detail=f"文章不存在: {filename}")
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="无效的文件路径")
        mapping = get_file_mapping(filename) or {}
        original_name = mapping.get("original_name") or filename
        return File(
            path=str(file_path),
            filename=original_name,
            media_type="text/markdown; charset=utf-8",
        )

    @delete(path="/delete/{filename:str}", status_code=200)
    async def delete_article(self, filename: str) -> BlogDeleteResponse:
        """删除文章"""
        filename = validate_storage_name(filename)
        file_path = STORAGE_DIR / filename
        if not file_path.exists():
            raise NotFoundException(detail=f"文章不存在: {filename}")
        try:
            file_path.unlink()
            remove_file_mapping(filename)
            return BlogDeleteResponse(filename=filename, message="删除成功")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

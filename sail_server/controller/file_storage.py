# -*- coding: utf-8 -*-
# @file file_storage.py
# @brief Simple File Storage Controller with filename preservation
# @author sailing-innocent
# @date 2026-03-14
# @version 2.0
# ---------------------------------

from __future__ import annotations
from litestar import Controller, delete, get, post
from litestar.datastructures import UploadFile
from litestar.exceptions import HTTPException, NotFoundException
from litestar.response import File
from litestar.params import Body
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime
import os
import hashlib
import uuid
import json
from pathlib import Path

# 文件存储目录 - 通过统一路径配置获取
from sail_server.config.paths import FILE_STORAGE_DIR

STORAGE_DIR = FILE_STORAGE_DIR
METADATA_FILE = STORAGE_DIR / ".metadata.json"
MAX_FILE_SIZE = 10485760  # 10MB


def ensure_storage_dir():
    """确保存储目录存在"""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def load_metadata() -> dict:
    """加载元数据文件"""
    if METADATA_FILE.exists():
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_metadata(metadata: dict):
    """保存元数据文件"""
    ensure_storage_dir()
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def add_file_mapping(storage_name: str, original_name: str):
    """添加文件名映射"""
    metadata = load_metadata()
    metadata[storage_name] = {
        "original_name": original_name,
        "uploaded_at": datetime.now().isoformat(),
    }
    save_metadata(metadata)


def get_original_filename(storage_name: str) -> str | None:
    """获取原始文件名"""
    metadata = load_metadata()
    if storage_name in metadata:
        return metadata[storage_name].get("original_name")
    return None


def remove_file_mapping(storage_name: str):
    """删除文件名映射"""
    metadata = load_metadata()
    if storage_name in metadata:
        del metadata[storage_name]
        save_metadata(metadata)


def get_file_info(filename: str) -> dict | None:
    """获取文件信息"""
    file_path = STORAGE_DIR / filename
    if not file_path.exists():
        return None
    stat = file_path.stat()
    original_name = get_original_filename(filename) or filename
    return {
        "filename": filename,
        "original_name": original_name,
        "size": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


# ============================================================================
# Request/Response Models
# ============================================================================


class FileUploadResponse(BaseModel):
    """文件上传响应"""

    filename: str = Field(description="文件名")
    original_name: str = Field(description="原始文件名")
    size: int = Field(description="文件大小(字节)")
    message: str = Field(default="上传成功")


class FileInfoResponse(BaseModel):
    """文件信息响应"""

    filename: str = Field(description="文件名")
    original_name: str = Field(description="原始文件名")
    size: int = Field(description="文件大小(字节)")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


class FileListResponse(BaseModel):
    """文件列表响应"""

    files: List[FileInfoResponse]
    total: int = Field(description="文件总数")


class FileDeleteResponse(BaseModel):
    """文件删除响应"""

    filename: str = Field(description="删除的文件名")
    message: str = Field(default="删除成功")


class FileContentResponse(BaseModel):
    """文件内容响应"""

    filename: str = Field(description="文件名")
    original_name: str = Field(description="原始文件名")
    content: str = Field(description="文件内容")
    size: int = Field(description="文件大小(字节)")


# ============================================================================
# Controller
# ============================================================================


class FileStorageController(Controller):
    """文件存储控制器 - 简单文本文件上传、下载、管理"""

    path = "/"

    @post(path="/upload")
    async def upload_file(
        self, data: UploadFile = Body(media_type="multipart/form-data")
    ) -> FileUploadResponse:
        """上传文件 - 限制10MB以内的文本文件"""
        ensure_storage_dir()

        # 检查文件大小
        content = await data.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"文件大小超过限制，最大允许 {MAX_FILE_SIZE} 字节",
            )

        # 生成唯一文件名（内部存储使用）
        original_name = data.filename or "unnamed"
        file_hash = hashlib.md5(content).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{timestamp}_{file_hash}_{uuid.uuid4().hex[:8]}.txt"

        # 保存文件
        file_path = STORAGE_DIR / safe_name
        with open(file_path, "wb") as f:
            f.write(content)

        # 保存文件名映射
        add_file_mapping(safe_name, original_name)

        return FileUploadResponse(
            filename=safe_name,
            original_name=original_name,
            size=len(content),
            message="上传成功",
        )

    @get(path="/list")
    async def list_files(self) -> FileListResponse:
        """获取所有文件列表"""
        ensure_storage_dir()

        files = []
        for filename in sorted(os.listdir(STORAGE_DIR)):
            if filename.startswith("."):
                continue
            file_info = get_file_info(filename)
            if file_info:
                files.append(FileInfoResponse(**file_info))

        # 按创建时间倒序排列
        files.sort(key=lambda x: x.created_at, reverse=True)

        return FileListResponse(files=files, total=len(files))

    @get(path="/download/{filename:str}")
    async def download_file(self, filename: str) -> File:
        """下载文件"""
        file_path = STORAGE_DIR / filename

        if not file_path.exists():
            raise NotFoundException(detail=f"文件不存在: {filename}")

        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="无效的文件路径")

        # 获取原始文件名用于下载
        original_name = get_original_filename(filename) or filename

        return File(
            path=str(file_path),
            filename=original_name,
            media_type="text/plain",
        )

    @get(path="/content/{filename:str}")
    async def get_file_content(self, filename: str) -> FileContentResponse:
        """获取文件内容（用于前端预览）"""
        file_path = STORAGE_DIR / filename

        if not file_path.exists():
            raise NotFoundException(detail=f"文件不存在: {filename}")

        try:
            content = file_path.read_text(encoding="utf-8")
            original_name = get_original_filename(filename) or filename
            return FileContentResponse(
                filename=filename,
                original_name=original_name,
                content=content,
                size=len(content.encode("utf-8")),
            )
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="文件不是有效的UTF-8文本")

    @delete(path="/delete/{filename:str}", status_code=200)
    async def delete_file(self, filename: str) -> FileDeleteResponse:
        """删除文件"""
        file_path = STORAGE_DIR / filename

        if not file_path.exists():
            raise NotFoundException(detail=f"文件不存在: {filename}")

        try:
            file_path.unlink()
            remove_file_mapping(filename)
            return FileDeleteResponse(filename=filename, message="删除成功")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

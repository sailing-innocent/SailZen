# -*- coding: utf-8 -*-
# @file temp_file_manager.py
# @brief 临时文件管理器
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------
"""
临时文件上传和管理
支持大文件存储、自动清理、文件验证
"""

import os
import uuid
import shutil
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# 常量定义
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
ALLOWED_EXTENSIONS = {'.txt', '.md', '.text'}
TEMP_DIR = Path("/tmp/sailzen_uploads")
CLEANUP_SUCCESS_HOURS = 24  # 成功后24小时清理
CLEANUP_FAILED_HOURS = 168  # 失败后7天清理（保留用于调试）


@dataclass
class FileUploadInfo:
    """文件上传信息"""
    file_id: str
    original_name: str
    stored_path: Path
    file_size: int
    checksum: str
    encoding: Optional[str] = None
    uploaded_at: datetime = None
    
    def __post_init__(self):
        if self.uploaded_at is None:
            self.uploaded_at = datetime.utcnow()


class TempFileManager:
    """临时文件管理器"""
    
    def __init__(self, temp_dir: Optional[Path] = None):
        """
        Args:
            temp_dir: 临时文件目录，默认使用系统临时目录
        """
        self.temp_dir = temp_dir or TEMP_DIR
        self._ensure_temp_dir()
        self._uploads: Dict[str, FileUploadInfo] = {}
    
    def _ensure_temp_dir(self):
        """确保临时目录存在"""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Temp file directory: {self.temp_dir}")
    
    def validate_file(self, filename: str, file_size: int) -> Tuple[bool, Optional[str]]:
        """验证文件
        
        Args:
            filename: 文件名
            file_size: 文件大小（字节）
            
        Returns:
            (是否有效, 错误信息)
        """
        # 检查文件大小
        if file_size > MAX_FILE_SIZE:
            max_mb = MAX_FILE_SIZE / (1024 * 1024)
            return False, f"File too large (max {max_mb:.0f}MB)"
        
        if file_size == 0:
            return False, "File is empty"
        
        # 检查文件扩展名
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            allowed = ', '.join(ALLOWED_EXTENSIONS)
            return False, f"Invalid file type. Allowed: {allowed}"
        
        return True, None
    
    def save_upload(
        self,
        file_data: bytes,
        original_name: str,
        encoding: Optional[str] = None
    ) -> FileUploadInfo:
        """保存上传的文件
        
        Args:
            file_data: 文件数据
            original_name: 原始文件名
            encoding: 检测到的编码
            
        Returns:
            文件上传信息
        """
        # 生成唯一ID
        file_id = str(uuid.uuid4())
        
        # 计算校验和
        checksum = hashlib.sha256(file_data).hexdigest()[:16]
        
        # 构建存储路径
        safe_name = Path(original_name).name
        stored_name = f"{file_id}_{safe_name}"
        stored_path = self.temp_dir / stored_name
        
        # 保存文件
        with open(stored_path, 'wb') as f:
            f.write(file_data)
        
        # 创建信息对象
        info = FileUploadInfo(
            file_id=file_id,
            original_name=original_name,
            stored_path=stored_path,
            file_size=len(file_data),
            checksum=checksum,
            encoding=encoding
        )
        
        self._uploads[file_id] = info
        
        logger.info(
            f"File saved: {original_name} -> {stored_path} "
            f"({len(file_data)} bytes, checksum={checksum})"
        )
        
        return info
    
    def get_file(self, file_id: str) -> Optional[FileUploadInfo]:
        """获取文件信息
        
        Args:
            file_id: 文件ID
            
        Returns:
            文件信息，不存在则返回 None
        """
        # 首先从内存缓存查找
        if file_id in self._uploads:
            return self._uploads[file_id]
        
        # 从磁盘查找
        for file_path in self.temp_dir.glob(f"{file_id}_*"):
            if file_path.is_file():
                # 重建信息对象
                stat = file_path.stat()
                info = FileUploadInfo(
                    file_id=file_id,
                    original_name=file_path.name[len(file_id)+1:],
                    stored_path=file_path,
                    file_size=stat.st_size,
                    checksum="",
                    uploaded_at=datetime.fromtimestamp(stat.st_mtime)
                )
                self._uploads[file_id] = info
                return info
        
        return None
    
    def read_file(self, file_id: str, encoding: Optional[str] = None) -> Optional[str]:
        """读取文件内容
        
        Args:
            file_id: 文件ID
            encoding: 编码，None则自动检测
            
        Returns:
            文件内容文本
        """
        info = self.get_file(file_id)
        if not info:
            return None
        
        # 读取字节数据
        with open(info.stored_path, 'rb') as f:
            raw_data = f.read()
        
        # 检测编码并解码
        if encoding:
            return raw_data.decode(encoding)
        
        # 使用编码检测器
        from sail_server.utils.text_import.encoding_detector import decode_bytes
        text, detected_encoding = decode_bytes(raw_data)
        info.encoding = detected_encoding
        
        return text
    
    def delete_file(self, file_id: str) -> bool:
        """删除文件
        
        Args:
            file_id: 文件ID
            
        Returns:
            是否成功删除
        """
        info = self.get_file(file_id)
        if not info:
            return False
        
        try:
            if info.stored_path.exists():
                info.stored_path.unlink()
                logger.info(f"File deleted: {info.stored_path}")
            
            # 从缓存移除
            self._uploads.pop(file_id, None)
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False
    
    def cleanup_old_files(self, max_age_hours: Optional[int] = None) -> int:
        """清理过期文件
        
        Args:
            max_age_hours: 最大保留时间（小时），None则使用默认值
            
        Returns:
            清理的文件数量
        """
        if max_age_hours is None:
            max_age_hours = CLEANUP_SUCCESS_HOURS
        
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        count = 0
        
        for file_path in self.temp_dir.iterdir():
            if not file_path.is_file():
                continue
            
            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff:
                    file_path.unlink()
                    count += 1
                    logger.debug(f"Cleaned up old file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {file_path}: {e}")
        
        if count > 0:
            logger.info(f"Cleaned up {count} old files")
        
        return count
    
    def get_storage_stats(self) -> Dict:
        """获取存储统计信息
        
        Returns:
            统计信息字典
        """
        total_size = 0
        file_count = 0
        oldest_file = None
        newest_file = None
        
        for file_path in self.temp_dir.iterdir():
            if not file_path.is_file():
                continue
            
            stat = file_path.stat()
            total_size += stat.st_size
            file_count += 1
            mtime = datetime.fromtimestamp(stat.st_mtime)
            
            if oldest_file is None or mtime < oldest_file:
                oldest_file = mtime
            if newest_file is None or mtime > newest_file:
                newest_file = mtime
        
        return {
            "file_count": file_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest_file": oldest_file.isoformat() if oldest_file else None,
            "newest_file": newest_file.isoformat() if newest_file else None,
            "temp_dir": str(self.temp_dir)
        }


# 全局实例
_temp_file_manager: Optional[TempFileManager] = None


def get_temp_file_manager() -> TempFileManager:
    """获取全局临时文件管理器实例"""
    global _temp_file_manager
    if _temp_file_manager is None:
        _temp_file_manager = TempFileManager()
    return _temp_file_manager

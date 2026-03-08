# -*- coding: utf-8 -*-
# @file encoding_detector.py
# @brief 文本编码检测工具
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------
"""
文本编码检测和转换工具
支持常见中文编码：UTF-8, GBK, GB2312, GB18030, Big5
"""

import logging
from typing import Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EncodingConfidence(Enum):
    """编码检测置信度"""
    HIGH = "high"       # >= 0.9
    MEDIUM = "medium"   # >= 0.7
    LOW = "low"         # < 0.7


@dataclass
class EncodingResult:
    """编码检测结果"""
    encoding: str
    confidence: float
    language: Optional[str] = None
    
    @property
    def confidence_level(self) -> EncodingConfidence:
        if self.confidence >= 0.9:
            return EncodingConfidence.HIGH
        elif self.confidence >= 0.7:
            return EncodingConfidence.MEDIUM
        else:
            return EncodingConfidence.LOW


class EncodingDetector:
    """编码检测器"""
    
    # 支持的编码列表（按优先级排序）
    SUPPORTED_ENCODINGS = [
        'utf-8',
        'utf-8-sig',  # 带 BOM 的 UTF-8
        'gbk',
        'gb2312',
        'gb18030',
        'big5',
        'shift_jis',
        'euc-jp',
        'euc-kr',
        'latin1',
    ]
    
    def __init__(self):
        self._try_import_chardet()
    
    def _try_import_chardet(self):
        """尝试导入 chardet 库"""
        try:
            import chardet
            self.chardet = chardet
            self.has_chardet = True
        except ImportError:
            self.chardet = None
            self.has_chardet = False
            logger.warning("chardet not installed, using fallback detection")
    
    def detect(self, raw_bytes: bytes, use_chardet: bool = True) -> EncodingResult:
        """检测编码
        
        Args:
            raw_bytes: 原始字节数据
            use_chardet: 是否使用 chardet 库
            
        Returns:
            编码检测结果
        """
        # 首先检查 BOM
        bom_encoding = self._check_bom(raw_bytes)
        if bom_encoding:
            return EncodingResult(
                encoding=bom_encoding,
                confidence=1.0,
                language=None
            )
        
        # 使用 chardet（如果可用且启用）
        if use_chardet and self.has_chardet:
            result = self._detect_with_chardet(raw_bytes)
            if result.confidence >= 0.7:
                return result
        
        # 备用检测方法
        return self._detect_fallback(raw_bytes)
    
    def _check_bom(self, raw_bytes: bytes) -> Optional[str]:
        """检查 BOM 标记"""
        boms = [
            (b'\xef\xbb\xbf', 'utf-8-sig'),      # UTF-8 BOM
            (b'\xff\xfe', 'utf-16-le'),           # UTF-16 LE
            (b'\xfe\xff', 'utf-16-be'),           # UTF-16 BE
            (b'\xff\xfe\x00\x00', 'utf-32-le'),   # UTF-32 LE
            (b'\x00\x00\xfe\xff', 'utf-32-be'),   # UTF-32 BE
        ]
        
        for bom, encoding in boms:
            if raw_bytes.startswith(bom):
                return encoding
        
        return None
    
    def _detect_with_chardet(self, raw_bytes: bytes) -> EncodingResult:
        """使用 chardet 检测"""
        # 限制检测样本大小以提高性能
        sample = raw_bytes[:100000] if len(raw_bytes) > 100000 else raw_bytes
        
        result = self.chardet.detect(sample)
        
        if result and result['encoding']:
            encoding = result['encoding'].lower()
            confidence = result.get('confidence', 0.0)
            
            # 标准化编码名称
            if encoding in ('gb2312', 'gbk', 'gb18030'):
                # 统一使用 gb18030（向下兼容）
                encoding = 'gb18030'
            
            return EncodingResult(
                encoding=encoding,
                confidence=confidence,
                language=result.get('language')
            )
        
        return EncodingResult(encoding='utf-8', confidence=0.0)
    
    def _detect_fallback(self, raw_bytes: bytes) -> EncodingResult:
        """备用检测方法（当 chardet 不可用时）"""
        # 尝试常见编码
        for encoding in self.SUPPORTED_ENCODINGS:
            try:
                decoded = raw_bytes.decode(encoding)
                # 检查解码后的文本是否合理
                if self._is_valid_text(decoded):
                    return EncodingResult(
                        encoding=encoding,
                        confidence=0.8  # 假设较高置信度
                    )
            except (UnicodeDecodeError, LookupError):
                continue
        
        # 默认返回 UTF-8
        return EncodingResult(encoding='utf-8', confidence=0.5)
    
    def _is_valid_text(self, text: str) -> bool:
        """检查文本是否有效
        
        检查标准：
        1. 不包含过多乱码字符
        2. 包含合理比例的汉字（如果是中文文本）
        """
        if not text:
            return True
        
        # 检查乱码字符比例
        garbage_chars = set('锟斤拷烫屯臺')
        garbage_count = sum(1 for c in text if c in garbage_chars)
        garbage_ratio = garbage_count / len(text) if text else 0
        
        if garbage_ratio > 0.01:  # 乱码字符超过 1%
            return False
        
        # 检查替换字符
        replacement_ratio = text.count('\ufffd') / len(text) if text else 0
        if replacement_ratio > 0.01:  # 替换字符超过 1%
            return False
        
        return True
    
    def decode(self, raw_bytes: bytes, encoding: Optional[str] = None) -> Tuple[str, str]:
        """解码字节数据
        
        Args:
            raw_bytes: 原始字节数据
            encoding: 指定编码（None则自动检测）
            
        Returns:
            (解码后的文本, 实际使用的编码)
        """
        if encoding:
            # 使用指定编码
            try:
                text = raw_bytes.decode(encoding)
                return text, encoding
            except UnicodeDecodeError as e:
                logger.warning(f"Failed to decode with {encoding}: {e}")
                # 回退到自动检测
        
        # 自动检测并解码
        result = self.detect(raw_bytes)
        detected_encoding = result.encoding
        
        try:
            text = raw_bytes.decode(detected_encoding)
            return text, detected_encoding
        except UnicodeDecodeError as e:
            logger.error(f"Failed to decode with detected encoding {detected_encoding}: {e}")
            # 最后尝试使用 errors='replace'
            text = raw_bytes.decode(detected_encoding, errors='replace')
            return text, detected_encoding


def detect_encoding(raw_bytes: bytes) -> EncodingResult:
    """便捷函数：检测编码
    
    Args:
        raw_bytes: 原始字节数据
        
    Returns:
        编码检测结果
    """
    detector = EncodingDetector()
    return detector.detect(raw_bytes)


def decode_bytes(raw_bytes: bytes, encoding: Optional[str] = None) -> Tuple[str, str]:
    """便捷函数：解码字节数据
    
    Args:
        raw_bytes: 原始字节数据
        encoding: 指定编码
        
    Returns:
        (解码后的文本, 实际使用的编码)
    """
    detector = EncodingDetector()
    return detector.decode(raw_bytes, encoding)

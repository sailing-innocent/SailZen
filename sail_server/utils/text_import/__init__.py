# -*- coding: utf-8 -*-
# @file __init__.py
# @brief Text Import Utils - 文本导入工具包
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------
"""
SailZen 文本导入工具包

提供文本清理、编码检测、AI 章节解析等功能
"""

from sail_server.utils.text_import.chapter_types import (
    ChapterType,
    get_chapter_type_by_title,
    get_sort_order,
    should_filter_by_default,
    get_all_keywords,
    get_standard_chapter_patterns,
)

from sail_server.utils.text_import.noise_patterns import (
    NoiseCategory,
    NoisePattern,
    TextCleaner,
    clean_text,
)

from sail_server.utils.text_import.encoding_detector import (
    EncodingDetector,
    EncodingResult,
    EncodingConfidence,
    detect_encoding,
    decode_bytes,
)

from sail_server.utils.text_import.ai_chapter_parser import (
    AIChapterParser,
    ParsedChapter,
    ParseResult,
    parse_chapters,
)

from sail_server.utils.text_import.temp_file_manager import (
    TempFileManager,
    FileUploadInfo,
    get_temp_file_manager,
)

from sail_server.utils.text_import.text_import_task import (
    TextImportTaskHandler,
    ImportStage,
    ImportProgress,
    ImportResult,
    execute_text_import_task,
)

from sail_server.utils.text_import.import_websocket_handler import (
    ImportWebSocketNotifier,
    ImportWebSocketHandler,
    create_import_notifier,
)

__all__ = [
    # 章节类型
    "ChapterType",
    "get_chapter_type_by_title",
    "get_sort_order",
    "should_filter_by_default",
    "get_all_keywords",
    "get_standard_chapter_patterns",
    
    # 噪音清理
    "NoiseCategory",
    "NoisePattern",
    "TextCleaner",
    "clean_text",
    
    # 编码检测
    "EncodingDetector",
    "EncodingResult",
    "EncodingConfidence",
    "detect_encoding",
    "decode_bytes",
    
    # AI 章节解析
    "AIChapterParser",
    "ParsedChapter",
    "ParseResult",
    "parse_chapters",
    
    # 临时文件管理
    "TempFileManager",
    "FileUploadInfo",
    "get_temp_file_manager",
    
    # 文本导入任务
    "TextImportTaskHandler",
    "ImportStage",
    "ImportProgress",
    "ImportResult",
    "execute_text_import_task",
]

__version__ = "1.0.0"

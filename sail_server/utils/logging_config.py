# -*- coding: utf-8 -*-
# @file logging_config.py
# @brief Comprehensive Logging Configuration for SailZen
# @author sailing-innocent
# @date 2025-02-28
# @version 1.0
# ---------------------------------
#
# 统一的日志配置体系，支持多级别、多目标的日志记录
#
# 环境变量:
#   LOG_LEVEL          - 全局日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
#   LOG_MODE           - 日志模式 (dev, prod, debug)
#   LOG_DIR            - 日志目录 (默认: logs)
#   LLM_DEBUG          - 启用 LLM 详细调试 (true/false)
#   API_DEBUG          - 启用 API 请求/响应日志 (true/false)
#   DB_DEBUG           - 启用数据库查询日志 (true/false)

import os
import sys
import json
import logging
import logging.handlers
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


# ============================================================================
# 日志级别映射
# ============================================================================

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


# ============================================================================
# 颜色格式化器 (用于控制台)
# ============================================================================

class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""
    
    COLORS = {
        "DEBUG": "\033[36m",      # 青色
        "INFO": "\033[32m",       # 绿色
        "WARNING": "\033[33m",    # 黄色
        "ERROR": "\033[31m",      # 红色
        "CRITICAL": "\033[35m",   # 紫色
        "RESET": "\033[0m",       # 重置
    }
    
    def __init__(self, fmt: str, use_colors: bool = True):
        super().__init__(fmt)
        self.use_colors = use_colors and sys.platform != "win32"
    
    def format(self, record: logging.LogRecord) -> str:
        if self.use_colors:
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        return super().format(record)


# ============================================================================
# JSON 格式化器 (用于结构化日志)
# ============================================================================

class JsonFormatter(logging.Formatter):
    """JSON 格式日志格式化器，便于日志分析"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加额外字段
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


# ============================================================================
# 上下文日志过滤器
# ============================================================================

class ContextFilter(logging.Filter):
    """添加上下文信息到日志记录"""
    
    def __init__(self, context: Dict[str, Any] = None):
        super().__init__()
        self.context = context or {}
    
    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in self.context.items():
            setattr(record, key, value)
        return True


# ============================================================================
# 日志配置管理器
# ============================================================================

class LoggingManager:
    """统一的日志配置管理器"""
    
    def __init__(self):
        self.log_dir = Path(os.getenv("LOG_DIR", "logs"))
        self.log_mode = os.getenv("LOG_MODE", "prod")
        self.log_level = LOG_LEVELS.get(os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
        self.handlers: List[logging.Handler] = []
        
        # 确保日志目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def setup(self) -> logging.Logger:
        """设置完整的日志体系"""
        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()
        
        # 根据模式配置
        if self.log_mode == "debug":
            self._setup_debug_mode(root_logger)
        elif self.log_mode == "dev":
            self._setup_dev_mode(root_logger)
        else:  # prod
            self._setup_prod_mode(root_logger)
        
        # 设置第三方库日志级别
        self._set_third_party_levels()
        
        return root_logger
    
    def _setup_debug_mode(self, logger: logging.Logger):
        """调试模式: 最详细的日志，包含所有调试文件"""
        # 1. 控制台输出 (带颜色，DEBUG级别)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(ColoredFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        ))
        logger.addHandler(console_handler)
        
        # 2. 主日志文件 (JSON格式，包含所有)
        main_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "sailzen.json.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(JsonFormatter())
        logger.addHandler(main_handler)
        
        # 3. 文本日志文件 (人类可读)
        text_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "sailzen.log",
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding="utf-8",
        )
        text_handler.setLevel(logging.DEBUG)
        text_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d]\n%(message)s\n"
        ))
        logger.addHandler(text_handler)
        
        # 4. API 请求/响应日志
        if os.getenv("API_DEBUG", "true").lower() == "true":
            self._setup_api_logger()
        
        # 5. LLM 详细日志
        if os.getenv("LLM_DEBUG", "true").lower() == "true":
            self._setup_llm_logger()
        
        # 6. 数据库查询日志
        if os.getenv("DB_DEBUG", "true").lower() == "true":
            self._setup_db_logger()
        
        logger.info(f"Logging configured in DEBUG mode. Log directory: {self.log_dir}")
    
    def _setup_dev_mode(self, logger: logging.Logger):
        """开发模式: 适中的日志，便于开发调试"""
        # 1. 控制台输出 (带颜色，INFO级别)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColoredFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
        logger.addHandler(console_handler)
        
        # 2. 主日志文件
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "sailzen.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
        logger.addHandler(file_handler)
        
        # 3. 错误日志单独文件
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "error.log",
            maxBytes=5*1024*1024,
            backupCount=3,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JsonFormatter())
        logger.addHandler(error_handler)
        
        logger.info(f"Logging configured in DEV mode. Log directory: {self.log_dir}")
    
    def _setup_prod_mode(self, logger: logging.Logger):
        """生产模式: 精简日志，注重性能"""
        # 1. 控制台只输出 WARNING 及以上
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        ))
        logger.addHandler(console_handler)
        
        # 2. 主日志文件 (JSON格式)
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "sailzen.json.log",
            maxBytes=20*1024*1024,  # 20MB
            backupCount=10,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)
        
        # 3. 错误日志
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "error.log",
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JsonFormatter())
        logger.addHandler(error_handler)
    
    def _setup_api_logger(self):
        """设置 API 请求/响应日志"""
        api_logger = logging.getLogger("api_debug")
        api_logger.setLevel(logging.DEBUG)
        
        # 避免重复添加 handler
        if api_logger.handlers:
            return
        
        handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "api_requests.log",
            maxBytes=10*1024*1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s\n%(message)s\n" + "="*80
        ))
        api_logger.addHandler(handler)
    
    def _setup_llm_logger(self):
        """设置 LLM 详细日志"""
        llm_logger = logging.getLogger("llm_debug")
        llm_logger.setLevel(logging.DEBUG)
        
        # 避免重复添加 handler
        if llm_logger.handlers:
            return
        
        handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "llm_debug.log",
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s\n%(message)s\n" + "="*80
        ))
        llm_logger.addHandler(handler)
    
    def _setup_db_logger(self):
        """设置数据库查询日志"""
        db_logger = logging.getLogger("sqlalchemy.engine")
        db_logger.setLevel(logging.DEBUG)
        
        # 避免重复添加 handler
        if db_logger.handlers:
            return
        
        handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "db_queries.log",
            maxBytes=10*1024*1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(message)s"
        ))
        db_logger.addHandler(handler)
    
    def _set_third_party_levels(self):
        """设置第三方库的日志级别"""
        # 降低噪音
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        
        # 根据模式调整
        if self.log_mode == "debug":
            logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)
        else:
            logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# ============================================================================
# 便捷函数
# ============================================================================

def setup_logging() -> logging.Logger:
    """快速设置日志"""
    manager = LoggingManager()
    return manager.setup()


def get_logger(name: str) -> logging.Logger:
    """获取命名日志记录器"""
    return logging.getLogger(name)


def log_api_request(method: str, path: str, body: Any = None, **kwargs):
    """记录 API 请求"""
    if os.getenv("API_DEBUG", "false").lower() != "true":
        return
    
    logger = logging.getLogger("api_debug")
    data = {
        "type": "request",
        "method": method,
        "path": path,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if body:
        data["body"] = str(body)[:1000]
    data.update(kwargs)
    logger.info(json.dumps(data, indent=2, ensure_ascii=False))


def log_api_response(path: str, status: int, duration: float, body: Any = None, **kwargs):
    """记录 API 响应"""
    if os.getenv("API_DEBUG", "false").lower() != "true":
        return
    
    logger = logging.getLogger("api_debug")
    data = {
        "type": "response",
        "path": path,
        "status": status,
        "duration_ms": round(duration * 1000, 2),
        "timestamp": datetime.utcnow().isoformat(),
    }
    if body:
        data["body"] = str(body)[:1000]
    data.update(kwargs)
    logger.info(json.dumps(data, indent=2, ensure_ascii=False))


# ============================================================================
# 全局初始化
# ============================================================================

# 默认初始化
setup_logging()

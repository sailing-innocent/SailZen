# -*- coding: utf-8 -*-
# @file logging_config.py
# @brief Simple Logging Configuration for SailZen
# @author sailing-innocent
# @date 2025-03-02
# @version 3.0
# ---------------------------------
#
# 简化的日志配置 - 根据环境变量控制日志级别
# - 默认: 只保存 INFO 级别以上的日志到文件
# - --dev 启动: 使用 .env.dev 配置，通常是 DEBUG 级别
# - --prod 启动: 使用 .env.prod 配置，通常是 INFO 或 WARNING 级别

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Optional


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
        super().__init__(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        self.use_colors = use_colors
    
    def format(self, record: logging.LogRecord) -> str:
        if self.use_colors and sys.platform == "win32":
            os.system("color >nul 2>&1")  # 启用 Windows ANSI 支持
        # 保存原始 levelname
        orig_levelname = record.levelname
        if self.use_colors:
            if orig_levelname in self.COLORS:
                record.levelname = f"{self.COLORS[orig_levelname]}{orig_levelname}{self.COLORS['RESET']}"
        result = super().format(record)
        # 恢复原始 levelname，避免影响其他 handler
        record.levelname = orig_levelname
        return result


# ============================================================================
# 日志管理器
# ============================================================================

class LoggingManager:
    """简化版日志管理器"""
    
    _instance: Optional["LoggingManager"] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.log_dir = Path(os.getenv("LOG_DIR", "logs"))
        self.log_level = self._get_log_level()
        self.console_level = self._get_console_level()
        self._initialized = True
    
    def _get_log_level(self) -> int:
        """从环境变量获取日志级别"""
        level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        return getattr(logging, level_str, logging.INFO)
    
    def _get_console_level(self) -> int:
        """获取控制台日志级别 - 与文件级别相同"""
        return self._get_log_level()
    
    def setup(self) -> logging.Logger:
        """设置日志系统"""
        # 确保日志目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # 根记录器设为 DEBUG，让 handler 控制级别
        
        # 清除所有现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()
        
        # 1. 控制台输出 - 带颜色
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.console_level)
        console_handler.setFormatter(ColoredFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
        root_logger.addHandler(console_handler)
        
        # 2. 主日志文件 - 轮转文件
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "sailzen.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d]\n%(message)s\n"
        ))
        root_logger.addHandler(file_handler)
        
        # 3. 错误日志单独文件 - ERROR 级别以上
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "error.log",
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d]\n%(message)s\n"
        ))
        root_logger.addHandler(error_handler)
        
        # 设置第三方库日志级别
        self._configure_third_party_loggers()
        
        root_logger.info(f"Logging initialized. Level: {logging.getLevelName(self.log_level)}, "
                        f"Log directory: {self.log_dir.absolute()}")
        
        return root_logger
    
    def _configure_third_party_loggers(self):
        """配置第三方库的日志级别"""
        # 从环境变量读取配置
        db_debug = os.getenv("DB_DEBUG", "false").lower() == "true"
        
        # Uvicorn - access 使用 INFO 级别以记录 API 请求
        logging.getLogger("uvicorn").setLevel(logging.INFO)
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)
        logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
        
        # HTTP 客户端
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        
        # SQLAlchemy
        if db_debug:
            logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)
        else:
            logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)


# ============================================================================
# 便捷函数
# ============================================================================

_logging_manager: Optional[LoggingManager] = None


def setup_logging() -> logging.Logger:
    """快速设置日志 - 全局单例"""
    global _logging_manager
    if _logging_manager is None:
        _logging_manager = LoggingManager()
    return _logging_manager.setup()


def get_logger(name: str) -> logging.Logger:
    """获取命名日志记录器"""
    return logging.getLogger(name)

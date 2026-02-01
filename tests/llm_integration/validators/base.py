# -*- coding: utf-8 -*-
# @file base.py
# @brief Base Validator Classes
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------
#
# 验证器基类和结果数据结构
#

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """验证级别"""
    SUCCESS = "success"     # 成功
    WARNING = "warning"     # 警告 (功能可用但有问题)
    ERROR = "error"         # 错误 (功能不可用)
    SKIPPED = "skipped"     # 跳过 (前置条件不满足)


@dataclass
class ValidationResult:
    """验证结果"""
    name: str                           # 验证项名称
    level: ValidationLevel              # 验证级别
    message: str                        # 结果消息
    details: Dict[str, Any] = field(default_factory=dict)  # 详细信息
    duration_ms: int = 0                # 执行时间(毫秒)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __str__(self) -> str:
        icon = {
            ValidationLevel.SUCCESS: "+",
            ValidationLevel.WARNING: "!",
            ValidationLevel.ERROR: "X",
            ValidationLevel.SKIPPED: "-",
        }.get(self.level, "?")
        return f"[{icon}] {self.name}: {self.message} ({self.duration_ms}ms)"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "level": self.level.value,
            "message": self.message,
            "details": self.details,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @property
    def is_success(self) -> bool:
        return self.level == ValidationLevel.SUCCESS
    
    @property
    def is_error(self) -> bool:
        return self.level == ValidationLevel.ERROR


@dataclass
class ValidationReport:
    """验证报告"""
    validator_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    results: List[ValidationResult] = field(default_factory=list)
    
    @property
    def total_count(self) -> int:
        return len(self.results)
    
    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.level == ValidationLevel.SUCCESS)
    
    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if r.level == ValidationLevel.WARNING)
    
    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.level == ValidationLevel.ERROR)
    
    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.level == ValidationLevel.SKIPPED)
    
    @property
    def total_duration_ms(self) -> int:
        return sum(r.duration_ms for r in self.results)
    
    @property
    def is_all_success(self) -> bool:
        """没有错误就算成功（警告是可接受的）"""
        return all(r.level in (ValidationLevel.SUCCESS, ValidationLevel.WARNING, ValidationLevel.SKIPPED) for r in self.results)
    
    @property
    def has_errors(self) -> bool:
        return any(r.level == ValidationLevel.ERROR for r in self.results)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "validator_name": self.validator_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "summary": {
                "total": self.total_count,
                "success": self.success_count,
                "warning": self.warning_count,
                "error": self.error_count,
                "skipped": self.skipped_count,
                "total_duration_ms": self.total_duration_ms,
            },
            "results": [r.to_dict() for r in self.results],
        }
    
    def print_summary(self, verbose: bool = False):
        """打印验证报告摘要"""
        print(f"\n{'='*60}")
        print(f"Validation Report: {self.validator_name}")
        print(f"{'='*60}")
        print(f"Total: {self.total_count} | "
              f"Success: {self.success_count} | "
              f"Warning: {self.warning_count} | "
              f"Error: {self.error_count} | "
              f"Skipped: {self.skipped_count}")
        print(f"Total Duration: {self.total_duration_ms}ms")
        print(f"{'='*60}")
        
        if verbose or self.has_errors:
            print("\nDetails:")
            for result in self.results:
                print(f"  {result}")
                if verbose and result.details:
                    for key, value in result.details.items():
                        print(f"    - {key}: {value}")
        
        status = "PASSED" if self.is_all_success else "FAILED"
        print(f"\nOverall Status: {status}")
        print(f"{'='*60}\n")


class BaseValidator(ABC):
    """验证器基类"""
    
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self.results: List[ValidationResult] = []
        self._progress_callback: Optional[Callable[[str, int, int], None]] = None
    
    def set_progress_callback(self, callback: Callable[[str, int, int], None]):
        """设置进度回调 (message, current, total)"""
        self._progress_callback = callback
    
    def _report_progress(self, message: str, current: int, total: int):
        """报告进度"""
        if self._progress_callback:
            self._progress_callback(message, current, total)
    
    def _add_result(
        self,
        name: str,
        level: ValidationLevel,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        duration_ms: int = 0
    ) -> ValidationResult:
        """添加验证结果"""
        result = ValidationResult(
            name=name,
            level=level,
            message=message,
            details=details or {},
            duration_ms=duration_ms,
        )
        self.results.append(result)
        
        # 立即输出结果 (不使用颜色代码，兼容 Windows)
        print(f"  {result}")
        
        return result
    
    def _success(
        self, 
        name: str, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        duration_ms: int = 0
    ) -> ValidationResult:
        """记录成功"""
        return self._add_result(name, ValidationLevel.SUCCESS, message, details, duration_ms)
    
    def _warning(
        self, 
        name: str, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        duration_ms: int = 0
    ) -> ValidationResult:
        """记录警告"""
        return self._add_result(name, ValidationLevel.WARNING, message, details, duration_ms)
    
    def _error(
        self, 
        name: str, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        duration_ms: int = 0
    ) -> ValidationResult:
        """记录错误"""
        return self._add_result(name, ValidationLevel.ERROR, message, details, duration_ms)
    
    def _skip(
        self, 
        name: str, 
        message: str, 
        details: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """记录跳过"""
        return self._add_result(name, ValidationLevel.SKIPPED, message, details, 0)
    
    async def _measure_async(self, coro) -> tuple:
        """测量异步操作耗时"""
        start = datetime.utcnow()
        try:
            result = await coro
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return result, duration, None
        except Exception as e:
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return None, duration, e
    
    def _measure_sync(self, func: Callable, *args, **kwargs) -> tuple:
        """测量同步操作耗时"""
        start = datetime.utcnow()
        try:
            result = func(*args, **kwargs)
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return result, duration, None
        except Exception as e:
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            return None, duration, e
    
    @abstractmethod
    async def validate(self) -> ValidationReport:
        """执行验证 (需要子类实现)"""
        pass
    
    async def run(self) -> ValidationReport:
        """运行验证并生成报告"""
        self.results = []  # 清空之前的结果
        started_at = datetime.utcnow()
        
        print(f"\n{'-'*60}")
        print(f"Running: {self.name}")
        print(f"{'-'*60}")
        
        try:
            report = await self.validate()
            report.completed_at = datetime.utcnow()
            return report
        except Exception as e:
            logger.error(f"Validator {self.name} failed: {e}")
            self._error("validator_execution", f"Validator failed: {e}")
            return ValidationReport(
                validator_name=self.name,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                results=self.results,
            )


class CompositeValidator(BaseValidator):
    """组合验证器 - 可以包含多个子验证器"""
    
    def __init__(self, name: str = "CompositeValidator"):
        super().__init__(name)
        self.validators: List[BaseValidator] = []
    
    def add_validator(self, validator: BaseValidator):
        """添加子验证器"""
        self.validators.append(validator)
        return self
    
    async def validate(self) -> ValidationReport:
        """执行所有子验证器"""
        started_at = datetime.utcnow()
        all_results = []
        
        for i, validator in enumerate(self.validators):
            self._report_progress(f"Running {validator.name}", i + 1, len(self.validators))
            
            report = await validator.run()
            all_results.extend(report.results)
        
        return ValidationReport(
            validator_name=self.name,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            results=all_results,
        )

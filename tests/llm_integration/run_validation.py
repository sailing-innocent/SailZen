#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file run_validation.py
# @brief LLM Integration Validation Runner
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------
#
# 后端 LLM 闭环验证运行器
# 使用方法:
#   python -m tests.llm_integration.run_validation [options]
#
# 或者在项目根目录:
#   python tests/llm_integration/run_validation.py [options]
#

import os
import sys
import json
import asyncio
import argparse
import logging
import signal
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 禁用 Google Gemini 的 AFC (Automatic Function Calling) 以避免卡住
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
os.environ["GOOGLE_GENAI_DISABLE_AFC"] = "True"

# 加载环境变量
from sail_server.utils.env import read_env


def setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    # 降低第三方库的日志级别
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('anthropic').setLevel(logging.WARNING)


def print_banner():
    """打印横幅"""
    print("""
================================================================
    SailZen LLM Integration Validation Framework
    Backend LLM Integration Validation
================================================================
""")


async def run_connection_validation(args):
    """运行连接验证"""
    from tests.llm_integration.validators.connection import (
        LLMConnectionValidator,
        LLMStabilityValidator,
    )
    
    providers = args.providers.split(',') if args.providers else None
    
    validator = LLMConnectionValidator(
        providers=providers,
        test_real_connection=args.real_connection,
        timeout_seconds=args.timeout,
    )
    
    report = await validator.run()
    report.print_summary(verbose=args.verbose)
    
    # 可选：运行稳定性测试
    if args.stability and args.real_connection:
        for provider in (providers or ['moonshot']):
            stability_validator = LLMStabilityValidator(
                provider=provider,
                num_iterations=args.stability_iterations,
                delay_between_calls=1.0,
            )
            stability_report = await stability_validator.run()
            stability_report.print_summary(verbose=args.verbose)
    
    return report


async def run_prompt_validation(args):
    """运行 Prompt 验证"""
    from tests.llm_integration.validators.prompt import (
        PromptValidator,
        PromptPerformanceValidator,
    )
    
    validator = PromptValidator(
        test_real_llm=args.real_llm,
        llm_provider=args.llm_provider,
    )
    
    report = await validator.run()
    report.print_summary(verbose=args.verbose)
    
    # 可选：运行性能测试
    if args.performance:
        perf_validator = PromptPerformanceValidator(iterations=100)
        perf_report = await perf_validator.run()
        perf_report.print_summary(verbose=args.verbose)
    
    return report


async def run_task_validation(args):
    """运行任务流程验证"""
    from tests.llm_integration.validators.task import (
        TaskFlowValidator,
        MinimalTaskValidator,
    )
    
    if args.minimal:
        validator = MinimalTaskValidator(
            use_real_llm=args.real_llm,
            llm_provider=args.llm_provider,
        )
    else:
        validator = TaskFlowValidator(
            use_real_llm=args.real_llm,
            llm_provider=args.llm_provider,
            cleanup_after_test=not args.no_cleanup,
        )
    
    report = await validator.run()
    report.print_summary(verbose=args.verbose)
    
    return report


async def run_all_validations(args):
    """运行所有验证"""
    from tests.llm_integration.validators.base import CompositeValidator
    from tests.llm_integration.validators.connection import LLMConnectionValidator
    from tests.llm_integration.validators.prompt import PromptValidator
    from tests.llm_integration.validators.task import MinimalTaskValidator, TaskFlowValidator
    
    composite = CompositeValidator("Full LLM Integration Validation")
    
    # 连接验证
    providers = args.providers.split(',') if args.providers else None
    composite.add_validator(LLMConnectionValidator(
        providers=providers,
        test_real_connection=args.real_connection,
        timeout_seconds=args.timeout,
    ))
    
    # Prompt 验证
    composite.add_validator(PromptValidator(
        test_real_llm=args.real_llm,
        llm_provider=args.llm_provider,
    ))
    
    # 任务流程验证
    if args.minimal:
        composite.add_validator(MinimalTaskValidator(
            use_real_llm=args.real_llm,
            llm_provider=args.llm_provider,
        ))
    else:
        composite.add_validator(TaskFlowValidator(
            use_real_llm=args.real_llm,
            llm_provider=args.llm_provider,
            cleanup_after_test=not args.no_cleanup,
        ))
    
    report = await composite.run()
    report.print_summary(verbose=args.verbose)
    
    return report


async def run_quick_check(args):
    """快速检查 - 最小化测试"""
    print("\n>> Running quick check (minimal tests, no real LLM)...")
    
    from tests.llm_integration.validators.connection import LLMConnectionValidator
    from tests.llm_integration.validators.prompt import PromptValidator
    from tests.llm_integration.validators.task import MinimalTaskValidator
    from tests.llm_integration.validators.base import CompositeValidator
    
    composite = CompositeValidator("Quick Check")
    
    # 仅检查配置，不执行真实连接
    composite.add_validator(LLMConnectionValidator(
        test_real_connection=False,
    ))
    
    # Prompt 模板验证，不调用真实 LLM
    composite.add_validator(PromptValidator(
        test_real_llm=False,
    ))
    
    # 最小任务验证
    composite.add_validator(MinimalTaskValidator(
        use_real_llm=False,
    ))
    
    report = await composite.run()
    report.print_summary(verbose=args.verbose)
    
    return report


def export_report(report, output_path: str, format: str = "json"):
    """导出报告"""
    data = report.to_dict()
    
    if format == "json":
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    elif format == "markdown":
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Validation Report: {report.validator_name}\n\n")
            f.write(f"**Started:** {report.started_at}\n")
            f.write(f"**Completed:** {report.completed_at}\n\n")
            f.write("## Summary\n\n")
            f.write(f"| Metric | Value |\n")
            f.write(f"|--------|-------|\n")
            f.write(f"| Total | {report.total_count} |\n")
            f.write(f"| Success | {report.success_count} |\n")
            f.write(f"| Warning | {report.warning_count} |\n")
            f.write(f"| Error | {report.error_count} |\n")
            f.write(f"| Skipped | {report.skipped_count} |\n")
            f.write(f"| Duration | {report.total_duration_ms}ms |\n\n")
            f.write("## Results\n\n")
            for result in report.results:
                icon = {"success": "✓", "warning": "⚠", "error": "✗", "skipped": "○"}.get(result.level.value, "?")
                f.write(f"- [{icon}] **{result.name}**: {result.message}\n")
                if result.details:
                    f.write(f"  - Details: `{json.dumps(result.details, ensure_ascii=False)}`\n")
    
    print(f"\n>> Report exported to: {output_path}")


def main():
    # 设置信号处理，确保 Ctrl+C 能正常工作
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(130))
    
    parser = argparse.ArgumentParser(
        description='SailZen LLM Integration Validation Framework',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 快速检查 (不调用真实 LLM)
  python run_validation.py quick
  
  # 验证 LLM 连接
  python run_validation.py connection --real-connection
  
  # 验证 Prompt 模板
  python run_validation.py prompt
  
  # 验证任务流程 (使用真实 LLM)
  python run_validation.py task --real-llm --llm-provider google
  
  # 运行所有验证
  python run_validation.py all --real-connection --real-llm
  
  # 导出报告
  python run_validation.py all -o report.json
"""
    )
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='Validation commands')
    
    # 公共参数
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    common_parser.add_argument('-e', '--env', default='dev', help='Environment (dev/prod)')
    common_parser.add_argument('-o', '--output', help='Export report to file')
    common_parser.add_argument('--format', choices=['json', 'markdown'], default='json', help='Export format')
    
    # LLM 相关参数
    llm_parser = argparse.ArgumentParser(add_help=False)
    llm_parser.add_argument('--real-llm', action='store_true', help='Test with real LLM API')
    llm_parser.add_argument('--llm-provider', default='moonshot',
                           choices=['openai', 'anthropic', 'google', 'moonshot', 'local'],
                           help='LLM provider to use')
    
    # quick 命令
    quick_parser = subparsers.add_parser('quick', parents=[common_parser],
                                         help='Quick check (no real LLM)')
    
    # connection 命令
    conn_parser = subparsers.add_parser('connection', parents=[common_parser],
                                        help='Validate LLM connections')
    conn_parser.add_argument('--providers', help='Comma-separated list of providers')
    conn_parser.add_argument('--real-connection', action='store_true', help='Test real connections')
    conn_parser.add_argument('--timeout', type=int, default=30, help='Connection timeout')
    conn_parser.add_argument('--stability', action='store_true', help='Run stability tests')
    conn_parser.add_argument('--stability-iterations', type=int, default=5, help='Stability test iterations')
    
    # prompt 命令
    prompt_parser = subparsers.add_parser('prompt', parents=[common_parser, llm_parser],
                                          help='Validate prompt templates')
    prompt_parser.add_argument('--performance', action='store_true', help='Run performance tests')
    
    # task 命令
    task_parser = subparsers.add_parser('task', parents=[common_parser, llm_parser],
                                        help='Validate task flow')
    task_parser.add_argument('--minimal', action='store_true', help='Run minimal validation (no DB)')
    task_parser.add_argument('--no-cleanup', action='store_true', help='Do not cleanup test data')
    
    # all 命令
    all_parser = subparsers.add_parser('all', parents=[common_parser, llm_parser],
                                       help='Run all validations')
    all_parser.add_argument('--providers', help='Comma-separated list of providers')
    all_parser.add_argument('--real-connection', action='store_true', help='Test real connections')
    all_parser.add_argument('--timeout', type=int, default=30, help='Connection timeout')
    all_parser.add_argument('--minimal', action='store_true', help='Use minimal task validation')
    all_parser.add_argument('--no-cleanup', action='store_true', help='Do not cleanup test data')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 加载环境配置
    read_env(args.env)
    
    # 配置日志
    setup_logging(verbose=args.verbose)
    
    # 打印横幅
    print_banner()
    print(f"Environment: {args.env}")
    print(f"Command: {args.command}")
    print(f"Time: {datetime.now().isoformat()}")
    
    # 运行验证 - 使用新的事件循环并设置超时
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        if args.command == 'quick':
            report = loop.run_until_complete(run_quick_check(args))
        elif args.command == 'connection':
            report = loop.run_until_complete(run_connection_validation(args))
        elif args.command == 'prompt':
            report = loop.run_until_complete(run_prompt_validation(args))
        elif args.command == 'task':
            report = loop.run_until_complete(run_task_validation(args))
        elif args.command == 'all':
            report = loop.run_until_complete(run_all_validations(args))
        else:
            parser.print_help()
            sys.exit(1)
        
        # 导出报告
        if args.output:
            export_report(report, args.output, args.format)
        
        # 返回状态码
        sys.exit(0 if report.is_all_success else 1)
        
    except KeyboardInterrupt:
        print("\n\n[!] Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n[X] Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # 清理事件循环
        try:
            # 取消所有待处理的任务
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

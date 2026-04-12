# -*- coding: utf-8 -*-
# @file db_sync.py
# @brief Database synchronization script for SailZen
# @author sailing-innocent
# @date 2026-04-12
# @version 1.0
# ---------------------------------
"""
数据库同步脚本

功能:
1. pull: 清空本地数据库，从云端数据库拉取数据覆盖
2. push-table: 将本地特定表上传到云端数据库

使用方法:
    # 从云端拉取数据到本地（会清空本地数据库！）
    uv run scripts/db_sync.py pull
    
    # 将本地特定表推送到云端
    uv run scripts/db_sync.py push-table --table work
    uv run scripts/db_sync.py push-table --table account
    
    # 查看帮助
    uv run scripts/db_sync.py --help

环境配置:
    - .env.dev: 本地数据库配置
    - .env.prod: 云端数据库配置（需要配置不同的 POSTGRE_URI）

注意事项:
    - pull 操作会清空本地数据库，请谨慎使用
    - 同步时会自动处理表之间的外键依赖关系
    - 建议在操作前备份重要数据
"""

import os
import sys
import argparse
import logging
from typing import List, Type, Any
from contextlib import contextmanager

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

# 设置 PostgreSQL 客户端编码环境变量
os.environ["PGCLIENTENCODING"] = "UTF8"

# 导入所有 ORM 模型
from sail_server.infrastructure.orm.orm_base import ORMBase
from sail_server.infrastructure.orm import health
from sail_server.infrastructure.orm import finance
from sail_server.infrastructure.orm import life
from sail_server.infrastructure.orm import project
from sail_server.infrastructure.orm import history
from sail_server.infrastructure.orm import text as text_module
from sail_server.infrastructure.orm import necessity
from sail_server.infrastructure.orm import analysis


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 定义表之间的依赖关系（用于确定同步顺序）
# 格式: '表名': ['依赖的表名列表']
TABLE_DEPENDENCIES = {
    # Finance 模块
    'accounts': [],
    'budgets': [],
    'budget_items': ['budgets'],
    'transactions': ['accounts', 'budgets'],
    
    # Project 模块
    'projects': [],
    'missions': ['projects'],
    
    # Text 模块
    'works': [],
    'editions': ['works'],
    'document_nodes': ['editions'],
    'ingest_jobs': ['editions'],
    
    # Necessity 模块
    'residences': [],
    'containers': ['residences'],
    'item_categories': [],
    'items': ['item_categories', 'containers'],
    'inventories': ['items', 'containers'],
    'journeys': [],
    'journey_items': ['journeys'],
    'consumptions': ['items'],
    'replenishments': ['items'],
    
    # Health 模块
    'weights': [],
    'weight_plans': [],
    'body_size': [],
    'exercises': [],
    
    # History 模块
    'history_events': [],
    'persons': [],
    
    # Life 模块
    # life_phenomenon, life_event 等
    
    # Analysis 模块 - Character
    'characters': [],
    'character_aliases': ['characters'],
    'character_arcs': ['characters'],
    'character_attributes': ['characters'],
    'character_relations': ['characters'],
    
    # Analysis 模块 - Setting & Outline
    'novel_settings': [],
    'setting_attributes': ['novel_settings'],
    'setting_relations': ['novel_settings'],
    'outlines': [],
    'outline_nodes': ['outlines'],
    'outline_events': ['outlines'],
    'text_evidence': ['novel_settings', 'characters'],
    'character_setting_links': ['characters', 'novel_settings'],
    
    # Unified Agent 模块
    'unified_agent_tasks': [],
    'unified_agent_steps': ['unified_agent_tasks'],
    'unified_agent_events': ['unified_agent_tasks'],
    
    # Service 模块
    'service_account': [],
}


def get_all_table_classes() -> List[Type]:
    """获取所有注册的 ORM 表类"""
    return list(ORMBase.registry.mappers)


def get_table_class_by_name(table_name: str) -> Type:
    """根据表名获取 ORM 类"""
    for mapper in ORMBase.registry.mappers:
        cls = mapper.class_
        if hasattr(cls, '__tablename__') and cls.__tablename__ == table_name:
            return cls
    raise ValueError(f"未知的表名: {table_name}")


def get_table_names() -> List[str]:
    """获取所有表名"""
    return sorted(ORMBase.metadata.tables.keys())


def get_sync_order() -> List[str]:
    """
    根据依赖关系计算表的同步顺序
    返回: 按依赖顺序排序的表名列表（被依赖的表在前）
    """
    all_tables = get_table_names()
    visited = set()
    order = []
    
    def visit(table: str):
        if table in visited:
            return
        if table not in all_tables:
            return
        visited.add(table)
        # 先访问依赖的表
        for dep in TABLE_DEPENDENCIES.get(table, []):
            visit(dep)
        order.append(table)
    
    for table in all_tables:
        visit(table)
    
    return order


class DatabaseSync:
    """数据库同步管理器"""
    
    def __init__(self, local_uri: str, remote_uri: str):
        # 转换 URI 格式以使用 psycopg3
        if local_uri.startswith("postgresql://"):
            local_uri = local_uri.replace("postgresql://", "postgresql+psycopg://", 1)
        if remote_uri.startswith("postgresql://"):
            remote_uri = remote_uri.replace("postgresql://", "postgresql+psycopg://", 1)
        
        self.local_uri = local_uri
        self.remote_uri = remote_uri
        
        # 创建引擎
        self.local_engine = create_engine(local_uri)
        self.remote_engine = create_engine(remote_uri)
        
        # 创建会话工厂
        self.LocalSession = sessionmaker(bind=self.local_engine)
        self.RemoteSession = sessionmaker(bind=self.remote_engine)
        
        logger.info("数据库同步管理器初始化完成")
        logger.info(f"本地数据库: {self._mask_uri(local_uri)}")
        logger.info(f"云端数据库: {self._mask_uri(remote_uri)}")
    
    @staticmethod
    def _mask_uri(uri: str) -> str:
        """隐藏 URI 中的密码"""
        try:
            if '@' in uri:
                prefix, suffix = uri.split('@', 1)
                if ':' in prefix:
                    protocol, auth = prefix.split('://', 1)
                    user, _ = auth.rsplit(':', 1)
                    return f"{protocol}://{user}:****@{suffix}"
        except:
            pass
        return uri
    
    @contextmanager
    def local_session(self):
        """本地数据库会话上下文管理器"""
        session = self.LocalSession()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    @contextmanager
    def remote_session(self):
        """云端数据库会话上下文管理器"""
        session = self.RemoteSession()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def test_connections(self) -> bool:
        """测试数据库连接"""
        try:
            with self.local_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✓ 本地数据库连接正常")
        except Exception as e:
            logger.error(f"✗ 本地数据库连接失败: {e}")
            return False
        
        try:
            with self.remote_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✓ 云端数据库连接正常")
        except Exception as e:
            logger.error(f"✗ 云端数据库连接失败: {e}")
            return False
        
        return True
    
    def reset_local_database(self):
        """重置本地数据库（删除所有表并重新创建）"""
        logger.warning("⚠️  正在重置本地数据库...")
        
        # 删除所有表
        ORMBase.metadata.drop_all(bind=self.local_engine)
        logger.info("  - 已删除所有表")
        
        # 重新创建所有表
        ORMBase.metadata.create_all(bind=self.local_engine)
        logger.info("  - 已重新创建所有表")
    
    def pull_from_remote(self, confirm: bool = True):
        """
        从云端数据库拉取数据到本地
        
        Args:
            confirm: 是否需要用户确认
        """
        if confirm:
            print("\n" + "=" * 60)
            print("⚠️  警告：此操作将清空本地数据库！")
            print("=" * 60)
            print(f"本地数据库: {self._mask_uri(self.local_uri)}")
            print(f"云端数据库: {self._mask_uri(self.remote_uri)}")
            print("=" * 60)
            
            response = input("\n确认要继续吗？(输入 'yes' 确认): ")
            if response.lower() != 'yes':
                logger.info("操作已取消")
                return
        
        # 测试连接
        if not self.test_connections():
            raise RuntimeError("数据库连接测试失败")
        
        # 重置本地数据库
        self.reset_local_database()
        
        # 获取同步顺序
        sync_order = get_sync_order()
        logger.info(f"\n同步顺序: {' -> '.join(sync_order)}")
        
        # 按顺序同步每个表
        total_copied = 0
        for table_name in sync_order:
            try:
                count = self._copy_table_from_remote(table_name)
                total_copied += count
                logger.info(f"  ✓ {table_name}: 复制了 {count} 条记录")
            except Exception as e:
                logger.error(f"  ✗ {table_name}: 复制失败 - {e}")
                raise
        
        logger.info(f"\n✅ 同步完成！共复制 {total_copied} 条记录")
    
    def _copy_table_from_remote(self, table_name: str) -> int:
        """从云端复制特定表的数据到本地"""
        cls = get_table_class_by_name(table_name)
        
        with self.remote_session() as remote_sess:
            # 从云端获取所有数据
            records = remote_sess.query(cls).all()
            
            if not records:
                return 0
            
            # 转换为字典列表（排除 SQLAlchemy 内部属性）
            data_list = []
            for record in records:
                data = {}
                for column in record.__table__.columns:
                    data[column.name] = getattr(record, column.name)
                data_list.append(data)
        
        with self.local_session() as local_sess:
            # 批量插入到本地
            for data in data_list:
                new_record = cls(**data)
                local_sess.add(new_record)
        
        return len(data_list)
    
    def push_table_to_remote(self, table_name: str, confirm: bool = True):
        """
        将本地特定表推送到云端
        
        Args:
            table_name: 要推送的表名
            confirm: 是否需要用户确认
        """
        # 验证表名
        all_tables = get_table_names()
        if table_name not in all_tables:
            logger.error(f"未知的表名: {table_name}")
            logger.info(f"可用表: {', '.join(all_tables)}")
            return
        
        # 检查依赖
        dependencies = TABLE_DEPENDENCIES.get(table_name, [])
        if dependencies:
            logger.warning(f"⚠️  表 '{table_name}' 依赖于: {', '.join(dependencies)}")
            logger.warning("    请确保云端数据库中已存在相关记录，否则可能导致外键约束错误")
        
        if confirm:
            print("\n" + "=" * 60)
            print(f"⚠️  警告：此操作将覆盖云端数据库中的 '{table_name}' 表！")
            print("=" * 60)
            print(f"本地数据库: {self._mask_uri(self.local_uri)}")
            print(f"云端数据库: {self._mask_uri(self.remote_uri)}")
            print(f"目标表: {table_name}")
            print("=" * 60)
            
            response = input("\n确认要继续吗？(输入 'yes' 确认): ")
            if response.lower() != 'yes':
                logger.info("操作已取消")
                return
        
        # 测试连接
        if not self.test_connections():
            raise RuntimeError("数据库连接测试失败")
        
        # 推送表
        try:
            count = self._copy_table_to_remote(table_name)
            logger.info(f"\n✅ 推送完成！共复制 {count} 条记录到云端 '{table_name}' 表")
        except Exception as e:
            logger.error(f"\n✗ 推送失败: {e}")
            raise
    
    def _copy_table_to_remote(self, table_name: str) -> int:
        """将本地特定表的数据复制到云端"""
        cls = get_table_class_by_name(table_name)
        
        with self.local_session() as local_sess:
            # 从本地获取所有数据
            records = local_sess.query(cls).all()
            
            if not records:
                logger.info(f"  - 本地 '{table_name}' 表为空，无需推送")
                return 0
            
            # 转换为字典列表
            data_list = []
            for record in records:
                data = {}
                for column in record.__table__.columns:
                    data[column.name] = getattr(record, column.name)
                data_list.append(data)
        
        with self.remote_session() as remote_sess:
            # 先删除云端该表的所有数据
            remote_sess.query(cls).delete()
            logger.info(f"  - 已清空云端 '{table_name}' 表")
            
            # 批量插入到云端
            for data in data_list:
                new_record = cls(**data)
                remote_sess.add(new_record)
        
        return len(data_list)
    
    def list_tables(self):
        """列出所有可用的表"""
        print("\n可用的表（按依赖顺序）:")
        print("=" * 60)
        
        sync_order = get_sync_order()
        for i, table_name in enumerate(sync_order, 1):
            deps = TABLE_DEPENDENCIES.get(table_name, [])
            dep_str = f" (依赖: {', '.join(deps)})" if deps else ""
            print(f"  {i:2d}. {table_name}{dep_str}")
        
        print("=" * 60)
        print(f"\n共 {len(sync_order)} 个表")


def load_env_file(env_file: str) -> dict:
    """加载环境文件并返回配置字典"""
    if not os.path.exists(env_file):
        raise FileNotFoundError(f"环境文件不存在: {env_file}")
    
    # 临时清空环境变量，避免干扰
    original_env = dict(os.environ)
    for key in list(os.environ.keys()):
        if key not in ['PATH', 'PGCLIENTENCODING']:
            del os.environ[key]
    
    # 加载环境文件
    load_dotenv(env_file, override=True)
    
    config = {
        'POSTGRE_URI': os.environ.get('POSTGRE_URI'),
    }
    
    # 恢复原始环境
    os.environ.clear()
    os.environ.update(original_env)
    
    return config


def main():
    parser = argparse.ArgumentParser(
        description='SailZen 数据库同步工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 从云端拉取数据到本地（会清空本地数据库！）
    uv run scripts/db_sync.py pull
    
    # 将本地特定表推送到云端
    uv run scripts/db_sync.py push-table --table work
    uv run scripts/db_sync.py push-table --table account
    
    # 跳过确认提示
    uv run scripts/db_sync.py pull --no-confirm
    uv run scripts/db_sync.py push-table --table work --no-confirm
    
    # 列出所有可用的表
    uv run scripts/db_sync.py list-tables
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # pull 命令
    pull_parser = subparsers.add_parser(
        'pull',
        help='从云端拉取数据到本地（会清空本地数据库）'
    )
    pull_parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='跳过确认提示'
    )
    
    # push-table 命令
    push_parser = subparsers.add_parser(
        'push-table',
        help='将本地特定表推送到云端'
    )
    push_parser.add_argument(
        '--table', '-t',
        required=True,
        help='要推送的表名'
    )
    push_parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='跳过确认提示'
    )
    
    # list-tables 命令
    subparsers.add_parser(
        'list-tables',
        help='列出所有可用的表'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 加载环境配置
    env_dev_path = os.path.join(project_root, '.env.dev')
    env_prod_path = os.path.join(project_root, '.env.prod')
    
    try:
        dev_config = load_env_file(env_dev_path)
        prod_config = load_env_file(env_prod_path)
    except FileNotFoundError as e:
        logger.error(f"加载环境文件失败: {e}")
        sys.exit(1)
    
    local_uri = dev_config.get('POSTGRE_URI')
    remote_uri = prod_config.get('POSTGRE_URI')
    
    if not local_uri:
        logger.error("未在 .env.dev 中找到 POSTGRE_URI 配置")
        sys.exit(1)
    
    if not remote_uri:
        logger.error("未在 .env.prod 中找到 POSTGRE_URI 配置")
        sys.exit(1)
    
    if local_uri == remote_uri:
        logger.warning("⚠️  警告: .env.dev 和 .env.prod 的数据库配置相同！")
        logger.warning("    请修改 .env.prod 中的 POSTGRE_URI 为云端数据库地址")
        response = input("\n确认要继续吗？(输入 'yes' 确认): ")
        if response.lower() != 'yes':
            logger.info("操作已取消")
            sys.exit(0)
    
    # 执行命令
    sync = DatabaseSync(local_uri, remote_uri)
    
    if args.command == 'pull':
        sync.pull_from_remote(confirm=not args.no_confirm)
    elif args.command == 'push-table':
        sync.push_table_to_remote(args.table, confirm=not args.no_confirm)
    elif args.command == 'list-tables':
        sync.list_tables()


if __name__ == '__main__':
    main()

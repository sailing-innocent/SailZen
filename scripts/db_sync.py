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
from typing import Dict, List, Set, Type
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# 设置项目根目录并加入 sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

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


def _build_table_dependencies() -> Dict[str, Set[str]]:
    """
    从 SQLAlchemy MetaData 自动推导表之间的外键依赖关系。
    
    遍历所有已注册的 ORM 表的 ForeignKey，构建依赖图。
    自引用外键（如 containers.parent_id -> containers.id）会被自动忽略。
    
    Returns:
        dict: {表名: {依赖的表名集合}}
    """
    deps: Dict[str, Set[str]] = {}
    all_tables = ORMBase.metadata.tables  # dict[str, Table]

    for table_name, table in all_tables.items():
        referred = set()
        for fk in table.foreign_keys:
            referred_table = fk.column.table.name
            # 排除自引用（如 containers.parent_id -> containers.id）
            if referred_table != table_name:
                referred.add(referred_table)
        deps[table_name] = referred

    return deps


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


def get_table_dependencies() -> Dict[str, Set[str]]:
    """获取表之间的依赖关系"""
    return _build_table_dependencies()


def get_reverse_dependencies() -> Dict[str, Set[str]]:
    """
    获取表的反向依赖关系。
    
    Returns:
        dict: {表名: {依赖于该表的表名集合}}
    """
    deps = get_table_dependencies()
    reverse: Dict[str, Set[str]] = {t: set() for t in deps}
    for table, referred_tables in deps.items():
        for ref in referred_tables:
            if ref in reverse:
                reverse[ref].add(table)
    return reverse


def get_sync_order() -> List[str]:
    """
    根据外键依赖关系做拓扑排序，计算表的同步顺序。
    返回: 按依赖顺序排序的表名列表（被依赖的表在前）
    
    Raises:
        RuntimeError: 如果检测到循环依赖
    """
    deps = get_table_dependencies()
    all_tables = set(deps.keys())
    visited: Set[str] = set()
    in_stack: Set[str] = set()  # 用于检测循环依赖
    order: List[str] = []
    
    def visit(table: str):
        if table in in_stack:
            raise RuntimeError(f"检测到循环依赖，涉及表: {table}")
        if table in visited:
            return
        if table not in all_tables:
            return
        visited.add(table)
        in_stack.add(table)
        # 先访问依赖的表
        for dep in deps.get(table, set()):
            visit(dep)
        in_stack.discard(table)
        order.append(table)
    
    for table in sorted(all_tables):
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
        except Exception:
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
    
    def _get_existing_tables(self, engine) -> Set[str]:
        """获取数据库中实际存在的表名集合"""
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(engine)
        return set(inspector.get_table_names())
    
    def _diff_tables(self, engine, label: str) -> tuple[Set[str], Set[str]]:
        """
        对比 ORM 定义的表与数据库中实际存在的表。
        
        Args:
            engine: SQLAlchemy engine
            label: 数据库标签（用于日志，如 "本地" / "云端"）
        
        Returns:
            (existing, missing): 存在的表名集合, 缺失的表名集合
        """
        orm_tables = set(get_table_names())
        db_tables = self._get_existing_tables(engine)
        
        existing = orm_tables & db_tables
        missing = orm_tables - db_tables
        extra = db_tables - orm_tables
        
        if missing:
            logger.warning(
                f"⚠️  {label}数据库缺少以下 ORM 表 (将跳过): "
                f"{', '.join(sorted(missing))}"
            )
        if extra:
            logger.info(
                f"ℹ️  {label}数据库存在 ORM 未定义的表 (已忽略): "
                f"{', '.join(sorted(extra))}"
            )
        
        return existing, missing
    
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
        
        # 检查云端数据库实际存在哪些表
        remote_existing, remote_missing = self._diff_tables(self.remote_engine, "云端")
        
        # 重置本地数据库
        self.reset_local_database()
        
        # 获取同步顺序，过滤掉云端不存在的表
        sync_order = [t for t in get_sync_order() if t in remote_existing]
        skipped = sorted(remote_missing)
        
        if skipped:
            logger.warning(f"\n⏭️  将跳过 {len(skipped)} 个云端不存在的表: {', '.join(skipped)}")
        logger.info(f"\n同步顺序 ({len(sync_order)} 表): {' -> '.join(sync_order)}")
        
        # 按顺序同步每个表
        total_copied = 0
        failed_tables: List[str] = []
        for table_name in sync_order:
            try:
                count = self._copy_table_from_remote(table_name)
                total_copied += count
                logger.info(f"  ✓ {table_name}: 复制了 {count} 条记录")
            except Exception as e:
                logger.error(f"  ✗ {table_name}: 复制失败 - {e}")
                failed_tables.append(table_name)
                # 不再直接 raise，继续处理后续无依赖关系的表
        
        # 输出汇总
        if failed_tables:
            logger.warning(
                f"\n⚠️  同步完成（有错误）！共复制 {total_copied} 条记录，"
                f"{len(failed_tables)} 个表失败: {', '.join(failed_tables)}"
            )
        else:
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
        
        # 检查依赖（该表依赖哪些表）
        deps = get_table_dependencies()
        dependencies = deps.get(table_name, set())
        if dependencies:
            logger.warning(f"⚠️  表 '{table_name}' 依赖于: {', '.join(sorted(dependencies))}")
            logger.warning("    请确保云端数据库中已存在相关记录，否则可能导致外键约束错误")
        
        # 检查反向依赖（哪些表依赖该表）
        reverse_deps = get_reverse_dependencies()
        dependents = reverse_deps.get(table_name, set())
        if dependents:
            logger.warning(f"⚠️  以下表依赖于 '{table_name}': {', '.join(sorted(dependents))}")
            logger.warning("    推送时会先清空云端该表数据，可能导致依赖表的外键约束报错")
        
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
        
        # 检查表在本地和云端数据库是否实际存在
        local_db_tables = self._get_existing_tables(self.local_engine)
        remote_db_tables = self._get_existing_tables(self.remote_engine)
        
        if table_name not in local_db_tables:
            logger.error(
                f"✗ 表 '{table_name}' 在本地数据库中不存在，无法推送。"
                f"请先运行数据库迁移创建该表。"
            )
            return
        
        if table_name not in remote_db_tables:
            logger.error(
                f"✗ 表 '{table_name}' 在云端数据库中不存在，无法推送。"
                f"请先在云端运行数据库迁移创建该表。"
            )
            return
        
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
    
def _print_table_list():
    """列出所有可用的表（独立函数，无需数据库连接）"""
    print("\n可用的表（按依赖顺序）:")
    print("=" * 60)
    
    sync_order = get_sync_order()
    deps = get_table_dependencies()
    for i, table_name in enumerate(sync_order, 1):
        table_deps = deps.get(table_name, set())
        dep_str = f" (依赖: {', '.join(sorted(table_deps))})" if table_deps else ""
        print(f"  {i:2d}. {table_name}{dep_str}")
    
    print("=" * 60)
    print(f"\n共 {len(sync_order)} 个表")


def _print_table_list_with_check(sync: DatabaseSync):
    """列出所有表并检查与实际数据库的一致性"""
    if not sync.test_connections():
        logger.error("数据库连接失败，无法执行一致性检查")
        return
    
    orm_tables = set(get_table_names())
    local_tables = sync._get_existing_tables(sync.local_engine)
    remote_tables = sync._get_existing_tables(sync.remote_engine)
    
    sync_order = get_sync_order()
    deps = get_table_dependencies()
    
    print("\n表一致性检查 (ORM vs 本地 vs 云端):")
    print("=" * 75)
    print(f"  {'#':>3}  {'表名':<30} {'本地':^6} {'云端':^6} {'依赖'}")
    print("-" * 75)
    
    local_missing = []
    remote_missing = []
    
    for i, table_name in enumerate(sync_order, 1):
        in_local = "✓" if table_name in local_tables else "✗"
        in_remote = "✓" if table_name in remote_tables else "✗"
        
        table_deps = deps.get(table_name, set())
        dep_str = ', '.join(sorted(table_deps)) if table_deps else ""
        
        # 标记有问题的行
        marker = ""
        if table_name not in local_tables:
            marker = " ← 本地缺失"
            local_missing.append(table_name)
        if table_name not in remote_tables:
            marker = " ← 云端缺失" if not marker else " ← 两端缺失"
            remote_missing.append(table_name)
        
        print(f"  {i:3d}. {table_name:<30} {in_local:^6} {in_remote:^6} {dep_str}{marker}")
    
    # 检查数据库中有但 ORM 没定义的表
    local_extra = local_tables - orm_tables
    remote_extra = remote_tables - orm_tables
    
    print("=" * 75)
    print(f"\n  ORM 定义: {len(orm_tables)} 表")
    print(f"  本地数据库: {len(local_tables & orm_tables)}/{len(orm_tables)} 表匹配"
          f"{f'，{len(local_missing)} 缺失' if local_missing else ''}")
    print(f"  云端数据库: {len(remote_tables & orm_tables)}/{len(orm_tables)} 表匹配"
          f"{f'，{len(remote_missing)} 缺失' if remote_missing else ''}")
    
    if local_extra:
        print(f"\n  ℹ️  本地数据库多余的表 (ORM 未定义): {', '.join(sorted(local_extra))}")
    if remote_extra:
        print(f"  ℹ️  云端数据库多余的表 (ORM 未定义): {', '.join(sorted(remote_extra))}")
    
    if not local_missing and not remote_missing:
        print(f"\n  ✅ 所有表一致，无问题！")
    else:
        print(f"\n  ⚠️  存在不一致，请检查是否需要运行数据库迁移。")


def load_env_file(env_file: str) -> dict:
    """加载环境文件并返回配置字典"""
    if not os.path.exists(env_file):
        raise FileNotFoundError(f"环境文件不存在: {env_file}")
    
    # 临时清空环境变量，避免干扰
    original_env = dict(os.environ)
    try:
        for key in list(os.environ.keys()):
            if key not in ['PATH', 'PGCLIENTENCODING']:
                del os.environ[key]
        
        # 加载环境文件
        load_dotenv(env_file, override=True)
        
        config = {
            'POSTGRE_URI': os.environ.get('POSTGRE_URI'),
        }
    finally:
        # 无论成功或异常，始终恢复原始环境
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
    list_parser = subparsers.add_parser(
        'list-tables',
        help='列出所有可用的表'
    )
    list_parser.add_argument(
        '--check',
        action='store_true',
        help='检查本地/云端数据库与 ORM 定义的一致性'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # list-tables: 基本模式不需要数据库连接；--check 模式需要
    if args.command == 'list-tables' and not args.check:
        _print_table_list()
        return
    
    # 其余命令需要加载环境配置
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
    elif args.command == 'list-tables' and args.check:
        _print_table_list_with_check(sync)

if __name__ == '__main__':
    main()

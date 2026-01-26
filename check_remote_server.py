#!/usr/bin/env python3
"""
远程PostgreSQL服务器状态检测脚本
检测指定服务器的PostgreSQL是否成功启动并可以连接
"""

import socket
import sys
import time
from typing import Optional, Tuple
import argparse

try:
    import psycopg2
    from psycopg2 import OperationalError, Error

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("警告: psycopg2未安装，将跳过数据库连接测试")
    print("安装命令: pip install psycopg2-binary")


def check_port_open(
    host: str, port: int, timeout: int = 5
) -> Tuple[bool, Optional[str]]:
    """检查端口是否开放"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            return True, None
        else:
            return False, f"端口连接失败 (错误代码: {result})"
    except socket.gaierror as e:
        return False, f"DNS解析失败: {e}"
    except socket.timeout:
        return False, f"连接超时 (>{timeout}秒)"
    except Exception as e:
        return False, f"连接错误: {e}"


def check_postgres_connection(
    host: str,
    port: int,
    database: str = "postgres",
    user: str = "postgres",
    password: Optional[str] = None,
    timeout: int = 5,
) -> Tuple[bool, Optional[str], Optional[dict]]:
    """检查PostgreSQL数据库连接"""
    if not PSYCOPG2_AVAILABLE:
        return False, "psycopg2未安装", None

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=timeout,
        )

        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]

        cursor.execute("SELECT now();")
        server_time = cursor.fetchone()[0]

        cursor.execute("""
            SELECT datname, pg_size_pretty(pg_database_size(datname)) as size 
            FROM pg_database 
            WHERE datistemplate = false 
            ORDER BY datname;
        """)
        databases = cursor.fetchall()

        cursor.execute("""
            SELECT 
                count(*) as total_connections,
                count(*) FILTER (WHERE state = 'active') as active_connections,
                count(*) FILTER (WHERE state = 'idle') as idle_connections
            FROM pg_stat_activity;
        """)
        conn_info = cursor.fetchone()

        server_info = {
            "version": version,
            "server_time": str(server_time),
            "databases": databases,
            "total_connections": conn_info[0],
            "active_connections": conn_info[1],
            "idle_connections": conn_info[2],
        }

        cursor.close()
        conn.close()

        return True, None, server_info

    except OperationalError as e:
        error_msg = str(e)
        if "password" in error_msg.lower() or "authentication" in error_msg.lower():
            return False, f"认证失败: {error_msg}", None
        elif "timeout" in error_msg.lower():
            return False, f"连接超时: {error_msg}", None
        else:
            return False, f"连接错误: {error_msg}", None
    except Error as e:
        return False, f"PostgreSQL错误: {e}", None
    except Exception as e:
        return False, f"未知错误: {e}", None


def ping_host(host: str, timeout: int = 3) -> Tuple[bool, Optional[str]]:
    """Ping主机检查网络连通性"""
    import platform

    try:
        if platform.system().lower() == "windows":
            import subprocess

            result = subprocess.run(
                ["ping", "-n", "1", "-w", str(timeout * 1000), host],
                capture_output=True,
                timeout=timeout + 2,
            )
            return (
                result.returncode == 0,
                None if result.returncode == 0 else "Ping失败",
            )
        else:
            import subprocess

            result = subprocess.run(
                ["ping", "-c", "1", "-W", str(timeout), host],
                capture_output=True,
                timeout=timeout + 2,
            )
            return (
                result.returncode == 0,
                None if result.returncode == 0 else "Ping失败",
            )
    except Exception as e:
        return False, f"Ping错误: {e}"


def main():
    parser = argparse.ArgumentParser(
        description="检测远程PostgreSQL服务器状态",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本检测
  python check_remote_postgres.py --host 101.43.22.254
  
  # 指定用户名和密码
  python check_remote_postgres.py --host 101.43.22.254 --user myuser --password mypass
  
  # 检测特定数据库
  python check_remote_postgres.py --host 101.43.22.254 --database mydb
        """,
    )

    parser.add_argument(
        "--host", "-H", default="101.43.22.254", help="PostgreSQL服务器地址"
    )
    parser.add_argument("--port", "-p", type=int, default=5432, help="PostgreSQL端口")
    parser.add_argument("--database", "-d", default="postgres", help="数据库名")
    parser.add_argument("--user", "-U", default="postgres", help="用户名")
    parser.add_argument("--password", "-P", help="密码")
    parser.add_argument("--timeout", "-t", type=int, default=5, help="超时时间(秒)")
    parser.add_argument("--skip-ping", action="store_true", help="跳过Ping测试")

    args = parser.parse_args()

    print("=" * 60)
    print("远程PostgreSQL服务器状态检测")
    print("=" * 60)
    print(f"服务器地址: {args.host}:{args.port}")
    print(f"数据库: {args.database}")
    print(f"用户名: {args.user}")
    print("=" * 60)
    print()

    all_checks_passed = True

    # 1. Ping测试
    if not args.skip_ping:
        print("[1/4] 检查网络连通性 (Ping)...")
        ping_ok, ping_error = ping_host(args.host, args.timeout)
        if ping_ok:
            print(f"✓ 主机 {args.host} 网络可达")
        else:
            print(f"✗ 主机 {args.host} 网络不可达: {ping_error}")
            all_checks_passed = False
        print()

    # 2. 端口检查
    print(f"[2/4] 检查端口 {args.port} 是否开放...")
    port_ok, port_error = check_port_open(args.host, args.port, args.timeout)
    if port_ok:
        print(f"✓ 端口 {args.port} 已开放")
    else:
        print(f"✗ 端口 {args.port} 未开放: {port_error}")
        all_checks_passed = False
        print()
        print("=" * 60)
        print("检测结果: PostgreSQL服务器可能未启动或无法访问")
        print("=" * 60)
        sys.exit(1)
    print()

    # 3. PostgreSQL连接测试
    print(f"[3/4] 尝试连接PostgreSQL数据库...")
    if args.password:
        conn_ok, conn_error, server_info = check_postgres_connection(
            args.host, args.port, args.database, args.user, args.password, args.timeout
        )

        if conn_ok:
            print("✓ PostgreSQL连接成功!")
            print()
            print("服务器信息:")
            print(f"  版本: {server_info['version']}")
            print(f"  服务器时间: {server_info['server_time']}")
            print(f"  总连接数: {server_info['total_connections']}")
            print(f"  活跃连接: {server_info['active_connections']}")
            print(f"  空闲连接: {server_info['idle_connections']}")
            print()
            print("数据库列表:")
            for db_name, db_size in server_info["databases"]:
                print(f"  - {db_name} ({db_size})")
        else:
            print(f"✗ PostgreSQL连接失败: {conn_error}")
            all_checks_passed = False
    else:
        print("⚠ 未提供密码，跳过数据库连接测试")
        print("提示: 使用 --password 参数进行完整测试")
    print()

    # 4. 总结
    print("[4/4] 检测总结")
    print("=" * 60)
    if all_checks_passed and (not args.password or conn_ok):
        print("✓ PostgreSQL服务器运行正常!")
        sys.exit(0)
    else:
        print("✗ PostgreSQL服务器存在问题")
        print()
        print("可能的原因:")
        print("  1. PostgreSQL服务未启动")
        print("  2. 防火墙阻止了连接")
        print("  3. PostgreSQL配置不允许远程连接")
        print("  4. 认证失败 (用户名/密码错误)")
        print("  5. 数据库不存在")
        print()
        print("建议:")
        print("  1. 检查服务器上的PostgreSQL服务状态")
        print("  2. 检查pg_hba.conf配置是否允许远程连接")
        print("  3. 检查postgresql.conf中的listen_addresses设置")
        print("  4. 检查防火墙规则")
        sys.exit(1)


if __name__ == "__main__":
    main()

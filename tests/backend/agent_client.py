#!/usr/bin/env python3
"""
CubeClaw Agent Client - 可在Windows/Mac上独立运行的Agent
使用配置文件确定角色(manager/worker)并注册到Manager服务器
"""
import argparse
import asyncio
import json
import os
import platform
import socket
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx


class AgentConfig:
    """Agent配置"""
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._default_config_path()
        self._config = self._load_config()
    
    def _default_config_path(self) -> str:
        return str(Path(__file__).parent / "agent_config.json")
    
    def _load_config(self) -> dict:
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def save(self):
        with open(self.config_path, 'w') as f:
            json.dump(self._config, f, indent=2)
    
    @property
    def agent_id(self) -> str:
        if 'agent_id' not in self._config:
            hostname = socket.gethostname().lower().replace('.', '-')
            plat = platform.system().lower()[:3]
            self._config['agent_id'] = f"{plat}-{hostname}-{uuid.uuid4().hex[:4]}"
            self.save()
        return self._config['agent_id']
    
    @property
    def agent_name(self) -> str:
        return self._config.get('agent_name', f"Agent on {socket.gethostname()}")
    
    @property
    def platform(self) -> str:
        system = platform.system().lower()
        if system == 'darwin':
            return 'macos'
        return system
    
    @property
    def role(self) -> str:
        return self._config.get('role', 'worker')
    
    @property
    def manager_url(self) -> str:
        return self._config.get('manager_url', 'http://localhost:8000')
    
    @property
    def capabilities(self) -> list:
        # 根据平台自动设置能力
        default_caps = ['globalbatch', 'review', 'git_commit', 'notify']
        if self.platform == 'windows':
            default_caps.append('build_win')
        elif self.platform == 'macos':
            default_caps.append('build_ios')
        return self._config.get('capabilities', default_caps)
    
    @property
    def working_dir(self) -> str:
        return self._config.get('working_dir', os.getcwd())
    
    @property
    def opencode_port(self) -> Optional[int]:
        return self._config.get('opencode_port', 4096)
    
    @property
    def port(self) -> int:
        return self._config.get('port', 8080)
    
    def set(self, key: str, value):
        self._config[key] = value
        self.save()


class AgentClient:
    """Agent客户端"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)
        self.registered = False
        self.heartbeat_interval = 30
        self.current_task_id: Optional[str] = None
        self.running = False
    
    async def register(self) -> bool:
        """向Manager注册Agent"""
        try:
            host = self._get_local_ip()
            response = await self.client.post(
                f"{self.config.manager_url}/agents/register",
                json={
                    "id": self.config.agent_id,
                    "name": self.config.agent_name,
                    "host": host,
                    "port": self.config.port,
                    "platform": self.config.platform,
                    "role": self.config.role,
                    "capabilities": self.config.capabilities,
                    "opencode_port": self.config.opencode_port,
                    "working_dir": self.config.working_dir,
                    "config": {}
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self.heartbeat_interval = data.get('heartbeat_interval', 30)
                self.registered = True
                print(f"✅ Agent registered successfully!")
                print(f"   ID: {self.config.agent_id}")
                print(f"   Role: {self.config.role}")
                print(f"   Platform: {self.config.platform}")
                print(f"   Capabilities: {', '.join(self.config.capabilities)}")
                return True
            else:
                print(f"❌ Registration failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return False
    
    async def heartbeat(self) -> dict:
        """发送心跳"""
        try:
            response = await self.client.post(
                f"{self.config.manager_url}/agents/{self.config.agent_id}/heartbeat",
                json={
                    "agent_id": self.config.agent_id,
                    "status": "busy" if self.current_task_id else "online",
                    "current_task_id": self.current_task_id,
                    "resource_usage": self._get_resource_usage(),
                    "active_sessions": 1 if self.current_task_id else 0
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️ Heartbeat failed: {response.status_code}")
                return {"ack": False}
                
        except Exception as e:
            print(f"⚠️ Heartbeat error: {e}")
            return {"ack": False}
    
    async def run(self):
        """运行Agent主循环"""
        print(f"\n🚀 Starting CubeClaw Agent...")
        print(f"   Manager: {self.config.manager_url}")
        print(f"   Working Dir: {self.config.working_dir}\n")
        
        # 注册
        if not await self.register():
            print("Failed to register agent. Retrying in 10 seconds...")
            await asyncio.sleep(10)
            if not await self.register():
                print("Registration failed. Exiting.")
                return
        
        self.running = True
        
        # 心跳循环
        while self.running:
            try:
                result = await self.heartbeat()
                
                if result.get("ack"):
                    pending_tasks = result.get("pending_tasks", [])
                    if pending_tasks and not self.current_task_id:
                        # 有待处理任务
                        task = pending_tasks[0]
                        print(f"\n📋 Received task: {task['task_type']} (ID: {task['id']})")
                        # 实际执行由Manager通过Session控制
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                await asyncio.sleep(5)
        
        print("\n👋 Agent stopped")
    
    def stop(self):
        """停止Agent"""
        self.running = False
    
    def _get_local_ip(self) -> str:
        """获取本机IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def _get_resource_usage(self) -> dict:
        """获取资源使用情况"""
        try:
            import psutil
            return {
                "cpu": psutil.cpu_percent(),
                "memory": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage('/').percent
            }
        except:
            return {"cpu": 0, "memory": 0, "disk": 0}
    
    async def close(self):
        await self.client.aclose()


def create_default_config(path: str, role: str = 'worker', manager_url: str = 'http://localhost:8000'):
    """创建默认配置文件"""
    config = {
        "agent_name": f"Agent on {socket.gethostname()}",
        "role": role,
        "manager_url": manager_url,
        "working_dir": os.getcwd(),
        "opencode_port": 4096,
        "port": 8080
    }
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"✅ Created config file: {path}")
    print(f"   Edit this file to customize your agent settings.")


def main():
    parser = argparse.ArgumentParser(description='CubeClaw Agent Client')
    parser.add_argument('--config', '-c', help='Path to config file')
    parser.add_argument('--role', choices=['manager', 'worker'], default='worker',
                        help='Agent role (default: worker)')
    parser.add_argument('--manager-url', '-m', default='http://localhost:8000',
                        help='Manager server URL (default: http://localhost:8000)')
    parser.add_argument('--working-dir', '-w', help='Working directory')
    parser.add_argument('--init', action='store_true', help='Initialize config file')
    
    args = parser.parse_args()
    
    config_path = args.config or 'agent_config.json'
    
    if args.init:
        create_default_config(config_path, args.role, args.manager_url)
        return
    
    # 加载或创建配置
    config = AgentConfig(config_path)
    
    # 命令行参数覆盖配置
    if args.role:
        config.set('role', args.role)
    if args.manager_url:
        config.set('manager_url', args.manager_url)
    if args.working_dir:
        config.set('working_dir', args.working_dir)
    
    # 创建并运行Agent
    agent = AgentClient(config)
    
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopping agent...")
        agent.stop()
    finally:
        asyncio.run(agent.close())


if __name__ == '__main__':
    main()

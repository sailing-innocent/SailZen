"""
Mock Skills for Demo - 模拟Agent执行的各类技能
后续可无缝替换为专业的Agent Skill实现
"""
import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class SkillResult:
    """Skill执行结果"""
    success: bool
    data: dict = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    error: Optional[str] = None
    duration_seconds: float = 0


class MockSkill:
    """Mock Skill基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    async def execute(self, context: dict, on_progress: Optional[Callable] = None) -> SkillResult:
        raise NotImplementedError


class GlobalBatchSkill(MockSkill):
    """GlobalBatch技能 - 模拟从微软main分支cherry-pick到netease/main"""
    
    def __init__(self):
        super().__init__(
            name="globalbatch",
            description="执行GlobalBatch流程：检查目录、注入skill、执行cherry-pick"
        )
    
    async def execute(self, context: dict, on_progress: Optional[Callable] = None) -> SkillResult:
        logs = []
        start_time = datetime.now()
        
        try:
            working_dir = context.get("working_dir", ".")
            branch = context.get("branch", "netease/globalbatch/demo")
            commits = context.get("commits", ["abc1234", "def5678", "ghi9012"])
            
            # Step 1: 检查目录
            logs.append(f"[{datetime.now().isoformat()}] 📂 检查工作目录: {working_dir}")
            if on_progress:
                await on_progress({"step": "check_dir", "progress": 10, "log": logs[-1]})
            await asyncio.sleep(1)
            
            # Step 2: 注入Skill
            logs.append(f"[{datetime.now().isoformat()}] 🔧 注入GlobalBatch Skill配置")
            if on_progress:
                await on_progress({"step": "inject_skill", "progress": 20, "log": logs[-1]})
            await asyncio.sleep(0.5)
            
            # Step 3: 创建分支
            logs.append(f"[{datetime.now().isoformat()}] 🌿 创建分支: {branch}")
            if on_progress:
                await on_progress({"step": "create_branch", "progress": 30, "log": logs[-1]})
            await asyncio.sleep(1)
            
            # Step 4: Cherry-pick commits
            picked_commits = []
            for i, commit in enumerate(commits):
                progress = 30 + int((i + 1) / len(commits) * 50)
                logs.append(f"[{datetime.now().isoformat()}] 🍒 Cherry-picking: {commit}")
                if on_progress:
                    await on_progress({"step": "cherry_pick", "progress": progress, "commit": commit, "log": logs[-1]})
                
                # 模拟可能的冲突
                if random.random() < 0.1:
                    logs.append(f"[{datetime.now().isoformat()}] ⚠️ 冲突检测: {commit} - 自动解决")
                    await asyncio.sleep(0.5)
                
                picked_commits.append(commit)
                await asyncio.sleep(1.5)
            
            # Step 5: 验证
            logs.append(f"[{datetime.now().isoformat()}] ✅ 验证cherry-pick结果")
            if on_progress:
                await on_progress({"step": "verify", "progress": 90, "log": logs[-1]})
            await asyncio.sleep(0.5)
            
            # Step 6: 完成
            logs.append(f"[{datetime.now().isoformat()}] 🎉 GlobalBatch完成! 成功pick {len(picked_commits)} commits")
            if on_progress:
                await on_progress({"step": "complete", "progress": 100, "log": logs[-1]})
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return SkillResult(
                success=True,
                data={
                    "branch": branch,
                    "picked_commits": picked_commits,
                    "total_commits": len(picked_commits)
                },
                logs=logs,
                duration_seconds=duration
            )
            
        except Exception as e:
            logs.append(f"[{datetime.now().isoformat()}] ❌ 错误: {str(e)}")
            return SkillResult(
                success=False,
                logs=logs,
                error=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )


class BuildWinSkill(MockSkill):
    """Windows构建技能"""
    
    def __init__(self):
        super().__init__(
            name="build_win",
            description="执行Windows平台构建"
        )
    
    async def execute(self, context: dict, on_progress: Optional[Callable] = None) -> SkillResult:
        logs = []
        start_time = datetime.now()
        
        try:
            project_dir = context.get("project_dir", ".")
            build_config = context.get("config", "Release")
            
            steps = [
                ("prepare", "准备构建环境", 10),
                ("cmake", "运行CMake配置", 25),
                ("compile", "编译源代码", 70),
                ("link", "链接目标文件", 85),
                ("package", "打包构建产物", 95),
                ("verify", "验证构建结果", 100),
            ]
            
            for step_id, step_name, progress in steps:
                logs.append(f"[{datetime.now().isoformat()}] 🔨 {step_name}")
                if on_progress:
                    await on_progress({"step": step_id, "progress": progress, "log": logs[-1]})
                
                # 模拟编译时间
                if step_id == "compile":
                    await asyncio.sleep(5)
                else:
                    await asyncio.sleep(1)
                
                # 模拟可能的编译警告
                if step_id == "compile" and random.random() < 0.3:
                    logs.append(f"[{datetime.now().isoformat()}] ⚠️ 编译警告: deprecated function usage")
            
            logs.append(f"[{datetime.now().isoformat()}] ✅ Windows构建完成")
            
            return SkillResult(
                success=True,
                data={
                    "platform": "windows",
                    "config": build_config,
                    "artifacts": ["app.exe", "app.pdb"]
                },
                logs=logs,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
            
        except Exception as e:
            logs.append(f"[{datetime.now().isoformat()}] ❌ 构建失败: {str(e)}")
            return SkillResult(
                success=False,
                logs=logs,
                error=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )


class BuildIOSSkill(MockSkill):
    """iOS构建技能 (macOS专用)"""
    
    def __init__(self):
        super().__init__(
            name="build_ios",
            description="执行iOS平台构建"
        )
    
    async def execute(self, context: dict, on_progress: Optional[Callable] = None) -> SkillResult:
        logs = []
        start_time = datetime.now()
        
        try:
            project_dir = context.get("project_dir", ".")
            scheme = context.get("scheme", "Minecraftpe")
            
            steps = [
                ("pod_install", "安装CocoaPods依赖", 15),
                ("xcode_build", "Xcode编译", 60),
                ("sign", "代码签名", 80),
                ("archive", "打包Archive", 95),
                ("verify", "验证IPA", 100),
            ]
            
            for step_id, step_name, progress in steps:
                logs.append(f"[{datetime.now().isoformat()}] 🍎 {step_name}")
                if on_progress:
                    await on_progress({"step": step_id, "progress": progress, "log": logs[-1]})
                
                if step_id == "xcode_build":
                    await asyncio.sleep(6)
                else:
                    await asyncio.sleep(1)
            
            logs.append(f"[{datetime.now().isoformat()}] ✅ iOS构建完成")
            
            return SkillResult(
                success=True,
                data={
                    "platform": "ios",
                    "scheme": scheme,
                    "artifacts": ["Minecraftpe.ipa", "Minecraftpe.dSYM"]
                },
                logs=logs,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
            
        except Exception as e:
            logs.append(f"[{datetime.now().isoformat()}] ❌ iOS构建失败: {str(e)}")
            return SkillResult(
                success=False,
                logs=logs,
                error=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )


class GitCommitSkill(MockSkill):
    """Git提交技能"""
    
    def __init__(self):
        super().__init__(
            name="git_commit",
            description="执行Git提交操作"
        )
    
    async def execute(self, context: dict, on_progress: Optional[Callable] = None) -> SkillResult:
        logs = []
        start_time = datetime.now()
        
        try:
            branch = context.get("branch", "netease/globalbatch/demo")
            message = context.get("message", "feat: GlobalBatch auto commit")
            
            logs.append(f"[{datetime.now().isoformat()}] 📝 Git status检查")
            if on_progress:
                await on_progress({"step": "status", "progress": 20, "log": logs[-1]})
            await asyncio.sleep(0.5)
            
            logs.append(f"[{datetime.now().isoformat()}] ➕ Git add .")
            if on_progress:
                await on_progress({"step": "add", "progress": 40, "log": logs[-1]})
            await asyncio.sleep(0.5)
            
            logs.append(f"[{datetime.now().isoformat()}] 💾 Git commit: {message}")
            if on_progress:
                await on_progress({"step": "commit", "progress": 60, "log": logs[-1]})
            await asyncio.sleep(1)
            
            logs.append(f"[{datetime.now().isoformat()}] 🚀 Git push origin {branch}")
            if on_progress:
                await on_progress({"step": "push", "progress": 90, "log": logs[-1]})
            await asyncio.sleep(1.5)
            
            commit_hash = f"{random.randint(1000000, 9999999):07x}"
            logs.append(f"[{datetime.now().isoformat()}] ✅ 提交成功: {commit_hash}")
            if on_progress:
                await on_progress({"step": "complete", "progress": 100, "log": logs[-1]})
            
            return SkillResult(
                success=True,
                data={
                    "branch": branch,
                    "commit_hash": commit_hash,
                    "message": message
                },
                logs=logs,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
            
        except Exception as e:
            logs.append(f"[{datetime.now().isoformat()}] ❌ Git操作失败: {str(e)}")
            return SkillResult(
                success=False,
                logs=logs,
                error=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )


class NotifySkill(MockSkill):
    """通知技能 - 通过POPO发送通知"""
    
    def __init__(self):
        super().__init__(
            name="notify",
            description="发送POPO/消息通知"
        )
    
    async def execute(self, context: dict, on_progress: Optional[Callable] = None) -> SkillResult:
        logs = []
        start_time = datetime.now()
        
        try:
            target = context.get("target", "team")
            message = context.get("message", "任务完成通知")
            notify_type = context.get("type", "popo")
            
            logs.append(f"[{datetime.now().isoformat()}] 📨 准备发送通知")
            if on_progress:
                await on_progress({"step": "prepare", "progress": 30, "log": logs[-1]})
            await asyncio.sleep(0.3)
            
            logs.append(f"[{datetime.now().isoformat()}] 📤 发送{notify_type}消息到 {target}")
            if on_progress:
                await on_progress({"step": "send", "progress": 70, "log": logs[-1]})
            await asyncio.sleep(0.5)
            
            logs.append(f"[{datetime.now().isoformat()}] ✅ 通知发送成功")
            if on_progress:
                await on_progress({"step": "complete", "progress": 100, "log": logs[-1]})
            
            return SkillResult(
                success=True,
                data={
                    "target": target,
                    "message": message,
                    "type": notify_type
                },
                logs=logs,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
            
        except Exception as e:
            logs.append(f"[{datetime.now().isoformat()}] ❌ 通知发送失败: {str(e)}")
            return SkillResult(
                success=False,
                logs=logs,
                error=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )


class ReviewSkill(MockSkill):
    """代码Review技能"""
    
    def __init__(self):
        super().__init__(
            name="review",
            description="执行自动代码审查"
        )
    
    async def execute(self, context: dict, on_progress: Optional[Callable] = None) -> SkillResult:
        logs = []
        start_time = datetime.now()
        
        try:
            branch = context.get("branch", "netease/globalbatch/demo")
            
            logs.append(f"[{datetime.now().isoformat()}] 🔍 开始代码审查: {branch}")
            if on_progress:
                await on_progress({"step": "start", "progress": 10, "log": logs[-1]})
            await asyncio.sleep(0.5)
            
            logs.append(f"[{datetime.now().isoformat()}] 📊 静态分析...")
            if on_progress:
                await on_progress({"step": "static_analysis", "progress": 40, "log": logs[-1]})
            await asyncio.sleep(2)
            
            logs.append(f"[{datetime.now().isoformat()}] 🧪 运行单元测试...")
            if on_progress:
                await on_progress({"step": "unit_test", "progress": 70, "log": logs[-1]})
            await asyncio.sleep(2)
            
            # 模拟Review结果
            issues = []
            if random.random() < 0.3:
                issues.append({"type": "warning", "file": "src/main.cpp", "message": "Potential null pointer"})
            
            logs.append(f"[{datetime.now().isoformat()}] ✅ Review完成: {len(issues)} issues")
            if on_progress:
                await on_progress({"step": "complete", "progress": 100, "log": logs[-1]})
            
            return SkillResult(
                success=True,
                data={
                    "branch": branch,
                    "issues": issues,
                    "passed": len(issues) == 0
                },
                logs=logs,
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
            
        except Exception as e:
            logs.append(f"[{datetime.now().isoformat()}] ❌ Review失败: {str(e)}")
            return SkillResult(
                success=False,
                logs=logs,
                error=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )


# ================== Skill Registry ==================

class SkillRegistry:
    """Skill注册表"""
    
    _skills: Dict[str, MockSkill] = {}
    
    @classmethod
    def register(cls, skill: MockSkill):
        cls._skills[skill.name] = skill
    
    @classmethod
    def get(cls, name: str) -> Optional[MockSkill]:
        return cls._skills.get(name)
    
    @classmethod
    def list_skills(cls) -> List[dict]:
        return [
            {"name": s.name, "description": s.description}
            for s in cls._skills.values()
        ]


# 注册所有Mock Skills
SkillRegistry.register(GlobalBatchSkill())
SkillRegistry.register(BuildWinSkill())
SkillRegistry.register(BuildIOSSkill())
SkillRegistry.register(GitCommitSkill())
SkillRegistry.register(NotifySkill())
SkillRegistry.register(ReviewSkill())

"""bot_server.service.codemaker 包。

通过 Codemaker SSE 远程遥控 CodeMaker 执行各类 skill 任务（pick/rebase/build_win/review）。

公共 API：
    run_skill_via_codemaker(task, db, codemaker_config)   主入口，按 task.type 分发

模块划分：
    base.py             公共常量、session_result 工具函数、校验逻辑
    process_manager.py  Codemaker 进程管理、Agent 发现、权限自动响应
    entry.py           DAG-aware Codemaker task entry；调用 cube.codemaker.run_task
    result_state.py    session_result、retry、后台 running 等待逻辑
    skill_runner.py     依赖注入分发核心，按 task type 调用对应 handler
    task_handlers/
        pick_handler.py      branch-dance 前处理与 prompt 构造
        rebase_handler.py    batch-rebase 前处理与 prompt 构造
        build_win_handler.py batch-fixbuild-windows 前处理与 prompt 构造
        review_handler.py    batch-review 前处理与 prompt 构造
"""

from .skill_runner import run_skill_via_codemaker

__all__ = ["run_skill_via_codemaker"]

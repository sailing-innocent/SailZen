"""Task handler 子包。

每个 handler 模块负责：
  1. 前处理：从 task/sub_batch/batch_config 提取所需字段
  2. 构造 extra_result（传递给 session_runner 和 session_result 校验）
  3. 构造 task-specific prompt 前缀
  4. 返回 (working_dir, prompt, extra_result) 供 skill_runner 统一调用

公共接口：handle(task, sub_batch, batch_config, db, spec, temp_dir, base_working_dir)
"""

from .pick_handler import handle as handle_pick
from .rebase_handler import handle as handle_rebase
from .build_win_handler import handle as handle_build_win
from .build_ios_handler import handle as handle_build_ios
from .review_handler import handle as handle_review

__all__ = [
    "handle_pick",
    "handle_rebase",
    "handle_build_win",
    "handle_review",
]

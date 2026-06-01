def _mock_result_for_task(task: dict) -> dict:
    """根据 Task 类型生成模拟结果。"""
    task_type = task.get("type", "")
    payload = task.get("payload") or {}
    base = {"mock": True, "runner": "mock_task_runner"}

    if task_type == "init_workspace":
        base.update({
            "initialized": True,
            "summary": "GlobalBatch workspace initialized (mock).",
            "predecessor_branch": payload.get("predecessor_branch", ""),
            "working_branch": payload.get("working_branch", ""),
            "work_dir": payload.get("work_dir", ""),
            "workspace_paths": payload.get("workspace_paths") or {},
        })
    elif task_type == "summary":
        commit_count = payload.get("commit_count", 0)
        branch = payload.get("branch_name", "")
        commits = payload.get("commits", [])
        first_short = commits[0]["short"] if commits else "?"
        last_short = commits[-1]["short"] if commits else "?"
        base["summary"] = (
            f"{commit_count} commits on {branch} "
            f"({first_short}..{last_short})"
        )
        base["commit_count"] = commit_count
        base["branch_name"] = branch
        base["commits"] = commits
    elif task_type == "report":
        deps = task.get("dependencies", [])
        base["report"] = f"All {len(deps)} reviews passed. Batch report generated."
    elif task_type == "ensure_worktree":
        variant = payload.get("variant", "main")
        branch = payload.get("branch_name", "")
        worktree_path = payload.get("worktree_path", "")
        base["worktree_ready"] = True
        base["variant"] = variant
        base["branch_name"] = branch
        base["worktree_path"] = worktree_path
        base["summary"] = f"Ensured {'buildfix' if variant == 'buildfix' else 'main'} worktree for {branch} (mock)"
    elif task_type == "pick":
        base["picked"] = True
    elif task_type.startswith("build_"):
        base["build_ok"] = True
        base["platform"] = "win" if "win" in task_type else "ios"
    elif task_type == "review":
        base["review_ok"] = True

    return base


# -*- coding: utf-8 -*-
"""
Kill Windows processes by PID
"""

import subprocess
import os
import sys


def kill_process_taskkill(pid: int) -> bool:
    """Try to kill process using taskkill command."""
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  Taskkill error: {e}")
        return False


def kill_process_os(pid: int) -> bool:
    """Fallback: kill process using os.kill()."""
    try:
        os.kill(pid, 9)  # SIGKILL
        return True
    except Exception as e:
        print(f"  os.kill error: {e}")
        return False


def kill_process(pid: int, description: str) -> dict:
    """Kill a process with taskkill, fallback to os.kill()."""
    print(f"\nKilling {description} (PID: {pid})...")

    # Try taskkill first
    if kill_process_taskkill(pid):
        print(f"  [OK] Success (taskkill)")
        return {"pid": pid, "success": True, "method": "taskkill"}

    print(f"  Taskkill failed, trying os.kill()...")

    # Fallback to os.kill
    if kill_process_os(pid):
        print(f"  [OK] Success (os.kill)")
        return {"pid": pid, "success": True, "method": "os.kill"}

    print(f"  [FAIL] Failed")
    return {"pid": pid, "success": False, "method": None}


def main():
    # Process list to kill
    processes = [
        (599372, "opencode on port 4098"),
        (602504, "opencode on port 4099"),
    ]

    print("=" * 50)
    print("Windows Process Termination Script")
    print("=" * 50)

    results = []
    for pid, desc in processes:
        result = kill_process(pid, desc)
        results.append(result)

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    for r in results:
        status = "[KILLED]" if r["success"] else "[FAILED]"
        method = f" ({r['method']})" if r["method"] else ""
        print(f"PID {r['pid']}: {status}{method}")

    # Exit code
    all_success = all(r["success"] for r in results)
    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    main()

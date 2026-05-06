"""OpenCode CLI Bridge — delegate coding tasks to opencode.

Survey-cli is NOT a coding agent. When coding is needed:
1. Write the task to a file
2. Invoke opencode cli as subprocess
3. Return result

This keeps survey-cli focused ONLY on surveys.
"""

import json
import os
import subprocess
import tempfile
import time
from typing import Dict, Any, Optional


def delegate_task(task: str, repo_path: Optional[str] = None,
                  timeout: int = 300, wait: bool = True) -> Dict[str, Any]:
    """Delegate a coding task to opencode cli.

    Creates a temporary task file and invokes:
        opencode < task_file.md

    Args:
        task: Natural language task description
        repo_path: Optional repo to work in (defaults to current)
        timeout: Max wait time in seconds
        wait: If True, wait for completion. If False, fire-and-forget.

    Returns:
        Dict with status, output, error
    """
    # Create task file
    task_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, prefix="survey_task_"
    )
    task_file.write(f"# Survey-CLI Delegated Task\n\n{task}\n")
    task_file.close()

    # Prepare command
    cwd = repo_path or os.getcwd()
    cmd = ["opencode", task_file.name]

    try:
        result = subprocess.run(
            cmd, cwd=cwd,
            capture_output=True, text=True,
            timeout=timeout if wait else 5,
        )

        # Clean up task file
        os.unlink(task_file.name)

        return {
            "status": "ok" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout": result.stdout[-1000:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
            "task": task[:200],
        }

    except subprocess.TimeoutExpired:
        # Fire-and-forget or timeout
        with open(task_file.name + ".pending", "w") as f:
            f.write(json.dumps({"task": task, "repo": cwd, "ts": time.time()}))

        return {
            "status": "running",
            "message": f"Task dispatched to opencode (timeout>{timeout}s)",
            "task_file": task_file.name + ".pending",
        }

    except FileNotFoundError:
        # opencode not installed
        return {
            "status": "error",
            "message": "opencode cli not found. Install with: npm install -g @opencode/cli",
        }


def check_pending_tasks():
    """Check for pending tasks that were dispatched."""
    pending_dir = tempfile.gettempdir()
    pending_files = []
    import glob
    for f in glob.glob(os.path.join(pending_dir, "survey_task_*.pending")):
        try:
            with open(f) as fh:
                data = json.load(fh)
            pending_files.append(data)
        except Exception:
            pass
    return pending_files


def submit_issue(title: str, body: str, repo: str = "SIN-CLIs/stealth-runner"):
    """Submit a GitHub issue via gh CLI.

    Used to report bugs or request features discovered during surveys.

    Args:
        title: Issue title
        body: Issue body
        repo: GitHub repo
    """
    try:
        # Create a temporary file for the issue body
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md",
                                          delete=False, prefix="issue_") as f:
            f.write(body)
            f.flush()

            result = subprocess.run(
                ["gh", "issue", "create",
                 "--repo", repo,
                 "--title", title,
                 "--body-file", f.name,
                 "--label", "automated,survey-cli"],
                capture_output=True, text=True, timeout=30
            )
            os.unlink(f.name)

        if result.returncode == 0:
            return {"status": "ok", "url": result.stdout.strip()}
        return {"status": "error", "message": result.stderr[:200]}

    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}

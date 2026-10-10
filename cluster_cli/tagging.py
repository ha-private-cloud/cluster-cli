import subprocess
import time
from pathlib import Path

BRANCH_TAG_PREFIXES = {
    "development": "DEV-",
    "preview": "PREVIEW-",
    "main": "",
}


def default_tag(app_dir: Path) -> str:
    """Tag for APP_DIR's current branch"""
    branch = _current_branch(app_dir)
    if branch not in BRANCH_TAG_PREFIXES:
        raise ValueError(
            f"branch {branch!r} has no tagging scheme (expected one of "
            f"{', '.join(BRANCH_TAG_PREFIXES)}) , pass --tag explicitly"
        )
    timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    return f"{BRANCH_TAG_PREFIXES[branch]}{timestamp}"


def _current_branch(app_dir: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(app_dir), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or result.stdout.strip() == "HEAD":
        raise ValueError(f"{app_dir} isn't on a resolvable git branch , pass --tag explicitly")
    return result.stdout.strip()

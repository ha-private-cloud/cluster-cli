import subprocess
import time
from pathlib import Path

# Each app repo's checked-out branch decides which "channel" its image tag
# belongs to: dev/preview builds are prefixed so environments only ever pick
# up their own channel's images (see clusterkeep-ui/tofu's image_tag_prefix);
# release builds get a plain, unprefixed tag.
BRANCH_TAG_PREFIXES = {
    "dev": "DEV-",
    "preview": "PREVIEW-",
    "main": "",
}


def default_tag(app_dir: Path) -> str:
    """Tag for APP_DIR's current branch, e.g. DEV-20260814120000. Raises
    ValueError if the branch isn't one cluster-ci's tagging scheme covers ,
    callers should fall back to requiring an explicit --tag in that case."""
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

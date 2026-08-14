import os
import tarfile
from pathlib import Path

import pathspec

# Applied regardless of .gitignore/.dockerignore contents. *.tfstate* matters
# most: app repos like clusterkeep-ui have live Terraform state sitting right
# next to their source, and it must never leave the machine in a build upload.
ALWAYS_EXCLUDE = [
    ".git/",
    ".venv/",
    "__pycache__/",
    "*.pyc",
    ".terraform/",
    "*.tfstate",
    "*.tfstate.*",
]


def _load_spec(app_dir: Path) -> pathspec.PathSpec:
    # Only .gitignore, deliberately not .dockerignore: .dockerignore controls
    # what goes into the *image* (Kaniko reads it itself from the extracted
    # workspace), which is a different concern from what needs to be
    # *uploaded* , e.g. clusterkeep-ui's .dockerignore excludes charts/
    # since the Dockerfile doesn't need it, but the deploy stage does.
    lines = list(ALWAYS_EXCLUDE)
    gitignore = app_dir / ".gitignore"
    if gitignore.exists():
        lines.extend(gitignore.read_text().splitlines())
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def build_tarball(app_dir: Path, dest: Path) -> Path:
    """Tar+gzip app_dir into dest, excluding anything matched by .gitignore
    plus ALWAYS_EXCLUDE. Prunes excluded directories during the walk rather
    than filtering every file after the fact."""
    app_dir = app_dir.resolve()
    spec = _load_spec(app_dir)

    with tarfile.open(dest, mode="w:gz") as tar:
        for root, dirnames, filenames in os.walk(app_dir):
            root_path = Path(root)
            rel_root = root_path.relative_to(app_dir)

            dirnames[:] = [d for d in dirnames if not spec.match_file(f"{rel_root / d}/")]

            for filename in filenames:
                rel_file = rel_root / filename
                if spec.match_file(str(rel_file)):
                    continue
                tar.add(root_path / filename, arcname=str(rel_file))

    return dest

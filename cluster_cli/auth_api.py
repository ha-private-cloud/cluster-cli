import json
import subprocess
from pathlib import Path

DEFAULT_NAMESPACE = "auth-prd-pub"
DEFAULT_DEPLOYMENT = "deploy/auth-api"


def _manage(args: list[str], *, kubeconfig_path: Path, namespace: str, deployment: str, stdin: str = "") -> dict | list:
    """Runs `python -m app.manage` in the auth-api pod; passwords go over stdin so they never reach `ps`."""
    command = [
        "kubectl",
        "--kubeconfig",
        str(kubeconfig_path),
        "-n",
        namespace,
        "exec",
        "-i",
        deployment,
        "--",
        "python",
        "-m",
        "app.manage",
        *args,
    ]
    try:
        result = subprocess.run(command, input=stdin, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as exc:
        raise RuntimeError("`kubectl` not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("timed out talking to the auth-api pod") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise RuntimeError(detail[-1] if detail else f"kubectl exec exited {result.returncode}")
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError) as exc:
        raise RuntimeError(f"unexpected output from auth-api:\n{result.stdout.strip()[-400:]}") from exc


def reset_password(
    username: str,
    password: str,
    *,
    kubeconfig_path: Path,
    namespace: str = DEFAULT_NAMESPACE,
    deployment: str = DEFAULT_DEPLOYMENT,
) -> str:
    user = _manage(
        ["set-password", username],
        kubeconfig_path=kubeconfig_path,
        namespace=namespace,
        deployment=deployment,
        stdin=password + "\n",
    )
    return f"{user['username']} ({user['email'] or 'no email'})"


def list_users(
    *,
    kubeconfig_path: Path,
    namespace: str = DEFAULT_NAMESPACE,
    deployment: str = DEFAULT_DEPLOYMENT,
) -> list[dict]:
    return _manage(["list-users"], kubeconfig_path=kubeconfig_path, namespace=namespace, deployment=deployment)

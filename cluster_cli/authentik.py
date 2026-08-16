import json
import subprocess
from pathlib import Path

DEFAULT_NAMESPACE = "cluster-auth"
DEFAULT_DEPLOYMENT = "deploy/authentik-server"


def _ak_shell(script: str, *, kubeconfig_path: Path, namespace: str, deployment: str) -> str:
    """Runs a Python snippet inside Authentik's Django shell.

    The script goes in on stdin rather than via `ak shell -c`, so passwords
    never appear in the pod's process arguments (anyone with exec access could
    otherwise read them out of `ps`).
    """
    args = [
        "kubectl",
        "--kubeconfig",
        str(kubeconfig_path),
        "-n",
        namespace,
        "exec",
        "-i",
        deployment,
        "--",
        "ak",
        "shell",
    ]
    try:
        result = subprocess.run(args, input=script, capture_output=True, text=True, timeout=180)
    except FileNotFoundError as exc:
        raise RuntimeError("`kubectl` not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("timed out talking to the authentik pod") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise RuntimeError(detail[-1] if detail else f"kubectl exec exited {result.returncode}")
    return result.stdout


# Markers let us pick our own output out of the Django shell's banner and any
# logging the pod writes to the same stream.
_OK = "__CLUSTER_CLI_OK__"
_ERR = "__CLUSTER_CLI_ERR__"


def _parse(output: str) -> str:
    for line in output.splitlines():
        line = line.strip()
        if line.startswith(_ERR):
            raise RuntimeError(line[len(_ERR) :].strip())
        if line.startswith(_OK):
            return line[len(_OK) :].strip()
    raise RuntimeError(f"unexpected output from authentik shell:\n{output.strip()[-400:]}")


def reset_password(
    username: str,
    password: str,
    *,
    kubeconfig_path: Path,
    namespace: str = DEFAULT_NAMESPACE,
    deployment: str = DEFAULT_DEPLOYMENT,
) -> str:
    """Sets a user's password directly, the way `ak` itself would.

    set_password() applies Authentik's configured hashers and validators, so
    this is not a shortcut around password policy , it is the same path the
    admin UI uses.
    """
    script = f"""
from authentik.core.models import User
username = {json.dumps(username)}
password = {json.dumps(password)}
user = User.objects.filter(username=username).first()
if user is None:
    print({json.dumps(_ERR)} + " no user named " + username)
else:
    user.set_password(password)
    user.save()
    print({json.dumps(_OK)} + " " + user.username + " (" + (user.email or "no email") + ")")
"""
    return _parse(_ak_shell(script, kubeconfig_path=kubeconfig_path, namespace=namespace, deployment=deployment))


def list_users(
    *,
    kubeconfig_path: Path,
    namespace: str = DEFAULT_NAMESPACE,
    deployment: str = DEFAULT_DEPLOYMENT,
) -> list[dict]:
    """Lists users, so you don't have to guess the exact username."""
    script = f"""
import json
from authentik.core.models import User
rows = [
    {{"username": u.username, "name": u.name, "email": u.email, "active": u.is_active}}
    for u in User.objects.all().order_by("username")
]
print({json.dumps(_OK)} + " " + json.dumps(rows))
"""
    return json.loads(
        _parse(_ak_shell(script, kubeconfig_path=kubeconfig_path, namespace=namespace, deployment=deployment))
    )

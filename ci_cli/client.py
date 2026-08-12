from pathlib import Path

import requests


class RunnerClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}

    def submit_build(self, app_name: str, tag: str, namespace: str, tarball_path: Path) -> dict:
        with open(tarball_path, "rb") as fh:
            resp = requests.post(
                f"{self.base_url}/builds",
                headers=self._headers,
                data={"app": app_name, "tag": tag, "namespace": namespace},
                files={"source": (tarball_path.name, fh, "application/gzip")},
                timeout=120,
                # Every *.talos.lab host sits behind ingress-nginx's self-signed
                # default cert (see cluster-config/README.md) — same reasoning
                # Headlamp/Kaniko/every other in-cluster client skips verification.
                verify=False,
            )
        resp.raise_for_status()
        return resp.json()

    def get_build(self, build_id: str) -> dict:
        resp = requests.get(
            f"{self.base_url}/builds/{build_id}", headers=self._headers, timeout=30, verify=False
        )
        resp.raise_for_status()
        return resp.json()

    def stream_logs(self, build_id: str):
        """Yields (event, data) pairs parsed from the runner's SSE stream."""
        with requests.get(
            f"{self.base_url}/builds/{build_id}/logs",
            headers=self._headers,
            stream=True,
            timeout=None,
            verify=False,
        ) as resp:
            resp.raise_for_status()
            event = None
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                if raw_line.startswith("event:"):
                    event = raw_line.removeprefix("event:").strip()
                elif raw_line.startswith("data:"):
                    data = raw_line.removeprefix("data:").strip()
                    yield event, data
                    event = None

import os
import sys
from urllib.parse import urlparse
import httpx
from rootmap_client.scripts.host import SystemCollector

HEAD_NODE_URL = os.environ.get("ROOTMAP_HEAD_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN_FILE = os.environ.get("ROOTMAP_TOKEN_FILE", "/etc/rootmap/token")
TIMEOUT_SECONDS = 10
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

class ClientError(Exception):
    """A failure with a message safe to show the user. Never contains the token."""

def check_url(base_url: str) -> None:
    """Require HTTPS, except for localhost or an explicit ROOTMAP_ALLOW_INSECURE=1."""
    parsed = urlparse(base_url)
    if parsed.scheme == "https": return
    if parsed.scheme == "http" and (parsed.hostname in LOCAL_HOSTS or os.environ.get("ROOTMAP_ALLOW_INSECURE") == "1"): return
    raise ClientError(
        f"ROOTMAP_HEAD_URL must use https. Plain http is allowed only for localhost "
        f"or with ROOTMAP_ALLOW_INSECURE=1 (got {base_url!r})."
    )

def load_token(path: str) -> str:
    try:
        st = os.stat(path)
    except FileNotFoundError:
        raise ClientError(f"Token file not found: {path}. Ask an admin to provision this host.")
    except OSError as exc:
        raise ClientError(f"Cannot access token file {path}: {exc.strerror}")

    if st.st_mode & 0o077:
        print(f"warning: {path} is readable by other users; it should be mode 600.", file=sys.stderr)

    try:
        with open(path) as f:
            token = f.read().strip()
    except OSError as exc:
        raise ClientError(f"Cannot read token file {path}: {exc.strerror}")

    if not token:
        raise ClientError(f"Token file {path} is empty.")
    return token

def generate_report() -> dict[str, str]:
    return SystemCollector().get_system_info()

def send_report(base_url: str, token: str, system_info: dict[str, str]) -> int:
    """POST the report and return the scan id the server assigned."""
    try:
        response = httpx.post(
            f"{base_url}/reports",
            json=system_info,
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise ClientError(f"Could not reach {base_url}: {type(exc).__name__}.")

    if response.status_code == 201:
        return response.json()["scan_id"]
    if response.status_code == 401:
        raise ClientError(
            "Server rejected the token (401). It may be revoked or expired; "
            "ask an admin to rotate it."
        )
    if response.status_code == 403:
        raise ClientError("Token is valid but not permitted to send reports (403).")
    if response.status_code == 422:
        raise ClientError(f"Server rejected the report (422): {response.text[:500]}")
    raise ClientError(f"Unexpected response from server: {response.status_code}.")

def main() -> int:
    try:
        check_url(HEAD_NODE_URL)
        token = load_token(TOKEN_FILE)
        report = generate_report()
        scan_id = send_report(HEAD_NODE_URL, token, report)
    except ClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Report accepted (scan {scan_id}).")
    return 0

if __name__ == "__main__":
    sys.exit(main())

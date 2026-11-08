"""SSH provisioning of host tokens (run by an admin, from the server).

Safety rules:
  * Host keys are checked against the system known_hosts.
  * The token is sent over the SSH channel's stdin, never in a command string.
  * The remote path must be absolute and made of safe characters before it's
    used in a command.

Reqs: paramiko, plus SSH access to the host with an admin account.
"""

import hashlib
import re
import shlex
from dataclasses import dataclass
import paramiko
from src.auth.auth import issue_token, revoke_other_tokens

DEFAULT_TOKEN_PATH = "/etc/rootmap/token"
CONNECT_TIMEOUT_SECONDS = 10
_SAFE_PATH = re.compile(r"^/[A-Za-z0-9._/-]+$")

class ProvisionError(Exception):
    """Provisioning failed. Messages never contain the token."""

@dataclass(frozen=True)
class SSHTarget:
    host: str
    port: int
    user: str
    key_filename: str | None = None

@dataclass(frozen=True)
class InstallSpec:
    token_path: str = DEFAULT_TOKEN_PATH
    client_user: str | None = None 

def _validate_path(path: str) -> str:
    """Validates a path for use in a shell command."""
    if not _SAFE_PATH.match(path) or ".." in path.split("/"):
        raise ProvisionError(f"Unsafe token path: {path!r}")
    return path

def _connect(target: SSHTarget) -> paramiko.SSHClient:
    """Open an SSH connection that rejects unknown or changed host keys."""
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(
            target.host,
            port=target.port,
            username=target.user,
            key_filename=target.key_filename,
            timeout=CONNECT_TIMEOUT_SECONDS,
            banner_timeout=CONNECT_TIMEOUT_SECONDS,
        )
    except paramiko.SSHException as exc:
        client.close()
        raise ProvisionError(f"SSH connection to {target.host} failed: {exc}") from None
    except OSError as exc:
        client.close()
        raise ProvisionError(f"Could not reach {target.host}:{target.port}: {exc}") from None
    return client

def _run(client: paramiko.SSHClient, command: str, stdin_data: bytes | None = None) -> bytes:
    """Run a remote command, and return its stdout."""
    stdin, stdout, stderr = client.exec_command(command)
    if stdin_data is not None:
        stdin.write(stdin_data)
        stdin.channel.shutdown_write()
    status = stdout.channel.recv_exit_status()
    if status != 0:
        err = stderr.read().decode(errors="replace").strip()
        raise ProvisionError(f"Remote command failed (exit {status}): {err}")
    return stdout.read()

def _install_command(spec: InstallSpec) -> str:
    """Build the remote shell command that writes the token file with priv permissions."""
    path = _validate_path(spec.token_path)
    directory = path.rsplit("/", 1)[0] or "/"
    tmp = f"{path}.tmp"
    owner = f"-o {shlex.quote(spec.client_user)} " if spec.client_user else ""
    chown = f"chown {shlex.quote(spec.client_user)} {shlex.quote(tmp)} && " if spec.client_user else ""
    return (
        "umask 077 && "
        f"install -d -m 700 {owner}{shlex.quote(directory)} && "
        f"cat > {shlex.quote(tmp)} && "
        f"chmod 600 {shlex.quote(tmp)} && "
        f"{chown}"
        f"mv {shlex.quote(tmp)} {shlex.quote(path)}"
    )

def install_token(target: SSHTarget, token: str, spec: InstallSpec = InstallSpec()) -> None:
    """Write token to the host, then confirm the file's hash matches it."""
    client = _connect(target)
    try:
        _run(client, _install_command(spec), stdin_data=token.encode("utf-8"))

        path = shlex.quote(_validate_path(spec.token_path))
        remote_hash = _run(client, f"sha256sum {path} | cut -d' ' -f1").decode().strip()
        if remote_hash != hashlib.sha256(token.encode("utf-8")).hexdigest():
            raise ProvisionError("Token on host does not match the one issued.")
    finally:
        client.close()


def _host_for_provisioning(connection, host_id: int) -> dict:
    """Look up an active host's address and SSH port, or raise ProvisionError."""
    row = connection.execute(
        "SELECT host_ip, ssh_port FROM hosts WHERE host_id = %s AND is_active",
        (host_id,),
    ).fetchone()
    if row is None:
        raise ProvisionError(f"Host {host_id} does not exist or is inactive.")
    return row

def provision_host(connection, host_id: int, *, ssh_user: str, key_filename: str | None = None, spec: InstallSpec = InstallSpec(),
) -> None:
    """First-time setup: issue and install a token. Refuses if one already exists."""
    host = _host_for_provisioning(connection, host_id)
    active = connection.execute(
        "SELECT count(*) AS n FROM host_tokens "
        "WHERE host_id = %s AND NOT is_revoked "
        "AND (expires_at IS NULL OR expires_at > now())",
        (host_id,),
    ).fetchone()["n"]
    if active:
        raise ProvisionError(f"Host {host_id} already has an active token. Use rotate instead.")

    target = SSHTarget(host["host_ip"], host["ssh_port"], ssh_user, key_filename)
    try:
        token = issue_token(connection, host_id)
        install_token(target, token, spec)
    except Exception:
        connection.rollback()
        raise
    connection.commit()

def rotate_host_token(connection, host_id: int, *, ssh_user: str, key_filename: str | None = None, spec: InstallSpec = InstallSpec(),
) -> None:
    """Issue a new token and install it. The old tokens are revoked only after
    the new one is confirmed on the host."""
    host = _host_for_provisioning(connection, host_id)
    target = SSHTarget(host["host_ip"], host["ssh_port"], ssh_user, key_filename)
    try:
        new_token = issue_token(connection, host_id)
        install_token(target, new_token, spec)
        revoke_other_tokens(connection, host_id, keep_token=new_token)
    except Exception:
        connection.rollback() 
        raise
    connection.commit()

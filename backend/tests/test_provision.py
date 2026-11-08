"""SSH provisioning. paramiko is replaced by a fake, so no real SSH server is needed.

DB-backed tests use the `db` fixture (TEST_DATABASE_URL). The rest run anywhere.
"""

import hashlib

import paramiko
import pytest

from src.auth import authenticate, hash_token
from src.auth import provision as prov
from src.auth.provision import (
    InstallSpec,
    ProvisionError,
    _install_command,
    provision_host,
    rotate_host_token,
)


class FakeSSHClient:
    """Stands in for paramiko.SSHClient. Class-level state is reset per test."""

    fail_install = False
    corrupt_hash = False
    policy = None
    loaded_system_keys = False
    commands: list[str] = []
    written: list[bytes] = []  # everything sent on stdin, in order

    def __init__(self):
        pass

    def load_system_host_keys(self):
        FakeSSHClient.loaded_system_keys = True

    def set_missing_host_key_policy(self, policy):
        FakeSSHClient.policy = policy

    def connect(self, *args, **kwargs):
        pass

    def exec_command(self, command):
        FakeSSHClient.commands.append(command)
        if command.startswith("umask"):
            status = 1 if FakeSSHClient.fail_install else 0
            stdin = _Stream(_Channel(status), sink=FakeSSHClient.written)
            stderr = _Stream(_Channel(0), data=b"install: permission denied" if status else b"")
            return stdin, _Stream(_Channel(status)), stderr
        if command.startswith("sha256sum"):
            content = FakeSSHClient.written[-1] if FakeSSHClient.written else b""
            digest = "0" * 64 if FakeSSHClient.corrupt_hash else hashlib.sha256(content).hexdigest()
            return _Stream(_Channel(0)), _Stream(_Channel(0), data=f"{digest}\n".encode()), _Stream(_Channel(0))
        raise AssertionError(f"unexpected command: {command}")

    def close(self):
        pass


class _Channel:
    def __init__(self, status):
        self._status = status

    def recv_exit_status(self):
        return self._status

    def shutdown_write(self):
        pass


class _Stream:
    def __init__(self, channel, data=b"", sink=None):
        self.channel = channel
        self._data = data
        self._sink = sink

    def write(self, data):
        self._sink.append(data)

    def read(self):
        return self._data


@pytest.fixture
def fake_ssh(monkeypatch):
    FakeSSHClient.fail_install = False
    FakeSSHClient.corrupt_hash = False
    FakeSSHClient.policy = None
    FakeSSHClient.loaded_system_keys = False
    FakeSSHClient.commands = []
    FakeSSHClient.written = []
    monkeypatch.setattr(prov.paramiko, "SSHClient", FakeSSHClient)
    return FakeSSHClient


def add_host(conn, *, active=True) -> int:
    host_id = conn.execute(
        """
        INSERT INTO hosts (host_name, host_ip, collection_interval, is_active)
        VALUES ('web01', '10.0.0.5', 300, %s) RETURNING host_id
        """,
        (active,),
    ).fetchone()["host_id"]
    conn.commit()
    return host_id


def token_count(conn, host_id) -> int:
    return conn.execute(
        "SELECT count(*) AS n FROM host_tokens WHERE host_id = %s", (host_id,)
    ).fetchone()["n"]


# --- SSH safety (no DB) ------------------------------------------------------


def test_host_keys_are_checked_and_unknown_keys_rejected(fake_ssh):
    prov._connect(prov.SSHTarget("10.0.0.5", 22, "admin"))

    assert fake_ssh.loaded_system_keys is True
    assert isinstance(fake_ssh.policy, paramiko.RejectPolicy)
    assert not isinstance(fake_ssh.policy, paramiko.AutoAddPolicy)


def test_token_is_sent_on_stdin_never_in_a_command(fake_ssh):
    token = "super-secret-token-value"

    prov.install_token(prov.SSHTarget("10.0.0.5", 22, "admin"), token)

    assert fake_ssh.written == [token.encode()]
    assert all(token not in cmd for cmd in fake_ssh.commands)


def test_install_command_is_atomic_and_private():
    cmd = _install_command(InstallSpec())

    assert cmd.startswith("umask 077 && ")
    assert "install -d -m 700 /etc/rootmap" in cmd
    assert "chmod 600 /etc/rootmap/token.tmp" in cmd
    assert cmd.endswith("mv /etc/rootmap/token.tmp /etc/rootmap/token")


def test_client_user_owns_the_token_file_and_directory():
    cmd = _install_command(InstallSpec(client_user="rootmap"))

    assert "install -d -m 700 -o rootmap /etc/rootmap" in cmd
    assert "chown rootmap /etc/rootmap/token.tmp" in cmd


@pytest.mark.parametrize(
    "path",
    ["/etc/rootmap/../shadow", "/etc/x;rm -rf /", "relative/token", "/tmp/$(whoami)"],
)
def test_unsafe_token_paths_are_rejected(path):
    with pytest.raises(ProvisionError):
        _install_command(InstallSpec(token_path=path))


# --- provisioning (DB) -------------------------------------------------------


@pytest.mark.db
def test_provision_installs_token_and_stores_only_its_hash(db, fake_ssh):
    host_id = add_host(db)

    provision_host(db, host_id, ssh_user="admin")

    token = fake_ssh.written[-1].decode()
    stored = db.execute(
        "SELECT token_hash FROM host_tokens WHERE host_id = %s", (host_id,)
    ).fetchall()
    assert [r["token_hash"] for r in stored] == [hash_token(token)]
    assert token not in [r["token_hash"] for r in stored]
    assert authenticate(db, token) is not None


@pytest.mark.db
def test_failed_install_leaves_no_token_behind(db, fake_ssh):
    host_id = add_host(db)
    fake_ssh.fail_install = True

    with pytest.raises(ProvisionError):
        provision_host(db, host_id, ssh_user="admin")

    assert token_count(db, host_id) == 0


@pytest.mark.db
def test_hash_mismatch_leaves_no_token_behind(db, fake_ssh):
    host_id = add_host(db)
    fake_ssh.corrupt_hash = True

    with pytest.raises(ProvisionError, match="does not match"):
        provision_host(db, host_id, ssh_user="admin")

    assert token_count(db, host_id) == 0


@pytest.mark.db
def test_provision_refuses_when_an_active_token_exists(db, fake_ssh):
    host_id = add_host(db)
    provision_host(db, host_id, ssh_user="admin")

    with pytest.raises(ProvisionError, match="rotate"):
        provision_host(db, host_id, ssh_user="admin")


@pytest.mark.db
def test_inactive_host_is_refused(db, fake_ssh):
    host_id = add_host(db, active=False)

    with pytest.raises(ProvisionError, match="inactive"):
        provision_host(db, host_id, ssh_user="admin")

    assert fake_ssh.written == []


@pytest.mark.db
def test_rotation_keeps_old_token_until_new_one_is_installed(db, fake_ssh):
    host_id = add_host(db)
    provision_host(db, host_id, ssh_user="admin")
    old_token = fake_ssh.written[-1].decode()

    fake_ssh.corrupt_hash = True
    with pytest.raises(ProvisionError):
        rotate_host_token(db, host_id, ssh_user="admin")
    assert authenticate(db, old_token) is not None  # still valid: rotation failed

    fake_ssh.corrupt_hash = False
    rotate_host_token(db, host_id, ssh_user="admin")
    new_token = fake_ssh.written[-1].decode()

    assert authenticate(db, old_token) is None
    assert authenticate(db, new_token) is not None
    assert new_token != old_token

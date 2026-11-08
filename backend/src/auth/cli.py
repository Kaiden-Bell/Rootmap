"""Admin CLI for host tokens. Run on the server, from backend/.

Commands:
    grant   first-time token setup for a host. Creates a token and installs it
            on the host over SSH. Fails if the host already has an active token.
    rotate  replaces the host's token. The old token keeps working until the new
            one is installed and verified, then it's revoked.
    revoke  revokes every token for the host. Nothing is installed on the host,
            so the host's copy stops working once revoked.

Options (grant and rotate):
    --host-id      the hosts.host_id row to act on (required, all commands)
    --ssh-user     admin account on the host (required)
    --key          SSH private key file (default: ssh-agent or ~/.ssh keys)
    --token-path   where the token is written on the host
                   (default /etc/rootmap/token)
    --client-user  account that owns the token file on the host (optional)

Examples (run from backend/):
    uv run python -m src.auth.cli grant  --host-id 1 --ssh-user admin --key ~/.ssh/id_ed25519
    uv run python -m src.auth.cli rotate --host-id 1 --ssh-user admin
    uv run python -m src.auth.cli revoke --host-id 1

"""

import argparse
import sys
from src.auth.auth import revoke_host_tokens
from src.auth.provision import (
    DEFAULT_TOKEN_PATH,
    InstallSpec,
    ProvisionError,
    provision_host,
    rotate_host_token,
)
from src.db.connection import get_connection

def build_parser() -> argparse.ArgumentParser:
    """Define the grant, rotate and revoke subcommands and their options."""
    parser = argparse.ArgumentParser(
        prog="python -m src.auth.cli",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("grant", "rotate", "revoke"):
        p = sub.add_parser(name)
        p.add_argument("--host-id", type=int, required=True)
        if name == "revoke":
            continue
        p.add_argument("--ssh-user", required=True, help="admin account on the host")
        p.add_argument("--key", dest="key_filename", help="SSH private key (default: agent/keys)")
        p.add_argument("--token-path", default=DEFAULT_TOKEN_PATH, help="where the token lands on the host")
        p.add_argument("--client-user", help="account that owns the token file on the host")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one admin command and return the process exit code (0 success, 1 error)."""
    args = build_parser().parse_args(argv)

    try:
        with get_connection() as connection:
            if args.command == "revoke":
                revoke_host_tokens(connection, args.host_id)
                connection.commit()
                print(f"Removed all tokens for host {args.host_id}.")
                return 0

            spec = InstallSpec(token_path=args.token_path, client_user=args.client_user)
            action = provision_host if args.command == "grant" else rotate_host_token
            action(
                connection,
                args.host_id,
                ssh_user=args.ssh_user,
                key_filename=args.key_filename,
                spec=spec,
            )
    except ProvisionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"{args.command}: token installed on host {args.host_id} at {args.token_path}.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

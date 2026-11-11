#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Exchange Claude and Codex project memory with an SSH host."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import sync_claude_memory as sync


def transfer_commands(
    endpoint: str, port: int, local_home: Path, remote_home: Path, dry_run: bool
) -> list[tuple[str, list[str]]]:
    """Build four exports, reading Claude sources before reverse exports."""
    script = Path(__file__).with_name("sync_claude_memory.py")
    commands = []
    for direction in ("claude-to-codex", "codex-to-claude"):
        for outbound in (True, False):
            source, destination = (
                (local_home, remote_home) if outbound else (remote_home, local_home)
            )
            command = [
                sys.executable,
                str(script),
                "--direction",
                direction,
                "--target-ssh" if outbound else "--source-ssh",
                endpoint,
                "--ssh-port",
                str(port),
                "--path-map",
                f"{source}={destination}",
            ]
            if direction == "codex-to-claude":
                command.append("--create-projects")
            if dry_run:
                command.append("--dry-run")
            label = f"{'Local → remote' if outbound else 'Remote → local'}: {direction}"
            commands.append((label, command))
    return commands


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="SSH host or USER@HOST")
    parser.add_argument("--ssh-port", type=int, default=22)
    parser.add_argument(
        "--dry-run", action="store_true", help="preview destination changes"
    )
    args = parser.parse_args()
    sync.validate_remote_args(
        argparse.Namespace(
            source_ssh=args.host, target_ssh=None, ssh_port=args.ssh_port
        )
    )
    host_home = sync.remote_home(args.host, args.ssh_port)
    print(f"Project paths: {Path.home()} ↔ {host_home}", flush=True)
    for label, command in transfer_commands(
        args.host, args.ssh_port, Path.home(), host_home, args.dry_run
    ):
        print(f"\n{label}", flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""OpenVPN 3 session helpers."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path


def _run_openvpn3(
    args: list[str],
    stdin: str | None = None,
    on_output: Callable[[str], None] | None = None,
) -> tuple[int, str]:
    proc = subprocess.Popen(
        ["openvpn3", *args],
        stdin=subprocess.PIPE if stdin is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if stdin is not None:
        assert proc.stdin is not None
        proc.stdin.write(stdin)
        proc.stdin.close()

    assert proc.stdout is not None
    lines: list[str] = []
    for line in proc.stdout:
        lines.append(line)
        if on_output is not None:
            on_output(line)

    return proc.wait(), "".join(lines)


def list_config_paths_by_name(config_name: str) -> list[str]:
    """Return configuration object paths for profiles matching ``config_name``."""
    code, output = _run_openvpn3(["configs-list", "--json"])
    if code != 0:
        return []
    try:
        profiles = json.loads(output)
    except json.JSONDecodeError:
        return []
    return [path for path, profile in profiles.items() if profile.get("name") == config_name]


def remove_config(
    config_name: str,
    on_output: Callable[[str], None] | None = None,
) -> tuple[int, str]:
    """Remove all configuration profiles with the given name."""
    if session_is_active(config_name):
        disconnect_code, disconnect_output = disconnect_session(config_name)
        if disconnect_code != 0:
            return disconnect_code, disconnect_output

    paths = list_config_paths_by_name(config_name)
    if not paths:
        return 0, ""

    combined_output: list[str] = []
    for path in paths:
        code, output = _run_openvpn3(
            ["config-remove", "--path", path, "--force"],
            on_output=on_output,
        )
        combined_output.append(output)
        if code != 0:
            return code, "".join(combined_output)
    return 0, "".join(combined_output)


def import_config(
    ovpn_path: str | Path,
    config_name: str,
    on_output: Callable[[str], None] | None = None,
) -> tuple[int, str]:
    """Import an .ovpn file as a persistent OpenVPN 3 configuration profile."""
    paths = list_config_paths_by_name(config_name)
    if paths:
        if on_output is not None:
            count = len(paths)
            noun = "profile" if count == 1 else "profiles"
            on_output(f"Removing {count} existing {noun} named '{config_name}'...\n")
        remove_code, remove_output = remove_config(config_name, on_output=on_output)
        if remove_code != 0:
            return remove_code, remove_output

    path = Path(ovpn_path)
    return _run_openvpn3(
        [
            "config-import",
            "--config",
            str(path),
            "--name",
            config_name,
            "--persistent",
        ],
        on_output=on_output,
    )


def start_session(
    config_name: str,
    username: str,
    password: str,
    on_output: Callable[[str], None] | None = None,
) -> tuple[int, str]:
    """Start an OpenVPN 3 session in the background, piping credentials on stdin."""
    return _run_openvpn3(
        ["session-start", "--config", config_name, "--background"],
        stdin=f"{username}\n{password}\n",
        on_output=on_output,
    )


def disconnect_session(config_name: str) -> tuple[int, str]:
    """Disconnect a running VPN session."""
    return _run_openvpn3(["session-manage", "--config", config_name, "--disconnect"])


def restart_session(config_name: str) -> tuple[int, str]:
    """Disconnect and reconnect a running VPN session."""
    return _run_openvpn3(["session-manage", "--config", config_name, "--restart"])


def get_session_stats(config_name: str) -> tuple[int, str]:
    """Fetch live statistics for a running VPN session."""
    return _run_openvpn3(["session-stats", "--config", config_name])


def session_is_active(config_name: str) -> bool:
    code, _ = get_session_stats(config_name)
    return code == 0


_CREATED_RE = re.compile(r"Created:\s*(.+?)(?:\s+PID:|\s*$)", re.MULTILINE)
_CONFIG_NAME_RE = re.compile(r"Config name:\s*(.+)", re.MULTILINE)
_CREATED_FMT = "%a %b %d %H:%M:%S %Y"


def _parse_session_blocks(output: str) -> list[str]:
    return [block for block in re.split(r"-{20,}", output) if block.strip()]


def _config_name_matches(listed_name: str, config_name: str) -> bool:
    listed_name = listed_name.strip()
    if listed_name == config_name:
        return True
    # Renamed profiles: "newname (was: oldname)"
    return f"(was: {config_name})" in listed_name


def get_session_started_at(config_name: str) -> datetime | None:
    """Return when the running session was created, from ``openvpn3 sessions-list``."""
    code, output = _run_openvpn3(["sessions-list"])
    if code != 0:
        return None

    for block in _parse_session_blocks(output):
        config_match = _CONFIG_NAME_RE.search(block)
        if config_match is None or not _config_name_matches(config_match.group(1), config_name):
            continue
        created_match = _CREATED_RE.search(block)
        if created_match is None:
            continue
        try:
            return datetime.strptime(created_match.group(1).strip(), _CREATED_FMT)
        except ValueError:
            continue
    return None

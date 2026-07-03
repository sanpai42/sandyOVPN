"""OpenVPN 3 session helpers."""

from __future__ import annotations

import json
import re
import subprocess
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from sandyvpn.errors import OpenVpn3NotFoundError, OpenVpn3TimeoutError

DEFAULT_TIMEOUT_SEC = 30.0
SESSION_START_TIMEOUT_SEC = 120.0

_CREATED_RE = re.compile(r"Created:\s*(.+?)(?:\s+PID:|\s*$)", re.MULTILINE)
_CONFIG_NAME_RE = re.compile(r"Config name:\s*(.+)", re.MULTILINE)
_CREATED_FMT = "%a %b %d %H:%M:%S %Y"


def _run_openvpn3(
    args: list[str],
    stdin: str | None = None,
    on_output: Callable[[str], None] | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> tuple[int, str]:
    try:
        proc = subprocess.Popen(
            ["openvpn3", *args],
            stdin=subprocess.PIPE if stdin is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise OpenVpn3NotFoundError("Could not find the openvpn3 command.") from exc

    if stdin is not None:
        assert proc.stdin is not None
        proc.stdin.write(stdin)
        proc.stdin.close()

    assert proc.stdout is not None
    lines: list[str] = []
    stderr_chunks: list[str] = []
    read_done = threading.Event()

    def read_stdout() -> None:
        try:
            for line in proc.stdout:
                lines.append(line)
                if on_output is not None:
                    on_output(line)
        finally:
            read_done.set()

    def read_stderr() -> None:
        if proc.stderr is None:
            return
        stderr_chunks.append(proc.stderr.read())

    reader = threading.Thread(target=read_stdout, daemon=True)
    stderr_reader = threading.Thread(target=read_stderr, daemon=True)
    reader.start()
    stderr_reader.start()

    try:
        returncode = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        reader.join(timeout=1)
        stderr_reader.join(timeout=1)
        raise OpenVpn3TimeoutError(f"openvpn3 {' '.join(args)} timed out after {timeout:.0f}s")

    reader.join(timeout=timeout)
    stderr_reader.join(timeout=timeout)
    if not read_done.is_set():
        proc.kill()
        raise OpenVpn3TimeoutError(f"openvpn3 {' '.join(args)} timed out while reading output")

    output = "".join(lines)
    stderr = "".join(stderr_chunks)
    if stderr:
        output = f"{output}{stderr}"
    return returncode, output


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
        timeout=SESSION_START_TIMEOUT_SEC,
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


def _config_name_matches(listed_name: str, config_name: str) -> bool:
    listed_name = listed_name.strip()
    if listed_name == config_name:
        return True
    return f"(was: {config_name})" in listed_name


def _parse_session_blocks(output: str) -> list[str]:
    return [block for block in re.split(r"-{20,}", output) if block.strip()]


def _session_name_from_mapping(session: dict[str, object]) -> str | None:
    for key in ("config_name", "config name", "Config name", "name"):
        value = session.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_created_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return datetime.strptime(text, _CREATED_FMT)
    except ValueError:
        return None


def _created_from_session(session: dict[str, object]) -> datetime | None:
    for key in ("created", "Created", "session_created", "start_time", "started"):
        if key in session:
            parsed = _parse_created_timestamp(session[key])
            if parsed is not None:
                return parsed
    return None


def _normalize_sessions_json(data: object) -> list[dict[str, object]]:
    if isinstance(data, dict):
        sessions: list[dict[str, object]] = []
        for key, value in data.items():
            if isinstance(value, dict):
                session = dict(value)
                session.setdefault("path", key)
                sessions.append(session)
        return sessions
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _list_sessions() -> list[dict[str, object]]:
    code, output = _run_openvpn3(["sessions-list", "--json"])
    if code == 0:
        try:
            sessions = _normalize_sessions_json(json.loads(output))
            if sessions:
                return sessions
        except json.JSONDecodeError:
            pass

    code, output = _run_openvpn3(["sessions-list"])
    if code != 0:
        return []

    sessions: list[dict[str, object]] = []
    for block in _parse_session_blocks(output):
        config_match = _CONFIG_NAME_RE.search(block)
        if config_match is None:
            continue
        created_match = _CREATED_RE.search(block)
        session: dict[str, object] = {"config_name": config_match.group(1).strip()}
        if created_match is not None:
            session["created"] = created_match.group(1).strip()
        sessions.append(session)
    return sessions


def _session_matches_config(session: dict[str, object], config_name: str) -> bool:
    listed_name = _session_name_from_mapping(session)
    return listed_name is not None and _config_name_matches(listed_name, config_name)


def session_is_active(config_name: str) -> bool:
    return any(_session_matches_config(session, config_name) for session in _list_sessions())


def get_session_started_at(config_name: str) -> datetime | None:
    """Return when the running session was created."""
    for session in _list_sessions():
        if not _session_matches_config(session, config_name):
            continue
        started_at = _created_from_session(session)
        if started_at is not None:
            return started_at
        created = session.get("created")
        if isinstance(created, str):
            try:
                return datetime.strptime(created.strip(), _CREATED_FMT)
            except ValueError:
                continue
    return None

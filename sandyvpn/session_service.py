"""VPN session operations decoupled from the GUI."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from sandyvpn import vpn


class VpnSessionService:
    """Thin service layer over ``openvpn3`` CLI helpers."""

    def is_active(self, config_name: str) -> bool:
        return vpn.session_is_active(config_name)

    def started_at(self, config_name: str) -> datetime | None:
        return vpn.get_session_started_at(config_name)

    def connect(
        self,
        config_name: str,
        username: str,
        password: str,
        *,
        on_output: Callable[[str], None] | None = None,
    ) -> tuple[int, str]:
        return vpn.start_session(config_name, username, password, on_output=on_output)

    def disconnect(self, config_name: str) -> tuple[int, str]:
        return vpn.disconnect_session(config_name)

    def reconnect(self, config_name: str) -> tuple[int, str]:
        return vpn.restart_session(config_name)

    def stats(self, config_name: str) -> tuple[int, str]:
        return vpn.get_session_stats(config_name)

    def import_config(
        self,
        ovpn_path: str | Path,
        config_name: str,
        *,
        on_output: Callable[[str], None] | None = None,
    ) -> tuple[int, str]:
        return vpn.import_config(ovpn_path, config_name, on_output=on_output)

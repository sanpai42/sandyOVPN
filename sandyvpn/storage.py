"""Encrypted credential storage for SandyVPN."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from sandyvpn.errors import CredentialsCorruptedError

CRED_DIR = Path.home() / ".local" / "share" / "sandyvpn"
KEY_FILE = CRED_DIR / ".key"
CRED_FILE = CRED_DIR / "credentials.enc"

_UNSET = object()


@dataclass
class Profile:
    config_name: str
    username: str


@dataclass
class Credentials:
    config_name: str
    username: str
    password: str


@dataclass(frozen=True)
class ConnectAuth:
    config_name: str
    username: str
    password: str


def _ensure_cred_dir() -> None:
    CRED_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CRED_DIR, 0o700)


def _get_fernet() -> Fernet:
    _ensure_cred_dir()
    if KEY_FILE.exists():
        key = KEY_FILE.read_bytes()
    else:
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)
        KEY_FILE.chmod(0o600)
    return Fernet(key)


def _read_payload_from_disk() -> tuple[dict | None, str | None]:
    if not CRED_FILE.exists():
        return None, None
    try:
        return json.loads(_get_fernet().decrypt(CRED_FILE.read_bytes()).decode()), None
    except InvalidToken:
        return None, "Saved credentials could not be decrypted. Clear them and save again."
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, "Saved credentials are corrupted. Clear them and save again."


class CredentialStore:
    """Encrypted credential storage with an in-memory cache."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict | None | object = _UNSET
        self._load_error: str | None = None

    @property
    def load_error(self) -> str | None:
        with self._lock:
            self._ensure_loaded()
            return self._load_error

    def _ensure_loaded(self) -> None:
        if self._cache is not _UNSET:
            return
        payload, error = _read_payload_from_disk()
        self._cache = payload
        self._load_error = error

    def _payload(self) -> dict | None:
        with self._lock:
            self._ensure_loaded()
            if self._load_error is not None:
                return None
            return self._cache  # type: ignore[return-value]

    def invalidate(self) -> None:
        with self._lock:
            self._cache = _UNSET
            self._load_error = None

    def credentials_exist(self) -> bool:
        payload = self._payload()
        if payload is None:
            return False
        return bool(payload.get("config_name") or payload.get("username") or payload.get("password"))

    def has_stored_password(self) -> bool:
        payload = self._payload()
        return bool(payload and payload.get("password"))

    def load_profile(self) -> Profile | None:
        if self.load_error is not None:
            raise CredentialsCorruptedError(self.load_error)
        payload = self._payload()
        if payload is None:
            return None
        config_name = payload.get("config_name", "")
        username = payload.get("username", "")
        if not config_name and not username:
            return None
        return Profile(config_name=config_name, username=username)

    def unlock_password(self) -> str | None:
        if self.load_error is not None:
            raise CredentialsCorruptedError(self.load_error)
        payload = self._payload()
        if payload is None:
            return None
        password = payload.get("password", "")
        return password or None

    def save(self, creds: Credentials) -> None:
        payload = {
            "config_name": creds.config_name,
            "username": creds.username,
            "password": creds.password,
        }
        encoded = json.dumps(payload).encode()
        _ensure_cred_dir()
        CRED_FILE.write_bytes(_get_fernet().encrypt(encoded))
        CRED_FILE.chmod(0o600)
        with self._lock:
            self._cache = payload
            self._load_error = None

    def clear(self) -> None:
        if CRED_FILE.exists():
            CRED_FILE.unlink()
        with self._lock:
            self._cache = None
            self._load_error = None

    @staticmethod
    def validate_profile_fields(config_name: str, username: str) -> tuple[str, str] | None:
        if not config_name:
            return ("Missing config", "Enter a configuration profile name.")
        if not username:
            return ("Missing username", "Enter an auth username.")
        return None

    def resolve_connect(
        self,
        config_name: str,
        username: str,
        typed_password: str | None,
    ) -> ConnectAuth | tuple[str, str]:
        error = self.validate_profile_fields(config_name, username)
        if error is not None:
            return error

        if typed_password:
            return ConnectAuth(config_name=config_name, username=username, password=typed_password)

        password = self.unlock_password()
        if password is None:
            return ("Missing password", "Save credentials first, then connect.")
        return ConnectAuth(config_name=config_name, username=username, password=password)

    def resolve_save(
        self,
        config_name: str,
        username: str,
        typed_password: str | None,
    ) -> Credentials | tuple[str, str] | None:
        if self.credentials_exist():
            return None
        error = self.validate_profile_fields(config_name, username)
        if error is not None:
            return error
        if not typed_password:
            return ("Missing password", "Enter an auth password to save.")
        return Credentials(config_name=config_name, username=username, password=typed_password)

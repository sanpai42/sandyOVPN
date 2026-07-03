"""Shared application errors."""


class SandyVpnError(Exception):
    """Base error for SandyVPN operations."""


class OpenVpn3Error(SandyVpnError):
    """Base error for OpenVPN 3 CLI integration."""


class OpenVpn3NotFoundError(OpenVpn3Error):
    """The openvpn3 executable is not available on PATH."""


class OpenVpn3TimeoutError(OpenVpn3Error):
    """An openvpn3 command did not finish within the allowed time."""


class CredentialsCorruptedError(SandyVpnError):
    """Saved credentials could not be decrypted or parsed."""

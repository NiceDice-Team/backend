"""Process-wide local-only socket guard for contract infrastructure."""

import ipaddress
import os
import socket


class LocalOnlyNetworkError(OSError):
    """Raised before an attempted non-local network connection."""


def _allowed_hosts() -> set[str]:
    configured = os.getenv("CONTRACT_ALLOWED_LOCAL_HOSTS", "")
    return {
        "localhost",
        "127.0.0.1",
        "::1",
        *{item.strip().lower() for item in configured.split(",") if item.strip()},
    }


def _is_allowed(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="strict")
    normalized = str(host).strip().lower().strip("[]")
    if normalized in _allowed_hosts():
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _guard_address(address) -> None:
    # Unix-domain sockets do not carry an Internet host and remain local.
    if isinstance(address, (str, bytes)):
        return
    if not address or not _is_allowed(address[0]):
        raise LocalOnlyNetworkError(
            f"Contract egress guard blocked non-local destination: {address!r}"
        )


if os.getenv("CONTRACT_EGRESS_GUARD") == "1":
    _original_connect = socket.socket.connect
    _original_connect_ex = socket.socket.connect_ex
    _original_create_connection = socket.create_connection

    def guarded_connect(self, address):
        _guard_address(address)
        return _original_connect(self, address)

    def guarded_connect_ex(self, address):
        _guard_address(address)
        return _original_connect_ex(self, address)

    def guarded_create_connection(address, *args, **kwargs):
        _guard_address(address)
        return _original_create_connection(address, *args, **kwargs)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.create_connection = guarded_create_connection

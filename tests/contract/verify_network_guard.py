"""Fail unless the process-wide contract egress guard blocks before connect."""

import socket

from sitecustomize import LocalOnlyNetworkError


def main() -> None:
    try:
        # RFC 5737 TEST-NET-2: documentation-only and intentionally non-local.
        socket.create_connection(("198.51.100.1", 443), timeout=0.01)
    except LocalOnlyNetworkError:
        print("forbidden_outbound_self_test=blocked")
        return
    except OSError as exc:
        raise SystemExit(f"egress guard did not block before OS connect: {exc}") from exc
    raise SystemExit("egress guard allowed forbidden outbound connection")


if __name__ == "__main__":
    main()

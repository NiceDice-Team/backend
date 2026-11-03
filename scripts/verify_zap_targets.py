"""Fail closed if ZAP evidence contains any non-approved application target."""

import argparse
import ipaddress
import json
from urllib.parse import urlparse


def origin(value: str) -> str:
    parsed = urlparse(value)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return f"{parsed.scheme}://{(parsed.hostname or '').lower()}:{port}"


def allowed(url: str, allowed_origins: set[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    try:
        local = ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = host == "host.docker.internal"
    return bool(local and origin(url) in allowed_origins)


def urls(payload):
    for site in payload.get("site", []):
        if site.get("@name"):
            yield site["@name"]
        for alert in site.get("alerts", []):
            for instance in alert.get("instances", []):
                if instance.get("uri"):
                    yield instance["uri"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--allow-origin", action="append", required=True)
    args = parser.parse_args()
    payload = json.load(open(args.report))
    allowed_origins = {origin(value) for value in args.allow_origin}
    rejected = sorted({url for url in urls(payload) if not allowed(url, allowed_origins)})
    if rejected:
        print("ZAP network safety FAILED; non-local targets were present:")
        for url in rejected:
            parsed = urlparse(url)
            print(f"- {parsed.scheme}://{parsed.hostname}:{parsed.port or ''}")
        return 1
    print(f"ZAP network safety PASSED; inspected {sum(1 for _ in urls(payload))} evidence URLs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

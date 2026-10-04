"""Validate effective contract settings before migrations or server startup."""

import ipaddress
import os
from urllib.parse import urlparse

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.contract_settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402


def _local(host: str) -> bool:
    normalized = host.strip().lower().strip("[]")
    allowed = {
        "localhost",
        "127.0.0.1",
        "::1",
        *{
            item.strip().lower()
            for item in os.getenv("CONTRACT_ALLOWED_LOCAL_HOSTS", "").split(",")
            if item.strip()
        },
    }
    if normalized in allowed:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _url_host(value: str) -> str:
    parsed = urlparse(value)
    return parsed.hostname or ""


def main() -> None:
    failures = []
    database = settings.DATABASES["default"]
    if database["ENGINE"] != "django.db.backends.sqlite3" and not _local(database["HOST"]):
        failures.append(f"database host is not local: {database['HOST']!r}")
    if settings.EMAIL_BACKEND.endswith("smtp.EmailBackend") and not _local(settings.EMAIL_HOST):
        failures.append(f"SMTP host is not local: {settings.EMAIL_HOST!r}")
    if not _local(_url_host(settings.FRONTEND_BASE_URL)):
        failures.append(f"frontend URL is not local: {settings.FRONTEND_BASE_URL!r}")
    if settings.STORAGES["default"]["BACKEND"] != (
        "django.core.files.storage.memory.InMemoryStorage"
    ):
        failures.append("default storage is not in-memory")
    credential_names = {
        "AWS_S3_ACCESS_KEY_ID",
        "AWS_S3_SECRET_ACCESS_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_CLOUDFRONT_DISTRIBUTION_ID",
        "GOOGLE_OAUTH2_CLIENT_ID",
        "GOOGLE_OAUTH2_CLIENT_SECRET",
        "FACEBOOK_APP_ID",
        "FACEBOOK_APP_SECRET",
        "STRIPE_SECRET_KEY",
    }
    leaked = sorted(name for name in credential_names if os.getenv(name))
    if leaked:
        failures.append(f"external credentials are populated: {', '.join(leaked)}")
    if os.getenv("CONTRACT_EGRESS_GUARD") != "1":
        failures.append("CONTRACT_EGRESS_GUARD is not enabled")
    if failures:
        raise SystemExit("unsafe contract environment:\n- " + "\n- ".join(failures))
    print("contract_environment=local_only")


if __name__ == "__main__":
    main()

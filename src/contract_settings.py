"""Fail-closed, local-only settings for runtime OpenAPI contract tests."""

import ipaddress
import os
from urllib.parse import urlparse


def _allowed_local_hosts() -> set[str]:
    configured = os.getenv("CONTRACT_ALLOWED_LOCAL_HOSTS", "")
    return {
        "localhost",
        "127.0.0.1",
        "::1",
        *{item.strip().lower() for item in configured.split(",") if item.strip()},
    }


def _require_local_host(value: str, setting_name: str) -> str:
    host = value.strip().lower().strip("[]")
    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback and host not in _allowed_local_hosts():
        raise RuntimeError(f"{setting_name} must be local in contract settings: {value!r}")
    return value


def _require_local_url(value: str, setting_name: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError(f"{setting_name} must be an absolute local HTTP URL")
    _require_local_host(parsed.hostname, setting_name)
    return value.rstrip("/")


contract_db_host = _require_local_host(
    os.getenv("CONTRACT_DB_HOST", "127.0.0.1"), "CONTRACT_DB_HOST"
)
contract_email_host = _require_local_host(
    os.getenv("CONTRACT_EMAIL_HOST", "127.0.0.1"), "CONTRACT_EMAIL_HOST"
)
contract_frontend_url = _require_local_url(
    os.getenv("CONTRACT_FRONTEND_BASE_URL", "http://127.0.0.1:8000"),
    "CONTRACT_FRONTEND_BASE_URL",
)
contract_storage_endpoint = os.getenv("CONTRACT_STORAGE_ENDPOINT_URL", "").strip()
if contract_storage_endpoint:
    _require_local_url(contract_storage_endpoint, "CONTRACT_STORAGE_ENDPOINT_URL")

# Set every runtime input before importing settings, so dotenv files cannot
# supply production-like values to a contract process.
os.environ.update(
    {
        "DJANGO_SECRET_KEY": "contract-tests-local-key",
        "ALLOWED_HOSTS": "localhost,127.0.0.1,[::1]",
        "DB_HOST": contract_db_host,
        "DB_PORT": os.getenv("CONTRACT_DB_PORT", "5432"),
        "DB_NAME": os.getenv("CONTRACT_DB_NAME", "backend_db"),
        "DB_USER": os.getenv("CONTRACT_DB_USER", "backend_user"),
        "DB_PASSWORD": os.getenv("CONTRACT_DB_PASSWORD", "backend_pass"),
        "DB_SSLMODE": "disable",
        "SITE_BASE_URL": "http://127.0.0.1:8000",
        "FRONTEND_BASE_URL": contract_frontend_url,
        "AWS_S3_ACCESS_KEY_ID": "",
        "AWS_S3_SECRET_ACCESS_KEY": "",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
        "AWS_CLOUDFRONT_DISTRIBUTION_ID": "",
        "GOOGLE_OAUTH2_CLIENT_ID": "",
        "GOOGLE_OAUTH2_CLIENT_SECRET": "",
        "FACEBOOK_APP_ID": "",
        "FACEBOOK_APP_SECRET": "",
        "STRIPE_SECRET_KEY": "",
        "EMAIL_HOST_USER": "",
        "EMAIL_HOST_PASSWORD": "",
        "DEFAULT_FROM_EMAIL": "NiceDice Contract Tests <contract@nicedice.invalid>",
        "REPLY_TO_EMAIL": "NiceDice Contract Tests <contract@nicedice.invalid>",
    }
)

from .settings import *  # noqa: E402,F403


CORS_ALLOWED_ORIGINS = []

EMAIL_BACKEND = os.getenv(
    "CONTRACT_EMAIL_BACKEND",
    "django.core.mail.backends.locmem.EmailBackend",
)
if EMAIL_BACKEND not in {
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.smtp.EmailBackend",
}:
    raise RuntimeError("Unsupported CONTRACT_EMAIL_BACKEND for local contract execution")
EMAIL_HOST = contract_email_host
EMAIL_PORT = int(os.getenv("CONTRACT_EMAIL_PORT", "1025"))
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
DEFAULT_FROM_EMAIL = "NiceDice Contract Tests <contract@nicedice.invalid>"
REPLY_TO_EMAIL = DEFAULT_FROM_EMAIL
FRONTEND_BASE_URL = contract_frontend_url
SITE_BASE_URL = "http://127.0.0.1:8000"
STRIPE_SECRET_KEY = ""
stripe.api_key = None  # noqa: F405

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.memory.InMemoryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

contract_sqlite_path = os.getenv("CONTRACT_SQLITE_PATH")
if contract_sqlite_path:
    DATABASES = {  # noqa: F405
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": contract_sqlite_path,
        }
    }

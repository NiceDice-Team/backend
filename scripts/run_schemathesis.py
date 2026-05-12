import argparse
import os
import subprocess
import sys
from urllib.parse import urlparse

import requests


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Schemathesis against API schema with optional auth token retrieval."
    )
    parser.add_argument(
        "--schema-url",
        default="http://127.0.0.1:8000/api/schema/?format=json",
        help="OpenAPI schema URL",
    )
    parser.add_argument(
        "--seed",
        default="102444487936215620529585841017150007980",
        help="Hypothesis seed",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=30,
        help="Hypothesis max examples",
    )
    parser.add_argument(
        "--checks",
        default="all",
        help="Schemathesis checks option",
    )
    parser.add_argument(
        "--output",
        default="schemathesis-auth-results.txt",
        help="Output file path",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Bearer token. If omitted, API_TOKEN env is used, then optional login flow.",
    )
    parser.add_argument(
        "--email",
        default=None,
        help="Login email for obtaining token from /api/users/token/",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Login password for obtaining token from /api/users/token/",
    )
    parser.add_argument(
        "--token-url",
        default=None,
        help="Token endpoint URL (defaults to <schema-host>/api/users/token/)",
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Run without Authorization header",
    )
    return parser


def default_token_url(schema_url: str) -> str:
    parsed = urlparse(schema_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return f"{base}/api/users/token/"


def get_token_from_credentials(token_url: str, email: str, password: str) -> str:
    response = requests.post(
        token_url,
        json={"email": email, "password": password},
        timeout=20,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Token request failed ({response.status_code}): {response.text[:300]}"
        )

    data = response.json()
    token = data.get("access")
    if not token:
        raise RuntimeError("Token response has no 'access' field")
    return token


def resolve_token(args: argparse.Namespace) -> str | None:
    if args.no_auth:
        return None

    if args.token:
        return args.token

    env_token = os.getenv("API_TOKEN")
    if env_token:
        return env_token

    if args.email and args.password:
        token_url = args.token_url or default_token_url(args.schema_url)
        return get_token_from_credentials(token_url, args.email, args.password)

    return None


def run_schemathesis(args: argparse.Namespace, token: str | None) -> int:
    command = [
        "uv",
        "run",
        "schemathesis",
        "run",
        args.schema_url,
        "--checks",
        args.checks,
        "--hypothesis-max-examples",
        str(args.max_examples),
        "--hypothesis-seed",
        args.seed,
    ]

    if token:
        command.extend(["--header", f"Authorization: Bearer {token}"])

    print("Running:", " ".join(command))
    print(f"Writing output to: {args.output}")

    with open(args.output, "w", encoding="utf-8") as output_file:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            output_file.write(line)

        return process.wait()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        token = resolve_token(args)
    except Exception as exc:
        print(f"Failed to resolve token: {exc}", file=sys.stderr)
        return 2

    if not args.no_auth and not token:
        print(
            "No token provided. Use --token, API_TOKEN env, or --email/--password.",
            file=sys.stderr,
        )
        return 2

    return run_schemathesis(args, token)


if __name__ == "__main__":
    raise SystemExit(main())

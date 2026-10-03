from types import SimpleNamespace

import pytest
import requests

from users.interfaces.serializers import OAuthLoginSerializer
from users.interfaces.views import build_public_url, wants_json_response


pytestmark = pytest.mark.unit


class FakeResponse:
    def __init__(self, status_code, payload=None, json_error=None):
        self.status_code = status_code
        self.payload = payload
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


def test_google_provider_maps_successful_profile(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse(
            200,
            {
                "email": "google@example.com",
                "given_name": "Google",
                "family_name": "User",
                "picture": "https://images.example.com/avatar.png",
            },
        )

    monkeypatch.setattr(
        "users.interfaces.serializers.requests.get",
        fake_get,
    )

    profile, error = OAuthLoginSerializer()._validate_google_token("fake-token")

    assert error is None
    assert profile == {
        "email": "google@example.com",
        "first_name": "Google",
        "last_name": "User",
        "picture": "https://images.example.com/avatar.png",
    }
    assert calls == [
        (
            ("https://www.googleapis.com/oauth2/v3/userinfo",),
            {"headers": {"Authorization": "Bearer fake-token"}, "timeout": 10},
        )
    ]


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (FakeResponse(401, {"error": {"message": "expired"}}), "Invalid Google token: expired"),
        (FakeResponse(503, json_error=ValueError("not json")), "Invalid Google token (HTTP 503)"),
    ],
)
def test_google_provider_maps_error_responses(monkeypatch, response, expected):
    calls = []
    monkeypatch.setattr(
        "users.interfaces.serializers.requests.get",
        lambda *args, **kwargs: calls.append((args, kwargs)) or response,
    )

    profile, error = OAuthLoginSerializer()._validate_google_token("fake-token")

    assert profile is None
    assert error == expected
    assert calls == [
        (
            ("https://www.googleapis.com/oauth2/v3/userinfo",),
            {"headers": {"Authorization": "Bearer fake-token"}, "timeout": 10},
        )
    ]


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (requests.Timeout(), "Request to Google API timed out"),
        (requests.ConnectionError("offline"), "Network error while validating Google token: offline"),
    ],
)
def test_google_provider_maps_transport_errors(monkeypatch, raised, expected):
    calls = []

    def fail_get(*args, **kwargs):
        calls.append((args, kwargs))
        raise raised

    monkeypatch.setattr(
        "users.interfaces.serializers.requests.get",
        fail_get,
    )

    profile, error = OAuthLoginSerializer()._validate_google_token("fake-token")

    assert profile is None
    assert error == expected
    assert calls == [
        (
            ("https://www.googleapis.com/oauth2/v3/userinfo",),
            {"headers": {"Authorization": "Bearer fake-token"}, "timeout": 10},
        )
    ]


def test_facebook_provider_maps_nested_picture(monkeypatch):
    calls = []
    response = FakeResponse(
        200,
        {
            "email": "facebook@example.com",
            "first_name": "Facebook",
            "last_name": "User",
            "picture": {"data": {"url": "https://images.example.com/facebook.png"}},
        },
    )
    monkeypatch.setattr(
        "users.interfaces.serializers.requests.get",
        lambda *args, **kwargs: calls.append((args, kwargs)) or response,
    )

    profile, error = OAuthLoginSerializer()._validate_facebook_token("fake-token")

    assert error is None
    assert profile["picture"] == "https://images.example.com/facebook.png"
    assert profile["email"] == "facebook@example.com"
    assert calls == [
        (
            (
                "https://graph.facebook.com/me?access_token=fake-token&fields="
                "id,email,first_name,last_name,picture",
            ),
            {"timeout": 10},
        )
    ]


def test_facebook_provider_maps_provider_error(monkeypatch):
    calls = []
    response = FakeResponse(403, {"error": {"message": "invalid token"}})
    monkeypatch.setattr(
        "users.interfaces.serializers.requests.get",
        lambda *args, **kwargs: calls.append((args, kwargs)) or response,
    )

    profile, error = OAuthLoginSerializer()._validate_facebook_token("fake-token")

    assert profile is None
    assert error == "Invalid Facebook token: invalid token"
    assert calls == [
        (
            (
                "https://graph.facebook.com/me?access_token=fake-token&fields="
                "id,email,first_name,last_name,picture",
            ),
            {"timeout": 10},
        )
    ]


def test_build_public_url_uses_configured_base_without_duplicate_path(settings):
    settings.SITE_BASE_URL = "https://local.example.test/api"

    assert build_public_url(None, "/api/users/activate/uid/token/") == (
        "https://local.example.test/api/users/activate/uid/token/"
    )


@pytest.mark.parametrize(
    ("renderer_format", "accept", "expected"),
    [("json", "", True), (None, "application/json", True), (None, "text/html", False)],
)
def test_wants_json_response(renderer_format, accept, expected):
    request = SimpleNamespace(
        accepted_renderer=SimpleNamespace(format=renderer_format) if renderer_format else None,
        headers={"Accept": accept},
    )

    assert wants_json_response(request) is expected

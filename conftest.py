# backend/conftest.py

import django
import os
import socket
import sys
import pytest
from pathlib import Path
from django.contrib.auth import get_user_model
from src.categories.models import Category

# Check that the settings module is set correctly
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.test_settings")
SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.append(str(SRC_DIR))


@pytest.fixture(scope="session", autouse=True)
def django_setup():
    # Ensure Django is set up before running tests
    django.setup()


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    """No normal backend test is allowed to open a network socket."""

    def blocked(*args, **kwargs):
        raise AssertionError("Backend tests must not access external networks")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


def pytest_collection_modifyitems(items):
    layers = {"unit", "component", "api", "contract"}
    errors = []
    for item in items:
        assigned = sorted(layer for layer in layers if item.get_closest_marker(layer))
        if len(assigned) != 1:
            errors.append(f"{item.nodeid}: expected exactly one layer marker, got {assigned}")
    if errors:
        raise pytest.UsageError("Invalid test layer classification:\n" + "\n".join(errors))

@pytest.fixture
def user_model():
    # User model fixture to be used in tests
    return get_user_model()


@pytest.fixture
def category_model():
    # Category model fixture to be used in tests
    return Category

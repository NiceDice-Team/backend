# backend/conftest.py

import django
import os
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

@pytest.fixture
def user_model():
    # User model fixture to be used in tests
    return get_user_model()


@pytest.fixture
def category_model():
    # Category model fixture to be used in tests
    return Category

# src/users/tests/test_views.py
import pytest
from django.test import Client
from django.urls import reverse
from rest_framework import status

@pytest.mark.django_db
def test_api_root_renders_index():
    client = Client()
    
    # If you have a URL pattern for this view, e.g., path('', api_root, name='api-root')
    url = reverse('api-root')
    
    response = client.get(url)
    
    # Check status code
    assert response.status_code in  (status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED)
    
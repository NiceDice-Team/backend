# src/users/tests/test_users_urls.py
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

@pytest.mark.api
@pytest.mark.django_db
class TestUserURLs:
    @pytest.fixture
    def api_client(self):
        return APIClient()

    def test_user_list_create_get(self, api_client):
        url = reverse('user-list-create')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_register_post(self, api_client):
        url = reverse('register')
        data = {
            "first_name": " Test Name",
            "last_name": "Test Last Name",
            "email": "newuser@example.com",
            "password": "strongpassword123"
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED

    def test_activate_url(self, api_client):
        uid = "fakeuid"
        token = "faketoken"
        url = reverse('activate', kwargs={'uidb64': uid, 'token': token})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error_code"] == "TOKEN_INVALID"

    def test_token_obtain_pair_post(self, api_client):
        url = reverse('token_obtain_pair')
        data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_forgot_password_post(self, api_client):
        url = reverse('forgot-password')
        data = {"email": "test@example.com"}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK

    def test_reset_password_post(self, api_client):
        url = reverse('reset-password')
        data = {
            "uid": "fakeuid",
            "token": "faketoken",
            "new_password": "newpassword123"
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

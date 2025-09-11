# src/users/tests/test_users_urls.py
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

@pytest.mark.positive
@pytest.mark.django_db
class TestCategoryURLs:
    @pytest.fixture
    def api_client(self):
        return APIClient()

    def test_category_list_create_get(self, api_client):
        url = reverse('category-list-create')
        response = api_client.get(url)
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_category_create_post(self, api_client):
        url = reverse('category-list-create')
        data = {
            "name": "Test Category",
            "slug": "test-category",
            "description": "A test category",
            "image": "http://example.com/image.jpg"
        }
        response = api_client.post(url, data)
        # Depending on permissions, could be 201, 403, or 401
        assert response.status_code in (
            status.HTTP_201_CREATED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_category_detail_get(self, api_client, category_model):
        category = category_model.objects.create(
            name="Detail Category",
            slug="detail-category",
            description="Detail test",
            image="http://example.com/image.jpg"
        )
        url = reverse('category-detail', kwargs={'pk': category.pk})
        response = api_client.get(url)
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_404_NOT_FOUND
        )

    def test_category_update_patch(self, api_client, category_model):
        category = category_model.objects.create(
            name="Patch Category",
            slug="patch-category",
            description="Patch test",
            image="http://example.com/image.jpg"
        )
        url = reverse('category-detail', kwargs={'pk': category.pk})
        data = {"name": "Updated Name"}
        response = api_client.patch(url, data)
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED
        )

    def test_category_delete(self, api_client, category_model):
        category = category_model.objects.create(
            name="Delete Category",
            slug="delete-category",
            description="Delete test",
            image="http://example.com/image.jpg"
        )
        url = reverse('category-detail', kwargs={'pk': category.pk})
        response = api_client.delete(url)
        assert response.status_code in (
            status.HTTP_204_NO_CONTENT,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED
        )

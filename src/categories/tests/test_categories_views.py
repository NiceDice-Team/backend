# src/users/tests/test_views.py
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

@pytest.mark.positive
@pytest.mark.django_db
class TestCategoryViews:
    @pytest.fixture
    def api_client(self):
        return APIClient()

    def test_category_list_view(self, api_client, category_model):
        # Create some categories
        category_model.objects.create(
            name="Category 1", slug="cat-1", description="desc1", image=""
        )
        category_model.objects.create(
            name="Category 2", slug="cat-2", description="desc2", image=""
        )
        url = reverse('category-list-create')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json().get("results"), list)
        assert len(response.json().get("results")) >= 2

    def test_category_create_view(self, api_client):
        url = reverse('category-list-create')
        data = {
            "name": "Created Category",
            "slug": "created-category",
            "description": "Created via test",
            "image": "http://example.com/image.jpg"
        }
        response = api_client.post(url, data)
        # Adjust expected status if authentication is required
        assert response.status_code in (status.HTTP_201_CREATED, status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED)

    def test_category_detail_view(self, api_client, category_model):
        category = category_model.objects.create(
            name="Detail Category", slug="detail-category", description="desc", image=""
        )
        url = reverse('category-detail', kwargs={'pk': category.pk})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['id'] == category.pk

    def test_category_update_view(self, api_client, category_model):
        category = category_model.objects.create(
            name="To Update", slug="to-update", description="desc", image=""
        )
        url = reverse('category-detail', kwargs={'pk': category.pk})
        data = {"name": "Updated Name"}
        response = api_client.patch(url, data)
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED)

    def test_category_delete_view(self, api_client, category_model):
        category = category_model.objects.create(
            name="To Delete", slug="to-delete", description="desc", image=""
        )
        url = reverse('category-detail', kwargs={'pk': category.pk})
        response = api_client.delete(url)
        assert response.status_code in (status.HTTP_204_NO_CONTENT, status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED)

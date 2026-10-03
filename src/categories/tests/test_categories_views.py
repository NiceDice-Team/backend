# src/users/tests/test_views.py
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

@pytest.mark.api
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

    @pytest.mark.bug
    def test_current_category_create_defect_rejects_documented_payload(
        self, api_client, user_model, category_model
    ):
        user = user_model.objects.create_user(username="category-create", email="category-create@example.com")
        api_client.force_authenticate(user=user)
        url = reverse('category-list-create')
        data = {
            "name": "Created Category",
            "slug": "created-category",
            "description": "Created via test",
            "image": "http://example.com/image.jpg"
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert {error["attr"] for error in response.json()["errors"]} == {
            "id", "creationAt", "updatedAt"
        }
        assert not category_model.objects.filter(name="Created Category").exists()

    def test_category_detail_view(self, api_client, category_model):
        category = category_model.objects.create(
            name="Detail Category", slug="detail-category", description="desc", image=""
        )
        url = reverse('category-detail', kwargs={'pk': category.pk})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['id'] == category.pk

    def test_category_update_view(self, api_client, category_model, user_model):
        user = user_model.objects.create_user(username="category-update", email="category-update@example.com")
        api_client.force_authenticate(user=user)
        category = category_model.objects.create(
            name="To Update", slug="to-update", description="desc", image=""
        )
        url = reverse('category-detail', kwargs={'pk': category.pk})
        data = {"name": "Updated Name"}
        response = api_client.patch(url, data)
        assert response.status_code == status.HTTP_200_OK
        category.refresh_from_db()
        assert category.name == "Updated Name"

    def test_category_delete_view(self, api_client, category_model, user_model):
        user = user_model.objects.create_user(username="category-delete", email="category-delete@example.com")
        api_client.force_authenticate(user=user)
        category = category_model.objects.create(
            name="To Delete", slug="to-delete", description="desc", image=""
        )
        url = reverse('category-detail', kwargs={'pk': category.pk})
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not category_model.objects.filter(pk=category.pk).exists()

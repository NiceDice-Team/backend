import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.positive
class TestDeliveryOptionsView:
    @pytest.fixture
    def api_client(self):
        return APIClient()

    def test_delivery_options_returns_available_methods(self, api_client):
        url = reverse('delivery-options')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_delivery_options_response_shape(self, api_client):
        url = reverse('delivery-options')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        for option in response.json():
            assert 'id' in option
            assert 'name' in option
            assert 'description' in option
            assert 'price' in option
            assert 'estimated_days' in option

    def test_delivery_options_contains_nova_poshta(self, api_client):
        url = reverse('delivery-options')
        response = api_client.get(url)
        ids = [opt['id'] for opt in response.json()]
        assert 'nova_poshta' in ids

    def test_delivery_options_post_not_allowed(self, api_client):
        url = reverse('delivery-options')
        response = api_client.post(url, {})
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

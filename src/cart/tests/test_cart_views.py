import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from categories.infrastructure.models import Category
from cart.infrastructure.models import CartItem
from products.infrastructure.models import Brand, Product


@pytest.mark.django_db
class TestCartViews:
    @pytest.fixture
    def api_client(self):
        return APIClient()

    def _create_product(self):
        category = Category.objects.create(
            name='Strategy',
            slug='strategy',
            description='Strategy games',
            image='https://example.com/category.jpg',
        )
        brand = Brand.objects.create(name='Hasbro')
        product = Product.objects.create(
            name='Chess',
            description='Classic strategy game',
            price='29.99',
            brand=brand,
            stock=10,
        )
        product.categories.add(category)
        return product

    def test_create_and_list_cart_item(self, api_client, user_model):
        user = user_model.objects.create_user(
            email='cart@example.com',
            username='cart@example.com',
            password='strongpassword123',
            first_name='Cart',
            last_name='User',
        )
        product = self._create_product()

        create_response = api_client.post(reverse('cart-list'), {
            'user': user.id,
            'product': product.id,
            'quantity': 2,
        }, format='json')

        assert create_response.status_code == status.HTTP_201_CREATED
        assert CartItem.objects.filter(user=user, product=product, quantity=2).exists()

        list_response = api_client.get(reverse('cart-list'), {'user_id': user.id})
        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.json()['count'] == 1
        assert len(list_response.json()['results']) == 1
        assert list_response.json()['results'][0]['product']['name'] == 'Chess'

    def test_retrieve_cart_item_requires_matching_user(self, api_client, user_model):
        user = user_model.objects.create_user(
            email='cart-owner@example.com',
            username='cart-owner@example.com',
            password='strongpassword123',
            first_name='Cart',
            last_name='Owner',
        )
        other_user = user_model.objects.create_user(
            email='cart-other@example.com',
            username='cart-other@example.com',
            password='strongpassword123',
            first_name='Cart',
            last_name='Other',
        )
        product = self._create_product()
        cart_item = CartItem.objects.create(user=user, product=product, quantity=1)

        response = api_client.get(reverse('cart-detail', kwargs={'pk': cart_item.pk}), {'user_id': other_user.id})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_partial_update_cart_item_quantity(self, api_client, user_model):
        user = user_model.objects.create_user(
            email='cart-update@example.com',
            username='cart-update@example.com',
            password='strongpassword123',
            first_name='Cart',
            last_name='Update',
        )
        product = self._create_product()
        cart_item = CartItem.objects.create(user=user, product=product, quantity=1)

        response = api_client.patch(
            reverse('cart-detail', kwargs={'pk': cart_item.pk}) + f'?user_id={user.id}',
            {'quantity': 3},
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        cart_item.refresh_from_db()
        assert cart_item.quantity == 3

    def test_delete_cart_item(self, api_client, user_model):
        user = user_model.objects.create_user(
            email='cart-delete@example.com',
            username='cart-delete@example.com',
            password='strongpassword123',
            first_name='Cart',
            last_name='Delete',
        )
        product = self._create_product()
        cart_item = CartItem.objects.create(user=user, product=product, quantity=1)

        response = api_client.delete(reverse('cart-detail', kwargs={'pk': cart_item.pk}) + f'?user_id={user.id}')

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert CartItem.objects.filter(pk=cart_item.pk).exists() is False

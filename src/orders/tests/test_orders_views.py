import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from categories.infrastructure.models import Category
from orders.infrastructure.models import Order
from products.infrastructure.models import Brand, Product


@pytest.mark.django_db
class TestOrderViews:
    @pytest.fixture
    def api_client(self):
        return APIClient()

    def _create_product(self):
        category = Category.objects.create(
            name='Board Games',
            slug='board-games',
            description='Board games category',
            image='https://example.com/category.jpg',
        )
        brand = Brand.objects.create(name='Hasbro')
        product = Product.objects.create(
            name='Chess',
            description='Classic strategy game',
            price='29.99',
            brand=brand,
            stock=5,
        )
        product.categories.add(category)
        return product

    def test_get_order_history_returns_orders_for_user(self, api_client, user_model):
        user = user_model.objects.create_user(
            email='orders@example.com',
            username='orders@example.com',
            password='strongpassword123',
            first_name='Order',
            last_name='User',
        )
        product = self._create_product()
        order = Order.objects.create(user=user, total_amount='29.99')
        order.products.add(product)

        response = api_client.get(reverse('order-list-create'), {'user_id': user.id})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]['product_count'] == 1

    def test_create_order_consumes_cart_items(self, api_client, user_model):
        user = user_model.objects.create_user(
            email='cart-order@example.com',
            username='cart-order@example.com',
            password='strongpassword123',
            first_name='Cart',
            last_name='Order',
        )
        product = self._create_product()
        from cart.infrastructure.models import CartItem

        CartItem.objects.create(user=user, product=product, quantity=2)

        response = api_client.post(reverse('order-list-create'), {'user_id': user.id}, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert Order.objects.filter(user=user).count() == 1
        assert CartItem.objects.filter(user=user).count() == 0
        assert response.json()['status'] == 'pending'

    def test_create_payment_intent_success(self, api_client, monkeypatch):
        class FakeIntent:
            id = 'pi_test_123'
            client_secret = 'secret_123'

            def __getitem__(self, item):
                if item == 'client_secret':
                    return self.client_secret
                raise KeyError(item)

        import stripe
        monkeypatch.setattr(stripe.PaymentIntent, 'create', lambda **kwargs: FakeIntent())

        response = api_client.post(reverse('create-payment-intent'), {'amount': 2500}, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.json()['clientSecret'] == 'secret_123'

    def test_create_payment_intent_rejects_invalid_amount(self, api_client):
        response = api_client.post(reverse('create-payment-intent'), {'amount': -1}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['error'] == 'Amount must be greater than zero'

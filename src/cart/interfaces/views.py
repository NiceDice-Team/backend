from cart.infrastructure.models import CartItem
from cart.interfaces.serializers import (CartItemSerializer, PatchedCartItemSerializer, CartItemDetailSerializer)
from drf_spectacular.utils import extend_schema, OpenApiExample, extend_schema_view, OpenApiParameter
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated


@extend_schema_view(
    list=extend_schema(operation_id='api_carts_list_items'),
    retrieve=extend_schema(
        operation_id='api_carts_get_item',
        parameters=[
            OpenApiParameter("id", type=int, location=OpenApiParameter.PATH,
                             description="Ідентифікатор товару в кошику")
        ]
    ),
    partial_update=extend_schema(
        parameters=[
            OpenApiParameter("id", type=int, location=OpenApiParameter.PATH,
                             description="Ідентифікатор товару в кошику")
        ]
    ),
    destroy=extend_schema(
        parameters=[
            OpenApiParameter("id", type=int, location=OpenApiParameter.PATH,
                             description="Ідентифікатор товару в кошику")
        ]
    ),
)
@extend_schema(tags=['Carts'])
@extend_schema(
    methods=['GET', 'POST'],
    tags=['Carts'],
    request=CartItemSerializer,
    responses={
        200: CartItemDetailSerializer(many=True),
        201: CartItemDetailSerializer
    },
    examples=[
        OpenApiExample(
            name='Додати до корзини',
            summary='POST /api/carts/',
            value={'product': 1, 'quantity': 2},
            request_only=True
        ),
        OpenApiExample(
            name='Список товарів у корзині',
            summary='GET /api/carts/',
            value=[
                {
                    'id': 1,
                    'product': {'id': 1, 'name': 'Шахи', 'price': '29.99'},
                    'quantity': 2
                }
            ],
            response_only=True
        )
    ]
)
class CartItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CartItemSerializer
    lookup_field = 'pk'
    lookup_url_kwarg = 'pk'

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return CartItemDetailSerializer
        if self.action in ['partial_update', 'patch']:
            return PatchedCartItemSerializer
        return CartItemSerializer

    @extend_schema(
        methods=['PATCH'],
        tags=['Carts'],
        request=PatchedCartItemSerializer,
        responses={200: CartItemDetailSerializer},
        examples=[
            OpenApiExample(
                name='Оновити кількість',
                summary='PATCH /api/carts/{id}/',
                value={'quantity': 3},
                request_only=True
            )
        ]
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

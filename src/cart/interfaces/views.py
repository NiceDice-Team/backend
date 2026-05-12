from cart.infrastructure.models import CartItem
from cart.interfaces.serializers import (CartItemSerializer, PatchedCartItemSerializer, CartItemDetailSerializer)
from drf_spectacular.utils import extend_schema, OpenApiExample, extend_schema_view, OpenApiParameter
from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema_view(
    list=extend_schema(
        operation_id='api_carts_list_items',
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description="User ID used to filter the cart",
                required=False
            )
        ],
        responses={200: CartItemDetailSerializer(many=True)},
        examples=[
            OpenApiExample(
                name='List all items in carts',
                summary='GET /api/carts/',
                value=[
                    {
                        'id': 1,
                        'user': 1,
                        'product': {'id': 1, 'name': 'Chess', 'price': '29.99'},
                        'quantity': 2
                    }
                ],
                response_only=True
            ),
            OpenApiExample(
                name='List items in a specific user cart',
                summary='GET /api/carts/?user_id=1',
                value=[
                    {
                        'id': 1,
                        'user': 1,
                        'product': {'id': 1, 'name': 'Chess', 'price': '29.99'},
                        'quantity': 2
                    }
                ],
                response_only=True
            )
        ]
    ),
    retrieve=extend_schema(
        operation_id='api_carts_get_item',
        parameters=[
            OpenApiParameter("id", type=int, location=OpenApiParameter.PATH,
                             description="Cart entry identifier (CartItem ID)"),
            OpenApiParameter("user_id", type=int, location=OpenApiParameter.QUERY,
                             description="User ID (required)", required=True)
        ],
        responses={200: CartItemDetailSerializer},
        examples=[
            OpenApiExample(
                name='Get a specific cart item',
                summary='GET /api/carts/{id}/?user_id={user_id}',
                value={
                    'id': 1,
                    'user': 1,
                    'product': {'id': 1, 'name': 'Chess', 'price': '29.99'},
                    'quantity': 2
                },
                response_only=True
            )
        ]
    ),
    create=extend_schema(
        operation_id='api_carts_add_item',
        request=CartItemSerializer,
        responses={201: CartItemDetailSerializer},
        examples=[
            OpenApiExample(
                name='Add to cart',
                summary='POST /api/carts/',
                value={'user': 1, 'product': 1, 'quantity': 2},
                request_only=True
            ),
        ]
    ),
    partial_update=extend_schema(
        operation_id='api_carts_update_item',
        parameters=[
            OpenApiParameter("id", type=int, location=OpenApiParameter.PATH,
                             description="Cart entry identifier (CartItem ID)"),
            OpenApiParameter("user_id", type=int, location=OpenApiParameter.QUERY,
                             description="User ID (required)", required=True)
        ],
        request=PatchedCartItemSerializer,
        responses={200: CartItemDetailSerializer},
        examples=[
            OpenApiExample(
                name='Update cart item quantity',
                summary='PATCH /api/carts/{id}/?user_id={user_id}',
                description="Updates the quantity of an item in the cart. The cart entry ID is passed in the URL.",
                value={'quantity': 3},
                request_only=True
            )
        ]
    ),
    destroy=extend_schema(
        operation_id='api_carts_remove_item',
        parameters=[
            OpenApiParameter("id", type=int, location=OpenApiParameter.PATH,
                             description="Cart entry identifier (CartItem ID)"),
            OpenApiParameter("user_id", type=int, location=OpenApiParameter.QUERY,
                             description="User ID (required)", required=True)
        ],
        responses={204: None}
    ),
)
@extend_schema(tags=['Carts'])
class CartItemViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = CartItemSerializer
    lookup_field = 'pk'
    lookup_url_kwarg = 'pk'

    def get_queryset(self):
        queryset = CartItem.objects.all().order_by('id')

        user_id = self.request.query_params.get('user_id', None)
        if user_id is not None:
            try:
                user_id = int(user_id)
                queryset = queryset.filter(user_id=user_id)
            except ValueError:
                return CartItem.objects.none().order_by('id')

        return queryset

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return CartItemDetailSerializer
        if self.action in ['partial_update']:
            return PatchedCartItemSerializer
        return CartItemSerializer

    def perform_create(self, serializer):
        serializer.save()

    def retrieve(self, request, *args, **kwargs):
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'detail': 'The user_id parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_id = int(user_id)
        except ValueError:
            return Response({'detail': 'The user_id parameter must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)

        cart_item = self.get_object()

        if cart_item.user_id != user_id:
            return Response({'detail': 'This cart entry does not belong to the specified user.'},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(cart_item)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'detail': 'The user_id parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_id = int(user_id)
        except ValueError:
            return Response({'detail': 'The user_id parameter must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)

        cart_item = self.get_object()

        if cart_item.user_id != user_id:
            return Response({'detail': 'This cart entry does not belong to the specified user.'},
                            status=status.HTTP_403_FORBIDDEN)

        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'detail': 'The user_id parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_id = int(user_id)
        except ValueError:
            return Response({'detail': 'The user_id parameter must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)

        cart_item = self.get_object()

        if cart_item.user_id != user_id:
            return Response({'detail': 'This cart entry does not belong to the specified user.'},
                            status=status.HTTP_403_FORBIDDEN)

        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'detail': 'The user_id parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_id = int(user_id)
        except ValueError:
            return Response({'detail': 'The user_id parameter must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)

        cart_item = self.get_object()

        if cart_item.user_id != user_id:
            return Response({'detail': 'This cart entry does not belong to the specified user.'},
                            status=status.HTTP_403_FORBIDDEN)

        return super().destroy(request, *args, **kwargs)
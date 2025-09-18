from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response


class ProductLimitPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100
    limit_query_param = 'limit'
    offset_query_param = 'offset'

    def get_paginated_response(self, data):
        return Response({
            'total_count': len(data),
            'results': data
        })

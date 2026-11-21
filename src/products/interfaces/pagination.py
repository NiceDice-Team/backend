from rest_framework.exceptions import ValidationError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from common.validation import INT64_MAX


class ProductLimitPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100
    min_limit = 1
    max_offset = INT64_MAX
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    unsupported_params = ('page', 'page_size')

    def paginate_queryset(self, queryset, request, view=None):
        self._reject_unsupported_params(request)
        return super().paginate_queryset(queryset, request, view=view)

    def _reject_unsupported_params(self, request):
        for param in self.unsupported_params:
            if param in request.query_params:
                raise ValidationError({
                    param: (
                        f'Parameter "{param}" is not supported. '
                        f'Use "limit" ({self.min_limit}-{self.max_limit}) and "offset" instead.'
                    )
                })

    def get_limit(self, request):
        value = request.query_params.get(self.limit_query_param)
        if value is None:
            return self.default_limit
        try:
            limit = int(value)
        except (TypeError, ValueError):
            raise ValidationError({self.limit_query_param: 'A valid integer is required.'})
        if limit < self.min_limit:
            raise ValidationError(
                {self.limit_query_param: f'Limit must be greater than or equal to {self.min_limit}.'}
            )
        if limit > self.max_limit:
            raise ValidationError(
                {self.limit_query_param: f'Limit must not exceed {self.max_limit}.'}
            )
        return limit

    def get_offset(self, request):
        value = request.query_params.get(self.offset_query_param)
        if value is None:
            return 0
        try:
            offset = int(value)
        except (TypeError, ValueError):
            raise ValidationError({self.offset_query_param: 'A valid integer is required.'})
        if offset < 0:
            raise ValidationError(
                {self.offset_query_param: 'Offset must be greater than or equal to 0.'}
            )
        if offset > self.max_offset:
            raise ValidationError(
                {self.offset_query_param: f'Offset must not exceed {self.max_offset}.'}
            )
        return offset

    def get_paginated_response(self, data):
        return Response({
            'count': self.count,
            'total_count': self.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })

    def get_paginated_response_schema(self, schema):
        response_schema = super().get_paginated_response_schema(schema)
        response_schema['properties'] = {
            'count': response_schema['properties']['count'],
            'total_count': {'type': 'integer', 'example': 123},
            **{key: value for key, value in response_schema['properties'].items() if key != 'count'},
        }
        response_schema['required'] = ['count', 'total_count', 'next', 'previous', 'results']
        return response_schema

    def get_schema_operation_parameters(self, view):
        parameters = super().get_schema_operation_parameters(view)
        for parameter in parameters:
            if parameter['name'] == self.limit_query_param:
                parameter['description'] = (
                    f'Кількість товарів на сторінці. Дозволений діапазон: {self.min_limit}-{self.max_limit}, '
                    'значення поза діапазоном повертають 400.'
                )
                parameter['schema'] = {
                    'type': 'integer', 'minimum': self.min_limit, 'maximum': self.max_limit,
                    'default': self.default_limit,
                }
            elif parameter['name'] == self.offset_query_param:
                parameter['description'] = 'Зміщення для пагінації. Ціле число від 0, інакше повертається 400.'
                parameter['schema'] = {'type': 'integer', 'minimum': 0, 'maximum': self.max_offset, 'default': 0}
        return parameters

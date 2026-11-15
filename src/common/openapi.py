import re

from django.db import models
from drf_standardized_errors.openapi import AutoSchema
from drf_standardized_errors.openapi_serializers import ClientErrorEnum, ValidationErrorEnum
from rest_framework import serializers
from rest_framework.permissions import SAFE_METHODS

NO_NULL_CHARACTER_PATTERN = '^[^\\u0000]*$'
NOT_BLANK_PATTERN = '\\S'

DECIMAL_DIGITS_PATTERN = re.compile(r'\\d\{0,(\d+)\}')

LENIENT_QUERY_PARAMETERS = {'search', 'ordering', 'brand', 'categories', 'types', 'audiences', 'product_id'}


class ErrorCode409Enum(models.TextChoices):
    CONFLICT = 'conflict'


class Error401Serializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ErrorResponse401Serializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ClientErrorEnum.choices)
    errors = Error401Serializer(many=True)


class Error409Serializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=ErrorCode409Enum.choices)
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class ErrorResponse409Serializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ClientErrorEnum.choices)
    errors = Error409Serializer(many=True)


class QueryValidationErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    attr = serializers.CharField(allow_null=True)


class QueryValidationErrorResponseSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ValidationErrorEnum.choices)
    errors = QueryValidationErrorSerializer(many=True)


class ApiAutoSchema(AutoSchema):

    def get_auth(self):
        auths = super().get_auth()
        if self.method in SAFE_METHODS and {} not in auths:
            permissions = self.view.get_permissions()
            if any(getattr(permission, 'allows_anonymous_reads', False) for permission in permissions):
                auths.append({})
        return auths

    def _should_add_error_response(self, responses, status_code):
        should_add = super()._should_add_error_response(responses, status_code)
        if status_code == '409':
            return should_add and self.method == 'DELETE'
        return should_add

    def _has_query_parameters(self):
        return any(parameter.get('in') == 'query' for parameter in self._get_parameters())

    def _should_add_validation_error_response(self):
        if self.method == 'GET' and self._has_query_parameters():
            return True
        return super()._should_add_validation_error_response()

    def _get_serializer_for_validation_error_response(self):
        if self.method == 'GET':
            return QueryValidationErrorResponseSerializer
        return super()._get_serializer_for_validation_error_response()

    def _get_parameters(self):
        parameters = super()._get_parameters()
        for parameter in parameters:
            if parameter.get('in') == 'query':
                self._normalize_query_parameter(parameter)
        return parameters

    @staticmethod
    def _normalize_query_parameter(parameter):
        name = parameter.get('name')
        schema = parameter.get('schema') or {}
        if name == 'page':
            parameter['schema'] = {'type': 'integer', 'minimum': 1}
            parameter['allowEmptyValue'] = True
        elif name == 'search':
            parameter['schema'] = {**schema, 'pattern': NO_NULL_CHARACTER_PATTERN}
            parameter['allowEmptyValue'] = True
        elif name in LENIENT_QUERY_PARAMETERS and not parameter.get('required'):
            parameter['allowEmptyValue'] = True

    def _map_serializer_field(self, field, direction, bypass_extensions=False):
        schema = super()._map_serializer_field(field, direction, bypass_extensions)
        if isinstance(field, serializers.DecimalField) and isinstance(schema, dict):
            return self._require_decimal_digit(schema)
        if not isinstance(schema, dict) or not self._is_required_text(field, schema):
            return schema
        schema = {**schema, 'minLength': max(schema.get('minLength', 0), 1)}
        if getattr(field, 'trim_whitespace', False) and 'pattern' not in schema:
            schema['pattern'] = NOT_BLANK_PATTERN
        return schema

    @staticmethod
    def _require_decimal_digit(schema):
        pattern = schema.get('pattern')
        if schema.get('format') != 'decimal' or not pattern:
            return schema
        return {**schema, 'pattern': DECIMAL_DIGITS_PATTERN.sub(r'\\d{1,\1}', pattern, count=1)}

    @staticmethod
    def _is_required_text(field, schema):
        if not isinstance(field, serializers.CharField) or field.read_only or field.allow_blank:
            return False
        if schema.get('type') != 'string' or 'enum' in schema or 'format' in schema:
            return False
        return True

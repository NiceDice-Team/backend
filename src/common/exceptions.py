from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError, RestrictedError
from django.db.utils import DataError
from drf_standardized_errors.handler import ExceptionHandler, exception_handler as standardized_exception_handler
from rest_framework import exceptions, status
from rest_framework.serializers import as_serializer_error
from rest_framework_simplejwt.exceptions import DetailDictMixin

TOKEN_NOT_VALID_DETAIL = (
    'Access token is invalid or expired. Send a valid Bearer access token or refresh it before retrying.'
)


class Conflict(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'The request conflicts with the current state of the resource.'
    default_code = 'conflict'


def add_legacy_error_keys(status_code, data):
    if not isinstance(data, dict):
        return data
    if status_code == status.HTTP_401_UNAUTHORIZED:
        serialized = str(data)
        if 'token_not_valid' in serialized or 'Given token not valid' in serialized:
            return {**data, 'code': 'TOKEN_NOT_VALID', 'detail': TOKEN_NOT_VALID_DETAIL}
    if status_code == status.HTTP_400_BAD_REQUEST and data.get('type') == 'validation_error':
        by_attr = {}
        for error in data.get('errors', []):
            by_attr.setdefault(error.get('attr'), error.get('detail'))
        if 'code' in by_attr and 'message' in by_attr:
            return {**data, 'code': by_attr['code'], 'field': by_attr.get('field'), 'message': by_attr['message']}
    return data


def flatten_detail_dict_exception(exc):
    detail = exc.detail
    message = str(detail.get('detail', exc.default_detail))
    code = str(detail.get('code', exc.default_code))
    converted = exceptions.AuthenticationFailed(detail=message, code=code)
    converted.status_code = exc.status_code
    converted.auth_header = getattr(exc, 'auth_header', None)
    return converted


def is_null_character_error(exc):
    return isinstance(exc, ValueError) and 'NUL' in str(exc) and '0x00' in str(exc)


class ApiExceptionHandler(ExceptionHandler):

    def convert_known_exceptions(self, exc):
        exc = super().convert_known_exceptions(exc)
        if isinstance(exc, DetailDictMixin) and isinstance(exc.detail, dict):
            return flatten_detail_dict_exception(exc)
        if is_null_character_error(exc):
            return exceptions.ValidationError(
                detail=[exceptions.ErrorDetail('Null characters are not allowed.', code='null_characters_not_allowed')]
            )
        if isinstance(exc, DjangoValidationError):
            return exceptions.ValidationError(detail=as_serializer_error(exc))
        if isinstance(exc, (ProtectedError, RestrictedError)):
            return Conflict('The object is referenced by other records and cannot be deleted.')
        if isinstance(exc, (OverflowError, DataError)):
            return exceptions.ValidationError(
                detail={'non_field_errors': ['A numeric or text value is outside the supported range.']}
            )
        return exc

    def get_response(self, exc, data):
        response = super().get_response(exc, data)
        response.data = add_legacy_error_keys(response.status_code, response.data)
        return response


def api_exception_handler(exc, context):
    return standardized_exception_handler(exc, context)

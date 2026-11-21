import json

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


@extend_schema_field({
    'oneOf': [
        {'type': 'string', 'format': 'uri', 'maxLength': 1000},
        {'type': 'string', 'enum': ['']},
    ]
})
class OptionalURLField(serializers.URLField):
    pass


PASSWORD_PATTERN = r'^(?=.*[A-Za-z])(?=.*[0-9])[!-~]+$'


@extend_schema_field({
    'type': 'string',
    'format': 'password',
    'minLength': 8,
    'maxLength': 128,
    'pattern': PASSWORD_PATTERN,
})
class StrongPasswordField(serializers.CharField):
    pass


NON_NULL_JSON_SCHEMA = {
    'anyOf': [
        {'type': 'object'},
        {'type': 'array', 'items': {}},
        {'type': 'string'},
        {'type': 'number'},
        {'type': 'boolean'},
    ]
}


@extend_schema_field(NON_NULL_JSON_SCHEMA)
class NonNullJSONField(serializers.JSONField):

    def to_internal_value(self, data):
        if getattr(data, 'is_json_string', False):
            try:
                value = json.loads(data)
            except ValueError:
                value = str(data)
        else:
            value = super().to_internal_value(data)
        if value is None:
            self.fail('null')
        return value


NAME_PATTERN = "^\\s*[a-zA-Z'\\-][a-zA-Z\\s'\\-]*$"


@extend_schema_field({
    'type': 'string',
    'minLength': 1,
    'maxLength': 150,
    'pattern': NAME_PATTERN,
})
class PersonNameField(serializers.CharField):
    pass


@extend_schema_field({'type': 'boolean', 'enum': [True]})
class AcceptedBooleanField(serializers.BooleanField):
    pass

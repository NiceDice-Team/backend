from django.urls import register_converter
from django.urls.converters import get_converters

INT64_MAX = 9223372036854775807
ID_CONVERTER_NAME = 'id'

ID_PATH_SCHEMA = {'type': 'integer', 'format': 'int64', 'minimum': 0, 'maximum': INT64_MAX}


class BoundedIntConverter:
    regex = '[0-9]+'

    def to_python(self, value):
        number = int(value)
        if number > INT64_MAX:
            raise ValueError(value)
        return number

    def to_url(self, value):
        return str(value)


def register_bounded_int_converter():
    if ID_CONVERTER_NAME not in get_converters():
        register_converter(BoundedIntConverter, ID_CONVERTER_NAME)

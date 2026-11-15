from rest_framework.exceptions import ValidationError

INT64_MIN = -9223372036854775808
INT64_MAX = 9223372036854775807


def parse_int_param(value, name):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({name: ['A valid integer is required.']})


def filter_by_int_param(queryset, lookup, value, name):
    number = parse_int_param(value, name)
    if number is None:
        return queryset
    if number < INT64_MIN or number > INT64_MAX:
        return queryset.none()
    return queryset.filter(**{lookup: number})

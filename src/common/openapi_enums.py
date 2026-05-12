from django.db import models


class ErrorCode401EnumWithJwt(models.TextChoices):
    AUTHENTICATION_FAILED = 'authentication_failed', 'Authentication Failed'
    NOT_AUTHENTICATED = 'not_authenticated', 'Not Authenticated'
    TOKEN_NOT_VALID = 'token_not_valid', 'Token Not Valid'

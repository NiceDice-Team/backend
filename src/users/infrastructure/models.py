from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True, validators=[MinLengthValidator(1)])
    subscribe_news = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    @property
    def admin(self):
        return self.is_staff or self.is_superuser

    def __str__(self):
        return self.email

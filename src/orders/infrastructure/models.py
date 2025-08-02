from django.db import models
from products.infrastructure.models import Product


class Order(models.Model):
    products = models.ManyToManyField(Product)
    created_at = models.DateTimeField(auto_now_add=True)

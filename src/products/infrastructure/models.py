import logging
from django.db import models
from django.utils.text import slugify
from categories.infrastructure.models import Category
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class GameType(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Audience(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    types = models.ManyToManyField(GameType, related_name='products', blank=True)
    categories = models.ManyToManyField(Category, related_name='products')
    audiences = models.ManyToManyField(Audience, related_name='products', blank=True)

    brand = models.ForeignKey(
        Brand,
        on_delete=models.PROTECT,
        related_name='products'
    )

    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        help_text='Percentage discount, e.g. 15.00'
    )
    stock = models.PositiveIntegerField(default=0)
    stars = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def clean(self):
        if self.price is not None and self.price <= 0:
            raise ValidationError({'price': 'Ціна повинна бути більшою за 0.'})


class ProductImage(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='images')
    url_original = models.URLField(max_length=1000, blank=True)
    url_lg = models.URLField(max_length=1000, blank=True)
    url_md = models.URLField(max_length=1000, blank=True)
    url_sm = models.URLField(max_length=1000, blank=True)
    alt = models.CharField(max_length=255, blank=True)
    sort = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort']

    def __str__(self):
        return f'Image ID {self.id} for Product {self.product.id}'


class Review(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    rating = models.DecimalField(
        max_digits=3, decimal_places=2,
        help_text='Score, e.g. 4.50'
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Review {self.rating} for {self.product.name}'

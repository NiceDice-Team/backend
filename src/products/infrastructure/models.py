from django.db import models
from django.utils.text import slugify
from categories.infrastructure.models import Category


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
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images'
    )
    url = models.URLField(max_length=1000)

    def __str__(self):
        return f'Image for {self.product.name} - {self.url}'


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

import logging
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.text import slugify
from categories.infrastructure.models import Category
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

User = get_user_model()


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

    short_description = models.TextField(blank=True, help_text="Короткий опис продукту (до 255 символів).")
    game_information = models.JSONField(default=dict, blank=True, help_text="Структурована інфа про гру.")
    delivery_and_payments = models.TextField(blank=True, help_text="Інформація про доставку та способи оплати.")

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
        help_text='Percentage discount, e.g. 15.00',
        validators=[
            MinValueValidator(Decimal('0.00'), message="Знижка не може бути менше 0%."),
            MaxValueValidator(Decimal('100.00'), message="Знижка не може бути більше 100%.")
        ]
    )
    stock = models.IntegerField(default=0, help_text="Кількість на складі. '-1' для статусу 'Coming soon'.")
    stars = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def build_unique_slug(self):
        base = slugify(self.name or '')[:240].strip('-') or 'product'
        others = Product.objects.exclude(pk=self.pk) if self.pk else Product.objects.all()
        slug = base
        suffix = 2
        while others.filter(slug=slug).exists():
            slug = f'{base}-{suffix}'
            suffix += 1
        return slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.build_unique_slug()
        self.full_clean()
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
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews', null=True)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Rating from 1 to 5'
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product'],
                name='uniq_review_user_product'
            )
        ]

    def __str__(self):
        return f'Review {self.rating} for {self.product.name} by {self.user.email if self.user else "Anonymous"}'

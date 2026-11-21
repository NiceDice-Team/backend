import logging
import secrets
import string
from datetime import timedelta
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from products.infrastructure.models import Product

logger = logging.getLogger(__name__)


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.user.email if self.user else 'Anonymous'}"

    class Meta:
        db_table = 'carts'

    @classmethod
    def get_active_for_user(cls, user):
        cart, created = cls.objects.get_or_create(user=user, defaults={'is_active': True})
        if not created and not cart.is_active:
            with transaction.atomic():
                cart.items.all().delete()
                cart.is_active = True
                cart.save(update_fields=['is_active', 'updated_at'])
        return cart


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    sku = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=500, blank=True)
    attrs = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cart', 'product')
        db_table = 'cart_items'

    def __str__(self):
        return f"{self.quantity}x {self.product.name} in cart {self.cart.id}"


class GuestCart(models.Model):
    token = models.CharField(max_length=64, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'guest_carts'
        verbose_name = 'Гостевая корзина'
        verbose_name_plural = 'Гостевые корзины'

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self._generate_token()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def _generate_token(self):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(64))

    def is_expired(self):
        return timezone.now() > self.expires_at

    def extend_expiration(self, hours=24):
        self.expires_at = timezone.now() + timedelta(hours=hours)
        self.save()

    @classmethod
    def create_guest_cart(cls):
        return cls.objects.create()

    @classmethod
    def get_by_token(cls, token, allow_expired=False):
        if not token:
            return None

        try:
            guest_cart = cls.objects.get(token=token)
        except cls.DoesNotExist:
            return None

        if not guest_cart.is_active:
            return None

        if guest_cart.is_expired() and not allow_expired:
            return None

        return guest_cart

    def refresh_if_needed(self, grace_hours=24, ttl_hours=24):
        if not self.is_active:
            return False

        now = timezone.now()

        if self.is_expired():
            grace_deadline = self.expires_at + timedelta(hours=grace_hours)

            if now > grace_deadline:
                self.delete_with_items()
                return False

        self.expires_at = now + timedelta(hours=ttl_hours)
        self.save(update_fields=['expires_at', 'updated_at'])

        return True

    def delete_with_items(self):
        self.items.all().delete()
        self.delete()

    def __str__(self):
        return f"GuestCart {self.token[:8]}... (expires: {self.expires_at})"


class GuestCartItem(models.Model):
    guest_cart = models.ForeignKey(GuestCart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    sku = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=500, blank=True)
    attrs = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('guest_cart', 'product')
        db_table = 'guest_cart_items'

    def __str__(self):
        return f"{self.quantity}x {self.title} in GuestCart {self.guest_cart.token[:8]}"


class GuestCheckoutSession(models.Model):
    session_token = models.CharField(max_length=64, unique=True, db_index=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    guest_cart = models.ForeignKey(
        'GuestCart',
        on_delete=models.CASCADE,
        related_name='checkout_sessions',
        null=True,
        blank=True
    )
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'guest_checkout_sessions'

    def save(self, *args, **kwargs):
        if not self.session_token:
            self.session_token = self._generate_token()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=2)
        super().save(*args, **kwargs)

    def _generate_token(self):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(64))

    def is_expired(self):
        return timezone.now() > self.expires_at

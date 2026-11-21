from decimal import Decimal

from django.db import models

from cart.infrastructure.models import Cart
from products.infrastructure.models import Product
from users.infrastructure.models import User


class DeliveryOption(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_days = models.PositiveIntegerField(help_text="Estimated delivery time in days")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} (about {self.estimated_days} days, {self.price} USD)"


class PaymentMethod(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    cart = models.ForeignKey(Cart, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    shipping_address = models.TextField()
    billing_address = models.TextField(blank=True, help_text="Якщо не вказано, використовується адреса доставки")
    delivery_option = models.ForeignKey('DeliveryOption', on_delete=models.PROTECT, null=True, blank=True)
    payment_method = models.ForeignKey('PaymentMethod', on_delete=models.PROTECT, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    ORDER_STATUS = [
        ('pending', 'Нове замовлення'),
        ('processing', 'Обробляється'),
        ('shipped', 'Відправлено'),
        ('delivered', 'Доставлено'),
        ('cancelled', 'Скасовано'),
    ]

    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.user_id:
            return f"Замовлення {self.id} користувача {self.user.email}"
        return f"Замовлення {self.id} гостя"

    @property
    def subtotal(self):
        if self.pk:
            return sum((item.subtotal for item in self.items.all()), Decimal('0.00'))
        else:
            return Decimal('0.00')

    @property
    def shipping_cost(self):
        if self.delivery_option:
            return Decimal(str(self.delivery_option.price))
        return Decimal('0.00')

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.full_clean()
        if not self.billing_address:
            self.billing_address = self.shipping_address
        if not is_new:
            self.total_amount = self.subtotal + self.shipping_cost
        super().save(*args, **kwargs)


ORDER_STATUS_CHOICES = Order.ORDER_STATUS


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} для замовлення {self.order.id}"

    @property
    def subtotal(self):
        return Decimal(str(self.quantity)) * Decimal(str(self.price))


class OrderStatusLog(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_logs')
    previous_status = models.CharField(max_length=20, choices=Order.ORDER_STATUS, null=True, blank=True)
    new_status = models.CharField(max_length=20, choices=Order.ORDER_STATUS)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='order_status_changes')
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_status_logs'
        ordering = ['-changed_at']
        verbose_name = 'Лог зміни статусу замовлення'
        verbose_name_plural = 'Логи змін статусів замовлень'

    def __str__(self):
        return f"Order {self.order.id} status: {self.previous_status} -> {self.new_status}"

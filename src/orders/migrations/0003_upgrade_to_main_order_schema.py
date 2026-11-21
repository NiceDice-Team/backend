import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0003_upgrade_to_main_cart_schema'),
        ('orders', '0002_order_updated_at'),
        ('products', '0004_review_user_alter_review_rating'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DeliveryOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('estimated_days', models.PositiveIntegerField(help_text='Estimated delivery time in days')),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='order',
            name='products',
        ),
        migrations.AddField(
            model_name='order',
            name='billing_address',
            field=models.TextField(blank=True, default='', help_text='Якщо не вказано, використовується адреса доставки'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='cart',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', to='cart.cart'),
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_address',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='order',
            name='total_amount',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='order',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='orderitem',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='products.product'),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_option',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='orders.deliveryoption'),
        ),
        migrations.CreateModel(
            name='OrderStatusLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('previous_status', models.CharField(blank=True, choices=[('pending', 'Нове замовлення'), ('processing', 'Обробляється'), ('shipped', 'Відправлено'), ('delivered', 'Доставлено'), ('cancelled', 'Скасовано')], max_length=20, null=True)),
                ('new_status', models.CharField(choices=[('pending', 'Нове замовлення'), ('processing', 'Обробляється'), ('shipped', 'Відправлено'), ('delivered', 'Доставлено'), ('cancelled', 'Скасовано')], max_length=20)),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_status_changes', to=settings.AUTH_USER_MODEL)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='status_logs', to='orders.order')),
            ],
            options={
                'verbose_name': 'Лог зміни статусу замовлення',
                'verbose_name_plural': 'Логи змін статусів замовлень',
                'db_table': 'order_status_logs',
                'ordering': ['-changed_at'],
            },
        ),
        migrations.AddField(
            model_name='order',
            name='payment_method',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='orders.paymentmethod'),
        ),
    ]

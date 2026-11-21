import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def move_legacy_items_to_carts(apps, schema_editor):
    Cart = apps.get_model('cart', 'Cart')
    CartItem = apps.get_model('cart', 'CartItem')
    database = schema_editor.connection.alias

    carts_by_user = {}
    for item in CartItem.objects.using(database).all().iterator():
        cart_id = carts_by_user.get(item.user_id)
        if cart_id is None:
            cart, _ = Cart.objects.using(database).get_or_create(user_id=item.user_id)
            cart_id = cart.pk
            carts_by_user[item.user_id] = cart_id
        item.cart_id = cart_id
        item.save(update_fields=['cart'])


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0002_initial'),
        ('products', '0004_review_user_alter_review_rating'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GuestCart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(db_index=True, max_length=64, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Гостевая корзина',
                'verbose_name_plural': 'Гостевые корзины',
                'db_table': 'guest_carts',
            },
        ),
        migrations.AddField(
            model_name='cartitem',
            name='added_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='cartitem',
            name='attrs',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='cartitem',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='cartitem',
            name='sku',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='cartitem',
            name='title',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='cartitem',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterModelTable(
            name='cartitem',
            table='cart_items',
        ),
        migrations.CreateModel(
            name='Cart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='cart', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'carts'},
        ),
        migrations.AlterUniqueTogether(
            name='cartitem',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='cartitem',
            name='cart',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='items', to='cart.cart'),
        ),
        migrations.RunPython(move_legacy_items_to_carts, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='cartitem',
            name='cart',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='cart.cart'),
        ),
        migrations.RemoveField(
            model_name='cartitem',
            name='user',
        ),
        migrations.AlterUniqueTogether(
            name='cartitem',
            unique_together={('cart', 'product')},
        ),
        migrations.CreateModel(
            name='GuestCheckoutSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_token', models.CharField(db_index=True, max_length=64, unique=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('phone', models.CharField(blank=True, max_length=20, null=True)),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('guest_cart', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='checkout_sessions', to='cart.guestcart')),
            ],
            options={'db_table': 'guest_checkout_sessions'},
        ),
        migrations.CreateModel(
            name='GuestCartItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('sku', models.CharField(blank=True, max_length=255)),
                ('title', models.CharField(blank=True, max_length=500)),
                ('attrs', models.JSONField(blank=True, default=dict)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('guest_cart', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='cart.guestcart')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='products.product')),
            ],
            options={
                'db_table': 'guest_cart_items',
                'unique_together': {('guest_cart', 'product')},
            },
        ),
    ]

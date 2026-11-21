from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('categories', '0002_alter_category_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='slug',
            field=models.SlugField(allow_unicode=True, blank=True, max_length=100, unique=True),
        ),
    ]

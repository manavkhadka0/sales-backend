# Generated by Django 5.1.4 on 2025-02-25 05:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0021_product_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='name',
            field=models.CharField(choices=[('Dandruff Oil Bottle', 'Dandruff Oil Bottle'), ('Hairfall Oil Bottle', 'Hairfall Oil Bottle'), ('Baldness Oil Bottle', 'Baldness Oil Bottle'), ('Hair Oil Sachet', 'Hair Oil Sachet'), ('Shampoo Bottle', 'Shampoo Bottle'), ('Shampoo Sachet', 'Shampoo Sachet'), ('Raw bottle', 'Raw bottle'), ('Sticker', 'Sticker')], max_length=255),
        ),
    ]

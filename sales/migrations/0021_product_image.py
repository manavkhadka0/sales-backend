# Generated by Django 5.1.4 on 2025-02-20 09:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0020_alter_orderproduct_product'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='image',
            field=models.FileField(blank=True, null=True, upload_to='products/'),
        ),
    ]

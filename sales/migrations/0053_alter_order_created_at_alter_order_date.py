# Generated by Django 5.1.4 on 2025-06-06 05:28

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0052_alter_order_payment_method'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name='order',
            name='date',
            field=models.DateField(default=django.utils.timezone.now),
        ),
    ]

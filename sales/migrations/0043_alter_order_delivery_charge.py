# Generated by Django 5.1.4 on 2025-03-23 06:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0042_alter_promocode_valid_from_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='delivery_charge',
            field=models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=10, null=True),
        ),
    ]

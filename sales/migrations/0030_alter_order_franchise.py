# Generated by Django 5.1.4 on 2025-03-03 10:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0009_customuser_factory'),
        ('sales', '0029_alter_inventorychangelog_action'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='franchise',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='account.franchise'),
        ),
    ]

# Generated by Django 5.1.4 on 2025-03-04 05:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0032_alter_inventorychangelog_action'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inventorychangelog',
            name='action',
            field=models.CharField(choices=[('add', 'Add'), ('update', 'Update'), ('deleted', 'Deleted'), ('order_created', 'Order Created'), ('order_cancelled', 'Order Cancelled')], default='update', max_length=20),
        ),
    ]

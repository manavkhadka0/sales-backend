# Generated by Django 5.1.4 on 2025-03-07 07:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0036_alter_inventory_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inventory',
            name='status',
            field=models.CharField(blank=True, choices=[('incoming', 'Incoming'), ('raw_material', 'Raw Material'), ('ready_to_dispatch', 'Ready to Dispatch'), ('damaged_returned', 'Damaged/Returned')], default='ready_to_dispatch', max_length=255, null=True),
        ),
    ]

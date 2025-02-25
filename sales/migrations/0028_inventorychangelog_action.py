# Generated by Django 5.1.4 on 2025-02-25 09:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0027_alter_inventorychangelog_inventory'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventorychangelog',
            name='action',
            field=models.CharField(choices=[('add', 'Add'), ('update', 'Update'), ('deleted', 'Deleted')], default='update', max_length=20),
        ),
    ]

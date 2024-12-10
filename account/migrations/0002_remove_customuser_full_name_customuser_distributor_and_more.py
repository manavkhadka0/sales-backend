# Generated by Django 5.1.4 on 2024-12-10 10:53

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customuser',
            name='full_name',
        ),
        migrations.AddField(
            model_name='customuser',
            name='distributor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='account.distributor'),
        ),
        migrations.AddField(
            model_name='distributor',
            name='name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='distributor',
            name='short_form',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]

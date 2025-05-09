# Generated by Django 5.1.4 on 2024-12-10 13:26

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0002_remove_customuser_full_name_customuser_distributor_and_more'),
        ('sales', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='image',
        ),
        migrations.RemoveField(
            model_name='product',
            name='stock',
        ),
        migrations.AlterField(
            model_name='product',
            name='description',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='product',
            name='name',
            field=models.CharField(choices=[('Dandruff Oil Bottle', 'Dandruff Oil Bottle'), ('Hairfall Oil Bottle', 'Hairfall Oil Bottle'), ('Baldness Oil Bottle', 'Baldness Oil Bottle'), ('Hair Oil Sachet', 'Hair Oil Sachet'), ('Shampoo Bottle', 'Shampoo Bottle'), ('Shampoo Sachet', 'Shampoo Sachet')], max_length=255),
        ),
        migrations.CreateModel(
            name='Inventory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=0)),
                ('distributor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='inventory', to='account.distributor')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inventory', to='sales.product')),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=200)),
                ('city', models.CharField(blank=True, max_length=200)),
                ('delivery_address', models.CharField(max_length=200)),
                ('landmark', models.CharField(blank=True, max_length=255)),
                ('phone_number', models.CharField(max_length=20)),
                ('alternate_phone_number', models.CharField(blank=True, max_length=20)),
                ('delivery_charge', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('payment_method', models.CharField(choices=[('Cash on Delivery', 'Cash on Delivery'), ('Prepaid', 'Prepaid')], max_length=255)),
                ('payment_screenshot', models.ImageField(blank=True, null=True, upload_to='payment_screenshots/')),
                ('order_status', models.CharField(choices=[('Pending', 'Pending'), ('Processing', 'Processing'), ('Shipped', 'Shipped'), ('Delivered', 'Delivered'), ('Cancelled', 'Cancelled')], default='Pending', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('total_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('remarks', models.TextField(blank=True)),
                ('distributor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='account.distributor')),
                ('sales_person', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='OrderProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('discount', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='order_products', to='sales.order')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sales.product')),
            ],
        ),
    ]

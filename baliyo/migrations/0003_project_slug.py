# Generated by Django 5.1.4 on 2025-01-02 08:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('baliyo', '0002_alter_project_document_no'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='slug',
            field=models.SlugField(blank=True, max_length=100, null=True, unique=True),
        ),
    ]
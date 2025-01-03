# Generated by Django 5.1.4 on 2025-01-02 06:02

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('department', models.CharField(choices=[('Software', 'Software'), ('Mechanical', 'Mechanical')], max_length=100)),
                ('document_no', models.CharField(max_length=100)),
                ('project_name', models.CharField(max_length=100)),
                ('date', models.DateField()),
                ('version', models.CharField(max_length=100)),
                ('project_description', models.TextField()),
                ('project_objective', models.TextField()),
                ('technical_requirements', models.TextField()),
                ('concept_design', models.FileField(upload_to='concept_design/')),
                ('technical_drawing', models.FileField(upload_to='technical_drawing/')),
                ('model_3d', models.FileField(upload_to='model_3d/')),
                ('project_plan', models.TextField()),
                ('timeline', models.TextField()),
                ('resource_allocation', models.TextField()),
                ('budget_breakdown', models.TextField()),
                ('quality_assurance', models.TextField()),
                ('progess_report', models.TextField()),
                ('issues_and_resolution', models.TextField()),
                ('final_deliverables', models.TextField()),
                ('supportive_documents', models.FileField(upload_to='supportive_documents/')),
                ('team', models.ManyToManyField(blank=True, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]

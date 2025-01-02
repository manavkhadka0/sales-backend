from django.db import models

# Create your models here.
class Project(models.Model):

    DEPARTMENT=(
        ('Software','Software'),
        ('Mechanical','Mechanical'),
    )
    team = models.ManyToManyField('account.CustomUser', blank=True)    
    department=models.CharField(max_length=100,choices=DEPARTMENT)
    document_no=models.CharField(max_length=100,unique=True)
    project_name = models.CharField(max_length=100)
    date=models.DateField()
    version=models.CharField(max_length=100)
    project_description = models.TextField()
    project_objective = models.TextField()
    technical_requirements = models.TextField()
    concept_design=models.FileField(upload_to='concept_design/')
    technical_drawing=models.FileField(upload_to='technical_drawing/')
    model_3d=models.FileField(upload_to='model_3d/')
    project_plan=models.TextField()
    timeline=models.TextField()
    resource_allocation=models.TextField()
    budget_breakdown=models.TextField()
    quality_assurance=models.TextField()
    progess_report=models.TextField()
    issues_and_resolution=models.TextField()
    final_deliverables=models.TextField()
    supportive_documents=models.FileField(upload_to='supportive_documents/')
    
    def __str__(self):
        return self.project_name

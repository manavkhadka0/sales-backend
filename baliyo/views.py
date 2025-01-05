from django.shortcuts import render, get_object_or_404
from rest_framework import generics
from django.utils.html import  format_html
from .models import Project
from .serializers import ProjectSerializer
from django.template.loader import render_to_string
from django.http import HttpResponse
from xhtml2pdf import pisa  # Import xhtml2pdf
from django.utils.text import slugify  # Import slugify to create a safe filename

# Create your views here.

class ProjectListCreateView(generics.ListCreateAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
from django.conf import settings

def download_project_pdf(request, project_slug):
    project = get_object_or_404(Project, slug=project_slug)


    # Prepare the context for rendering
    context = {
        'project': project,
        'project_description': format_html(project.project_description),
        'project_objective': format_html(project.project_objective),
        'technical_requirements': format_html(project.technical_requirements),
        'project_plan': format_html(project.project_plan),
        'timeline': format_html(project.timeline),
        'resource_allocation': format_html(project.resource_allocation),
        'budget_breakdown': format_html(project.budget_breakdown),
        'quality_assurance': format_html(project.quality_assurance),
        'progess_report': format_html(project.progess_report),
        'issues_and_resolution': format_html(project.issues_and_resolution),
        'final_deliverables': format_html(project.final_deliverables),
        'concept_design_url': request.build_absolute_uri(project.concept_design.url) if project.concept_design else None,
        'technical_drawing_url': request.build_absolute_uri(project.technical_drawing.url) if project.technical_drawing else None,
        'model_3d_url': request.build_absolute_uri(project.model_3d.url) if project.model_3d else None,
        'supportive_documents_url': request.build_absolute_uri(project.supportive_documents.url) if project.supportive_documents else None,
    }

    # Render the HTML template with context
    html_string = render_to_string('project_pdf.html', context)

    # Create a safe filename based on the project name
    safe_project_name = slugify(project.project_name)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{safe_project_name}_project.pdf"'

    # Convert HTML to PDF using xhtml2pdf
    pisa_status = pisa.CreatePDF(html_string, dest=response)

    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html_string + '</pre>')

    return response
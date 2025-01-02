from django.urls import path
from .views import ProjectListCreateView, download_project_pdf

urlpatterns = [
    path('projects/', ProjectListCreateView.as_view(), name='project-list-create'),
    path('projects/<int:project_id>/download/', download_project_pdf, name='download-project-pdf'),
]

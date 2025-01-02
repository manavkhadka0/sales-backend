from django.urls import path
from .views import ProjectListCreateView, download_project_pdf

urlpatterns = [
    path('projects/', ProjectListCreateView.as_view(), name='project-list-create'),
    path('projects/download/<slug:project_slug>/', download_project_pdf, name='download_project_pdf'),
]

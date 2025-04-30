from django.urls import path
from .views import (
    CustomerTreatmentListCreateView,
    CustomerTreatmentDetailView,
    ImageListCreateView,
    ImageDetailView
)

urlpatterns = [
    path('customers/', CustomerTreatmentListCreateView.as_view(),
         name='customer-list-create'),
    path('customers/<int:pk>/', CustomerTreatmentDetailView.as_view(),
         name='customer-detail'),
    path('images/', ImageListCreateView.as_view(), name='image-list-create'),
    path('images/<int:pk>/', ImageDetailView.as_view(), name='image-detail'),
]

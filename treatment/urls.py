from django.urls import path

from .views import (
    CustomerTreatmentDetailView,
    CustomerTreatmentListCreateView,
    ImageDetailView,
    ImageListCreateView,
    PaymentHistoryDetailView,
    PaymentHistoryListCreateView,
)

urlpatterns = [
    path(
        "customers/",
        CustomerTreatmentListCreateView.as_view(),
        name="customer-list-create",
    ),
    path(
        "customers/<int:pk>/",
        CustomerTreatmentDetailView.as_view(),
        name="customer-detail",
    ),
    path("images/", ImageListCreateView.as_view(), name="image-list-create"),
    path("images/<int:pk>/", ImageDetailView.as_view(), name="image-detail"),
    path(
        "payments/", PaymentHistoryListCreateView.as_view(), name="payment-list-create"
    ),
    path(
        "payments/<int:pk>/", PaymentHistoryDetailView.as_view(), name="payment-detail"
    ),
]

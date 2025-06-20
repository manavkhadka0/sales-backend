from django.urls import path
from .views import DashLoginView, SendOrderToDashByIdView, DashListCreateView

urlpatterns = [
    path('login/', DashLoginView.as_view(), name='dash-login'),
    path('send-order/<int:order_id>/',
         SendOrderToDashByIdView.as_view(), name='send-order-to-dash'),
    path('create/', DashListCreateView.as_view(), name='dash-list-create'),
]

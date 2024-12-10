from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import UserListView, LoginView  # Import the LoginView

urlpatterns = [
    path('users/', UserListView.as_view(), name='user-list'),  # Existing user list URL
    path('login/', LoginView.as_view(), name='login'),  # New login URL
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

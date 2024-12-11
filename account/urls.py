from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import UserListView, LoginView, UserProfileView

urlpatterns = [
    path('users/', UserListView.as_view(), name='user-list'),  # Existing user list URL
    path('login/', LoginView.as_view(), name='login'),  # New login URL
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

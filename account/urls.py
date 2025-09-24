from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangePassword,
    DemoUserList,
    DistributorListCreateView,
    FactoryListCreateView,
    FranchiseByDistributorView,
    FranchiseListCreateView,
    LoginView,
    LogisticsDetailView,
    LogisticsListCreateView,
    SalesPersonListView,
    UserDistributorListView,
    UserFranchiseListView,
    UserListView,
    UserProfileView,
    UserRetrieveUpdateDestroyView,
    YDMFranchiseListCreateView,
)

urlpatterns = [
    path("users/", UserListView.as_view(), name="user-list"),  # Existing user list URL
    path(
        "users/<str:phone_number>/",
        UserRetrieveUpdateDestroyView.as_view(),
        name="user-detail",
    ),  # New URL for PATCH and DELETE
    path("login/", LoginView.as_view(), name="login"),  # New login URL
    path("profile/", UserProfileView.as_view(), name="user-profile"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("factories/", FactoryListCreateView.as_view(), name="factory-list-create"),
    path(
        "distributors/",
        DistributorListCreateView.as_view(),
        name="distributor-list-create",
    ),
    path(
        "franchises/",
        FranchiseListCreateView.as_view(),
        name="franchise-by-distributor",
    ),
    path(
        "ydm-franchises/",
        YDMFranchiseListCreateView.as_view(),
        name="ydm-franchise-list-create",
    ),
    path(
        "distributors/<int:distributor_id>/franchises/",
        FranchiseByDistributorView.as_view(),
        name="franchise-by-distributor",
    ),
    path("change-password/", ChangePassword.as_view(), name="change-password"),
    path("my-franchises/", UserFranchiseListView.as_view(), name="user-franchises"),
    path(
        "my-distributors/", UserDistributorListView.as_view(), name="user-distributors"
    ),
    path("logistics/", LogisticsListCreateView.as_view(), name="logistics-list-create"),
    path("logistics/<int:id>/", LogisticsDetailView.as_view(), name="logistics-detail"),
    path("salespersons/", SalesPersonListView.as_view(), name="salesperson-list"),
    path("demo-users/", DemoUserList.as_view(), name="demo-user-list"),
]

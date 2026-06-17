from django.urls import path

from .views import (
    ActiveGameView,
    ChooseRandomConditionView,
    GameDetailView,
    GameListCreateView,
    GameWinnerListView,
)

app_name = "sales_game"

urlpatterns = [
    path("", GameListCreateView.as_view(), name="game-list-create"),
    path("<int:pk>/", GameDetailView.as_view(), name="game-detail"),
    path("active/", ActiveGameView.as_view(), name="active-game"),
    path(
        "choose-condition/",
        ChooseRandomConditionView.as_view(),
        name="choose-random-condition",
    ),
    path("winners/", GameWinnerListView.as_view(), name="game-winners"),
]

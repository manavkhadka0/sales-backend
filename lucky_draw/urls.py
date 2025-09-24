from django.urls import path

from .views import (
    FixOfferListCreateView,
    FixOfferRetrieveUpdateDestroyView,
    GetGiftList,
    GetGifts,
    LuckyDrawSystemListCreateView,
    LuckyDrawSystemRetrieveUpdateDestroyView,
    OfferListCreateView,
    OfferRetrieveUpdateDestroyView,
    SlotMachineListCreateView,
)

urlpatterns = [
    path(
        "lucky-draw-systems/",
        LuckyDrawSystemListCreateView.as_view(),
        name="luckydrawsystem-list-create",
    ),
    path(
        "lucky-draw-systems/<int:pk>/",
        LuckyDrawSystemRetrieveUpdateDestroyView.as_view(),
        name="luckydrawsystem-detail",
    ),
    path(
        "fix-offers/",
        FixOfferListCreateView.as_view(),
        name="fix-offer-list-create",
    ),
    path(
        "fix-offers/<int:pk>/",
        FixOfferRetrieveUpdateDestroyView.as_view(),
        name="fix-offer-detail",
    ),
    path(
        "slot-machine/",
        SlotMachineListCreateView.as_view(),
        name="slot-machine-list-create",
    ),
    path("gifts/", GetGifts, name="get-gifts"),
    path("get-gift-list/", GetGiftList, name="get-gift-list"),
    path(
        "offers/",
        OfferListCreateView.as_view(),
        name="offer-list-create",
    ),
    path(
        "offers/<int:pk>/",
        OfferRetrieveUpdateDestroyView.as_view(),
        name="offer-detail",
    ),
]

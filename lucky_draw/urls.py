from django.urls import path

from .views import (
    FixOfferListCreateView,
    FixOfferRetrieveUpdateDestroyView,
    GetGiftList,
    GetGifts,
    GiftItemListCreateView,
    GiftItemRetrieveUpdateDestroyView,
    LuckyDrawSystemListCreateView,
    LuckyDrawSystemRetrieveUpdateDestroyView,
    OfferListCreateView,
    OfferRetrieveUpdateDestroyView,
    SlotMachineListCreateView,
    download_customers_detail,
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
    path(
        "gift-items/",
        GiftItemListCreateView.as_view(),
        name="gift-item-list-create",
    ),
    path(
        "gift-items/<int:pk>/",
        GiftItemRetrieveUpdateDestroyView.as_view(),
        name="gift-item-detail",
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
    path(
        "export-detail/",
        download_customers_detail,
        name="export-detail",
    ),
]

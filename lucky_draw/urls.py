from django.urls import path
from .views import SlotMachineListCreateView, GetGifts, GetGiftList

urlpatterns = [
    path('slot-machine/', SlotMachineListCreateView.as_view(),
         name='customer-list-create'),
    path('gifts/', GetGifts, name='get-gifts'),
    path("get-gift-list/", GetGiftList, name="get-gift-list"),

]

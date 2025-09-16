from rest_framework import generics, status
import random
from sales.models import Order
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from .models import Customer, FixOffer, ElectronicsShopOffer, Sales, LuckyDrawSystem, GiftItem
from .serializers import CustomerSerializer, CustomerGiftSerializer, GiftItemSerializer
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
# Create your views here.


@api_view(["GET"])
def GetGifts(request):
    luck_draw_system_id = request.GET.get("lucky_draw_system")
    if not luck_draw_system_id:
        return Response(
            {"error": "lucky_draw_system parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    gifts = GiftItem.objects.all()
    serializer = GiftItemSerializer(gifts, many=True)
    return Response(serializer.data)


class SlotMachineListCreateView(generics.ListCreateAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    def create(self, request, *args, **kwargs):
        lucky_draw_system = request.data.get("lucky_draw_system")
        full_name = request.data.get("full_name")
        if lucky_draw_system is None:
            return Response(
                {"error": "lucky_draw_system is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            lucky_draw = LuckyDrawSystem.objects.get(id=lucky_draw_system)
        except LuckyDrawSystem.DoesNotExist:
            return Response(
                {"error": "Lucky Draw System not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        customer = Customer.objects.create(
            lucky_draw_system=lucky_draw,
            full_name=full_name,
        )

        self.assign_gift(customer)

        serializer = CustomerGiftSerializer(customer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # ---------------- GIFT ASSIGNMENT ---------------- #
    def assign_gift(self, customer):
        today_date = timezone.now().date()
        lucky_draw_system = customer.lucky_draw_system

        # Update daily sales count
        sales_today, _ = Sales.objects.get_or_create(
            date=today_date,
            lucky_draw_system=lucky_draw_system,
            defaults={"sales_count": 0},
        )
        sales_today.sales_count += 1
        sales_today.save()
        sales_count = sales_today.sales_count

        phone_number = customer.full_name

        # ------------------ FIXED OFFERS ------------------ #
        fixed_offer = FixOffer.objects.filter(
            lucky_draw_system=lucky_draw_system,
            phone_number=phone_number,
            quantity__gt=0
        ).first()

        if fixed_offer:
            customer.gift.set(fixed_offer.gift.all())
            gift_names = ", ".join(
                [gift.name for gift in fixed_offer.gift.all()])
            customer.prize_details = f"Congratulations! You've won {gift_names}"
            customer.save()
            fixed_offer.quantity -= 1
            fixed_offer.save()
            return

        # ------------------ ELECTRONIC OFFERS ------------------ #
        electronic_offers = ElectronicsShopOffer.objects.filter(
            lucky_draw_system=lucky_draw_system,
            start_date__lte=today_date,
            end_date__gte=today_date,
            daily_quantity__gt=0,
        )

        # Step 1: collect offers that match condition
        matching_offers = [
            offer for offer in electronic_offers
            if self.check_offer_condition(offer, sales_count)
        ]

        if not matching_offers:
            customer.prize_details = "Thank you for your purchase!"
            customer.save()
            return

        # Step 2: Collect all gifts from ALL matching offers with percentage-based weights
        gift_weights = {}

        for offer in matching_offers:
            for gift in offer.gift.all():
                already_assigned = Customer.objects.filter(
                    date_of_purchase=today_date,
                    gift=gift
                ).count()

                # Only include gifts that haven't exceeded their daily limit
                if already_assigned < offer.daily_quantity:
                    # Calculate weight with strong preference for less assigned gifts
                    remaining_slots = offer.daily_quantity - already_assigned

                    # Weight based on remaining slots (more remaining = higher weight)
                    # This creates a strong preference hierarchy
                    if already_assigned == 0:
                        weight = 1000  # Very high priority for unassigned gifts
                    elif already_assigned == 1:
                        weight = 100   # Medium priority for once-assigned gifts
                    elif already_assigned == 2:
                        weight = 10    # Low priority for twice-assigned gifts
                    else:
                        weight = 1     # Minimum priority for heavily assigned gifts

                    gift_weights[gift] = weight

        if not gift_weights:
            customer.prize_details = "Thank you for your purchase!"
            customer.save()
            return

        # Debug: Print current gift assignment status (remove this in production)
        for gift, weight in gift_weights.items():
            assigned_count = Customer.objects.filter(
                date_of_purchase=today_date,
                gift=gift
            ).count()
            print(f"{gift.name}: assigned {assigned_count}/3, weight {weight}")

        # Step 3: Weighted random selection based on assignment percentages
        gifts = list(gift_weights.keys())
        weights = list(gift_weights.values())
        selected_gift = random.choices(gifts, weights=weights, k=1)[0]

        customer.gift.add(selected_gift)
        customer.prize_details = f"Congratulations! You've won {selected_gift.name}"
        customer.save()

    # ---------------- OFFER CHECKING (unchanged) ---------------- #

    def check_offer_condition(self, offer, sales_count):
        today_date = timezone.now().date()
        today_time = timezone.now().time()

        if offer.has_time_limit:
            if today_time < offer.start_time or today_time > offer.end_time:
                return False

        if offer.type_of_offer == "After every certain sale":
            todays_gift_count = Customer.objects.filter(
                date_of_purchase=today_date,
                gift__in=offer.gift.all()
            ).distinct().count()

            return (
                sales_count % int(offer.offer_condition_value) == 0
                and todays_gift_count < offer.daily_quantity
            )

        elif offer.type_of_offer == "At certain sale position":
            return str(sales_count) in offer.sale_numbers

        return False

@api_view(["GET"])
def GetGiftList(request):
    lucky_draw_system_id = request.GET["lucky_draw_system_id"]
    lucky_draw_system = LuckyDrawSystem.objects.get(id=lucky_draw_system_id)
    gifts = GiftItem.objects.filter(lucky_draw_system=lucky_draw_system)
    serializer = GiftItemSerializer(gifts, many=True)
    data = serializer.data
    # data["image"] = request.build_absolute_uri(data["image"])
    for gift in data:
        gift["image"] = request.build_absolute_uri(gift["image"])
    return Response(data)

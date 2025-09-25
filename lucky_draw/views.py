import csv
import datetime
import random

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sales_fest.models import FestConfig

from .models import (
    Customer,
    FixOffer,
    GiftItem,
    LuckyDrawSystem,
    Offer,
    Sales,
)
from .serializers import (
    CustomerGiftSerializer,
    CustomerSerializer,
    FixOfferSerializer,
    GiftItemSerializer,
    LuckyDrawSystemSerializer,
    OfferSerializer,
    OfferSerializer2,
)

# Create your views here.


class LuckyDrawSystemListCreateView(generics.ListCreateAPIView):
    serializer_class = LuckyDrawSystemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LuckyDrawSystem.objects.filter(franchise=self.request.user.franchise)

    def create(self, request, *args, **kwargs):
        if self.request.user.role != "Franchise":
            return Response(
                {"error": "User must be a franchise account to create Lucky Draw."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not self.request.user.franchise:
            return Response(
                {"error": "User must be associated with a franchise."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        franchise = self.request.user.franchise
        name = request.data.get("name")
        description = request.data.get("description")
        background_image = request.data.get("background_image")
        hero_image = request.data.get("hero_image")
        main_offer_stamp_image = request.data.get("main_offer_stamp_image")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")

        lucky_draw_system = LuckyDrawSystem.objects.create(
            franchise=franchise,
            name=name,
            description=description,
            background_image=background_image,
            hero_image=hero_image,
            main_offer_stamp_image=main_offer_stamp_image,
            start_date=start_date,
            end_date=end_date,
        )

        lucky_draw_system.save()
        fest_config, created = FestConfig.objects.get_or_create(
            franchise=franchise,
        )
        if not created and not fest_config.lucky_draw_system:
            fest_config.lucky_draw_system = lucky_draw_system
            fest_config.save()
        serializer = LuckyDrawSystemSerializer(lucky_draw_system)
        return Response(serializer.data)


class LuckyDrawSystemRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = LuckyDrawSystemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LuckyDrawSystem.objects.filter(franchise=self.request.user.franchise)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        name = request.data.get("name")
        description = request.data.get("description")
        background_image = request.data.get("background_image")
        hero_image = request.data.get("hero_image")
        main_offer_stamp_image = request.data.get("main_offer_stamp_image")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")

        # Update the instance fields if provided in the request
        if name is not None:
            instance.name = name
        if description is not None:
            instance.description = description
        if background_image is not None:
            instance.background_image = background_image
        if hero_image is not None:
            instance.hero_image = hero_image
        if main_offer_stamp_image is not None:
            instance.main_offer_stamp_image = main_offer_stamp_image
        if start_date is not None:
            instance.start_date = start_date
        if end_date is not None:
            instance.end_date = end_date

        # Save the updated instance
        instance.save()

        # Serialize and return the updated instance
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Unpack get_or_create
        fest_config, created = FestConfig.objects.get_or_create(
            franchise=instance.franchise,
        )
        
        fest_config.lucky_draw_system = None
        fest_config.save()
        
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FixOfferListCreateView(generics.ListCreateAPIView):
    serializer_class = FixOfferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FixOffer.objects.filter(
            lucky_draw_system__franchise=self.request.user.franchise
        )

    def create(self, request, *args, **kwargs):
        lucky_draw_system = request.data.get("lucky_draw_system")
        phone_number = request.data.get("phone_number")
        quantity = request.data.get("quantity")
        gift = request.data.get("gift")

        fix_offer = FixOffer.objects.create(
            lucky_draw_system=lucky_draw_system,
            phone_number=phone_number,
            quantity=quantity,
        )
        if gift:
            if isinstance(gift, list):
                fix_offer.gift.set(gift)
            else:
                fix_offer.gift.add(gift)
        serializer = FixOfferSerializer(fix_offer)
        return Response(serializer.data)


class FixOfferRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FixOfferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FixOffer.objects.filter(
            lucky_draw_system__franchise=self.request.user.franchise
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        lucky_draw_system = request.data.get("lucky_draw_system")
        phone_number = request.data.get("phone_number")
        quantity = request.data.get("quantity")
        gift = request.data.get("gift")

        if lucky_draw_system is not None:
            instance.lucky_draw_system_id = lucky_draw_system
        if phone_number is not None:
            instance.phone_number = phone_number
        if quantity is not None:
            instance.quantity = quantity

        instance.save()

        if gift:
            if isinstance(gift, list):
                instance.gift.set(gift)
            else:
                instance.gift.set([gift])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OfferListCreateView(generics.ListCreateAPIView):
    serializer_class = OfferSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return OfferSerializer2
        return OfferSerializer

    def get_queryset(self):
        lucky_draw_system_id = self.request.GET["lucky_draw_system_id"]
        return Offer.objects.filter(lucky_draw_system_id=lucky_draw_system_id)

    def create(self, request, *args, **kwargs):
        lucky_draw_system_id = request.data.get("lucky_draw_system")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")
        daily_quantity = request.data.get("daily_quantity")
        type_of_offer = request.data.get("type_of_offer")
        offer_condition_value = request.data.get("offer_condition_value")
        sale_numbers = request.data.get("sale_numbers")
        gifts = request.data.get("gift", [])

        lucky_draw_system = LuckyDrawSystem.objects.get(id=lucky_draw_system_id)

        offer = Offer.objects.create(
            lucky_draw_system=lucky_draw_system,
            start_date=start_date,
            end_date=end_date,
            daily_quantity=daily_quantity,
            type_of_offer=type_of_offer,
            offer_condition_value=offer_condition_value,
            sale_numbers=sale_numbers,
        )

        offer.gift.set(gifts)

        # Handle many-to-many relationship for valid_condition
        valid_conditions = request.data.get("valid_condition", [])
        offer.valid_condition.set(valid_conditions)

        offer.save()

        serializer = self.get_serializer(offer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class OfferRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Offer.objects.all()
    serializer_class = OfferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Offer.objects.filter(
            lucky_draw_system__franchise=self.request.user.franchise
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        # Updating the instance fields with provided data or using existing values
        lucky_draw_system_id = request.data.get(
            "lucky_draw_system", instance.lucky_draw_system.id
        )
        instance.lucky_draw_system = LuckyDrawSystem.objects.get(
            id=lucky_draw_system_id
        )

        instance.start_date = request.data.get("start_date", instance.start_date)
        instance.end_date = request.data.get("end_date", instance.end_date)
        instance.daily_quantity = request.data.get(
            "daily_quantity", instance.daily_quantity
        )
        instance.type_of_offer = request.data.get(
            "type_of_offer", instance.type_of_offer
        )
        instance.offer_condition_value = request.data.get(
            "offer_condition_value", instance.offer_condition_value
        )
        instance.sale_numbers = request.data.get("sale_numbers", instance.sale_numbers)

        # Handling many-to-many relationship for valid_condition
        valid_conditions = request.data.get("valid_condition", [])
        if valid_conditions:
            instance.valid_condition.set(valid_conditions)

        instance.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"message": "Electronics shop offer deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


class GiftItemListCreateView(generics.ListCreateAPIView):
    serializer_class = GiftItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        lucky_draw_system_id = self.request.GET["lucky_draw_system_id"]
        return GiftItem.objects.filter(lucky_draw_system__id=lucky_draw_system_id)

    def create(self, request):
        lucky_draw_system_id = self.request.GET["lucky_draw_system_id"]
        name = request.data.get("name")
        image = request.data.get("image")

        gift_item = GiftItem.objects.create(
            lucky_draw_system_id=lucky_draw_system_id, name=name, image=image
        )

        gift_item.save()
        gift_item_uploaded = GiftItem.objects.get(id=gift_item.id)
        serializer = GiftItemSerializer(gift_item_uploaded)
        data = serializer.data
        data["image"] = request.build_absolute_uri(data["image"])
        return Response(data)


class GiftItemRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = GiftItem.objects.all()
    serializer_class = GiftItemSerializer
    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        # Get the data from the request
        name = request.data.get("name")
        image = request.data.get("image")
        lucky_draw_system = request.data.get("lucky_draw_system")

        # Update the instance fields if provided in the request
        if name is not None:
            instance.name = name
        if image is not None:
            instance.image = image
        if lucky_draw_system is not None:
            instance.lucky_draw_system_id = lucky_draw_system

        # Save the updated instance
        instance.save()

        # Serialize and return the updated instance
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        instance.delete()


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
    serializer_class = CustomerSerializer

    def get_serializer_class(self):
        if self.request.method == "GET":
            return CustomerGiftSerializer
        return CustomerSerializer

    def get_queryset(self):
        lucky_draw_system_id = self.request.GET.get("lucky_draw_system_id")
        customer = Customer.objects.filter(
            lucky_draw_system__id=lucky_draw_system_id,
        )
        return customer

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
            quantity__gt=0,
        ).first()

        if fixed_offer:
            customer.gift.set(fixed_offer.gift.all())
            gift_names = ", ".join([gift.name for gift in fixed_offer.gift.all()])
            customer.prize_details = f"Congratulations! You've won {gift_names}"
            customer.save()
            fixed_offer.quantity -= 1
            fixed_offer.save()
            return

        # ------------------ ELECTRONIC OFFERS ------------------ #
        offers = Offer.objects.filter(
            lucky_draw_system=lucky_draw_system,
            start_date__lte=today_date,
            end_date__gte=today_date,
            daily_quantity__gt=0,
        )

        # Step 1: collect offers that match condition
        matching_offers = [
            offer for offer in offers if self.check_offer_condition(offer, sales_count)
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
                    date_of_purchase=today_date, gift=gift
                ).count()

                # Only include gifts that haven't exceeded their daily limit
                if already_assigned < offer.daily_quantity:
                    # Calculate weight with strong preference for less assigned gifts

                    # Weight based on remaining slots (more remaining = higher weight)
                    # This creates a strong preference hierarchy
                    if already_assigned == 0:
                        weight = 1000  # Very high priority for unassigned gifts
                    elif already_assigned == 1:
                        weight = 100  # Medium priority for once-assigned gifts
                    elif already_assigned == 2:
                        weight = 10  # Low priority for twice-assigned gifts
                    else:
                        weight = 1  # Minimum priority for heavily assigned gifts

                    gift_weights[gift] = weight

        if not gift_weights:
            customer.prize_details = "Thank you for your purchase!"
            customer.save()
            return

        # Debug: Print current gift assignment status (remove this in production)
        for gift, weight in gift_weights.items():
            assigned_count = Customer.objects.filter(
                date_of_purchase=today_date, gift=gift
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
            todays_gift_count = (
                Customer.objects.filter(
                    date_of_purchase=today_date, gift__in=offer.gift.all()
                )
                .distinct()
                .count()
            )

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


@api_view(["POST"])
def download_customers_detail(request):
    if request.method == "POST":
        data = request.data
        start_date = data.get("start_date", datetime.date.today())
        end_date = data.get("end_date", datetime.date.today())
        luckydraw = data.get("lucky_draw_system_id", None)

        # Create a base queryset for customers with gifts
        queryset = Customer.objects.all()

        if luckydraw is not None:
            system = LuckyDrawSystem.objects.get(id=luckydraw)
            queryset = queryset.filter(lucky_draw_system=system)

        if start_date and end_date:
            queryset = queryset.filter(date_of_purchase__range=(start_date, end_date))

        if start_date and not end_date:
            queryset = queryset.filter(date_of_purchase=start_date)

        if end_date and not start_date:
            queryset = queryset.filter(date_of_purchase=end_date)

        # Create a CSV response
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="customers_detail.csv"'

        # Create a CSV writer and write the header row
        writer = csv.writer(response)
        writer.writerow(
            [
                "Full Name",
                "Gift",
                "Date of Spin",
            ]
        )

        # Write the data rows
        for customer in queryset:
            writer.writerow(
                [
                    customer.full_name,
                    ", ".join([gift.name for gift in customer.gift.all()])
                    if customer.gift.exists()
                    else "",
                    customer.date_of_purchase,
                ]
            )

        return response

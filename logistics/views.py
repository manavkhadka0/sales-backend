# views.py
from django.db.models import Q, Sum, Case, When, IntegerField
from .models import OrderChangeLog
from rest_framework.views import APIView
from .serializers import AssignOrderSerializer
from .models import AssignOrder, Order, CustomUser, FranchisePaymentLog
from rest_framework.permissions import IsAuthenticated
from datetime import date, timedelta
from calendar import monthrange
from datetime import date
from django.utils import timezone
from django.db.models import Sum, Count
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from sales.models import Order
# You'll need to create this serializer
from sales.serializers import OrderSerializer
from .serializers import OrderChangeLogSerializer, OrderCommentSerializer, OrderCommentDetailSerializer, OrderCommentDetailSerializer, FranchisePaymentLogSerializer
from rest_framework import generics
from .models import OrderComment, AssignOrder
from account.models import CustomUser, Franchise
from account.serializers import SmallUserSerializer
from rest_framework.filters import SearchFilter

DELIVERY_CHARGE = 100
CANCELLED_CHARGE = 0


class GetYDMRiderView(generics.ListAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = SmallUserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter]
    search_fields = ['first_name', 'phone_number', 'address']

    def get_queryset(self):
        return CustomUser.objects.filter(role='YDM_Rider')


class OrderCommentListCreateView(generics.ListCreateAPIView):
    queryset = OrderComment.objects.all()
    serializer_class = OrderCommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class OrderCommentRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = OrderComment.objects.all()
    serializer_class = OrderCommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


@api_view(['GET'])
@permission_classes([AllowAny])
def track_order(request):
    order_code = request.query_params.get('order_code')
    order = get_object_or_404(Order, order_code=order_code)
    serializer = OrderSerializer(order)
    order_change_log = OrderChangeLogSerializer(
        order.change_logs.all(), many=True)
    order_comment = OrderCommentDetailSerializer(
        order.comments.all(), many=True)

    return Response({
        'order': serializer.data,
        'order_change_log': order_change_log.data,
        'order_comment': order_comment.data
    })


@api_view(['GET'])
def get_franchise_order_stats(request, franchise_id):
    """
    Get order statistics for a franchise where logistics is YDM
    """
    try:
        # Base queryset
        orders = Order.objects.filter(
            franchise_id=franchise_id,
            logistics='YDM'
        ).exclude(order_status__in=['Pending', 'Processing', 'Sent to Dash', 'Indrive', 'Return By Dash'])

        # Helper function to get stats
        def get_status_stats(statuses):
            if isinstance(statuses, str):
                statuses = [statuses]
            filtered = orders.filter(order_status__in=statuses)
            result = filtered.aggregate(
                count=Count('id'),
                total=Sum('total_amount'),
                prepaid=Sum('prepaid_amount')
            )
            total = float(result['total'] or 0)
            prepaid = float(result['prepaid'] or 0)
            return {
                'nos': result['count'] or 0,
                'amount': total - prepaid
            }

        # Calculate statistics
        data = {
            'Total Orders': get_status_stats(['Sent to YDM', 'Verified', 'Out For Delivery', 'Rescheduled', 'Delivered', 'Cancelled', 'Returned By Customer', 'Returned By YDM', 'Return Pending']),
            'order_processing': {
                'Order Placed': get_status_stats('Sent to YDM'),
                'Order Verified': get_status_stats('Verified'),
            },
            'order_dispatched': {
                'Out For Delivery': get_status_stats('Out For Delivery'),
                'Rescheduled': get_status_stats('Rescheduled'),
            },
            'order_status': {
                'Delivered': get_status_stats('Delivered'),
                'Cancelled': get_status_stats('Returned By YDM'),
                'Pending RTV': get_status_stats('Return Pending'),
            }
        }

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_complete_dashboard_stats(request, franchise_id):
    """
    Get all dashboard statistics in a single function
    """
    try:
        today = timezone.now().date()
        exclude_status = ['Pending', 'Processing',
                          'Sent to Dash', 'Indrive', 'Return By Dash']

        # Base queryset - filter by user's organization
        orders = Order.objects.filter(franchise_id=franchise_id, logistics='YDM').exclude(
            order_status__in=exclude_status)
        user = request.user

        # Helper function to get stats
        def get_status_stats(statuses):
            if isinstance(statuses, str):
                statuses = [statuses]
            filtered = orders.filter(
                logistics='YDM', order_status__in=statuses)
            result = filtered.aggregate(
                count=Count('id'),
                total=Sum('total_amount'),
                prepaid=Sum('prepaid_amount')
            )
            total = float(result['total'] or 0)
            prepaid = float(result['prepaid'] or 0)
            return {
                'nos': result['count'] or 0,
                'amount': total - prepaid
            }

        valid_orders = Order.objects.filter(logistics='YDM').exclude(
            order_status__in=['Cancelled', 'Return Pending']).count()

        cancelled_orders = Order.objects.filter(logistics='YDM', order_status__in=[
                                                'Cancelled', 'Return Pending']).count()

        # Calculate total charges
        valid_charge = valid_orders * DELIVERY_CHARGE
        cancelled_charge = cancelled_orders * CANCELLED_CHARGE
        total_charge = valid_charge + cancelled_charge

        # Calculate delivery performance percentages
        completed_orders = orders.filter(
            order_status__in=['Delivered', 'Returned By YDM']).count()
        delivered_count = orders.filter(order_status='Delivered').count()
        cancelled_count = orders.filter(
            order_status='Returned By YDM').count()

        delivered_percentage = round(
            (delivered_count / completed_orders) * 100, 2) if completed_orders > 0 else 0
        cancelled_percentage = round(
            (cancelled_count / completed_orders) * 100, 2) if completed_orders > 0 else 0

        def get_todays_orders_by_status(status):
            """
            Helper function to get count of orders with specific status(es) change today

            Args:
                status: A single status string or a list/tuple of status strings

            Returns:
                int: Count of orders matching the status criteria
            """
            qs = OrderChangeLog.objects.filter(
                changed_at__date=today,
                order__franchise_id=franchise_id,
                order__logistics='YDM'
            )

            if isinstance(status, (list, tuple)):
                qs = qs.filter(new_status__in=status)
            else:
                qs = qs.filter(new_status=status)

            return qs.count()

        # Get today's order counts by status
        todays_orders_count = get_todays_orders_by_status('Sent to YDM')
        todays_deliveries_count = get_todays_orders_by_status('Delivered')
        todays_rescheduled_count = get_todays_orders_by_status('Rescheduled')
        todays_cancellations_count = get_todays_orders_by_status(
            'Returned By YDM')

        # Complete dashboard data
        data = {
            'overall_statistics': {
                'Total Orders': get_status_stats(['Sent to YDM', 'Verified', 'Out For Delivery', 'Rescheduled', 'Delivered', 'Cancelled', 'Returned By Customer', 'Returned By YDM', 'Return Pending']),
                'Total COD': get_status_stats(['Sent to YDM', 'Verified', 'Out For Delivery', 'Rescheduled', 'Delivered']),
                'Total Delivered': get_status_stats('Delivered'),
                'Total RTV': get_status_stats('Return Pending'),
                'Total Cancelled': get_status_stats(['Cancelled', 'Returned By Customer', 'Returned By YDM']),
                'Total Delivery Charge': {
                    'nos': orders.count(),
                    'amount': total_charge
                },
                'Total Pending COD': get_status_stats(['Sent to YDM', 'Verified', 'Out For Delivery', 'Rescheduled', 'Delivered']),
            },

            'todays_statistics': {
                'Todays Orders': todays_orders_count,
                'Todays Delivery': todays_deliveries_count,
                'Todays Rescheduled': todays_rescheduled_count,
                'Todays Cancellation': todays_cancellations_count,
            },

            'delivery_performance': {
                'Delivered Percentage': delivered_percentage,
                'Cancelled Percentage': cancelled_percentage
            },
        }

        return Response({
            'success': True,
            'data': data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daily_orders_by_franchise(request, franchise_id):
    """
    Return daily order counts for the given franchise_id
    based on when orders were marked as 'Sent to YDM' status
    in the current month only (no missing days filled).
    """
    from django.db.models.functions import TruncDate

    today = date.today()
    year, month = today.year, today.month

    # Get all orders that were marked as 'Sent to YDM' for this franchise in current month
    qs = (
        OrderChangeLog.objects
        .filter(
            order__franchise_id=franchise_id,
            order__logistics='YDM',
            new_status='Sent to YDM',
            changed_at__year=year,
            changed_at__month=month
        )
        .annotate(change_date=TruncDate('changed_at'))
        .values('change_date')
        .annotate(count=Count('id'))
        .order_by('change_date')
    )

    # Format the results to match the previous response structure
    formatted_days = [
        {'date': item['change_date'], 'count': item['count']}
        for item in qs
    ]

    return Response({
        "franchise_id": franchise_id,
        "days": formatted_days,
    })


class AssignOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.data.get("user_id")
        order_ids = request.data.get("order_ids")

        if not user_id or not order_ids:
            return Response(
                {"detail": "user_id and order_ids are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # validate user (must be rider)
        try:
            user = CustomUser.objects.get(id=user_id, role="YDM_Rider")
        except CustomUser.DoesNotExist:
            return Response(
                {"detail": "User not found or is not a YDM Rider"},
                status=status.HTTP_404_NOT_FOUND
            )

        # validate orders
        orders = Order.objects.filter(
            id__in=order_ids).prefetch_related("assign_orders__user")
        if orders.count() != len(order_ids):
            return Response(
                {"detail": "One or more orders not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        assignments = []

        for order in orders:
            existing_assignment = order.assign_orders.first()
            if existing_assignment:
                continue
            else:
                assignment = AssignOrder.objects.create(order=order, user=user)
                # Update order status to 'Out For Delivery' when assigned to rider
                if order.order_status != 'Out For Delivery':
                    order.order_status = 'Out For Delivery'
                    order.save()
                assignments.append(assignment)

        return Response({
            "assigned": AssignOrderSerializer(assignments, many=True).data,
        }, status=status.HTTP_201_CREATED)

    def patch(self, request):
        user_id = request.data.get("user_id")
        order_ids = request.data.get("order_ids")

        if not user_id or not order_ids:
            return Response(
                {"detail": "user_id and order_ids are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # validate user (must be rider)
        try:
            user = CustomUser.objects.get(id=user_id, role="YDM_Rider")
        except CustomUser.DoesNotExist:
            return Response(
                {"detail": "User not found or is not a YDM Rider"},
                status=status.HTTP_404_NOT_FOUND
            )

        # validate orders
        orders = Order.objects.filter(
            id__in=order_ids).prefetch_related("assign_orders__user")
        if orders.count() != len(order_ids):
            return Response(
                {"detail": "One or more orders not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        updated = []

        for order in orders:
            # Update or create assignment for each order
            assign_order, created = AssignOrder.objects.update_or_create(
                order=order,
                defaults={'user': user}
            )

            # Update order status to 'Out For Delivery' when assigned to rider
            if order.order_status != 'Out For Delivery':
                order.order_status = 'Out For Delivery'
                order.save()

            if created:
                updated.append({
                    "order_code": order.order_code,
                    "status": "assigned",
                    "assigned_to": user.first_name or user.username,
                    "order_status": "Out For Delivery"
                })
            else:
                updated.append({
                    "order_code": order.order_code,
                    "status": "reassigned",
                    "assigned_to": user.first_name or user.username,
                    "order_status": "Out For Delivery"
                })

        return Response({
            "updated": updated,
        }, status=status.HTTP_200_OK)


class UpdateOrderStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_ids = request.data.get("order_ids")
        status_value = request.data.get("status")

        if not order_ids or not status_value:
            return Response(
                {"detail": "order_ids and status are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate status value (add more statuses as per your Order model)
        valid_statuses = ['Verified', 'Sent to YDM', 'Delivered', 'Cancelled', 'Rescheduled',
                          'Out For Delivery', 'Returned By Customer', 'Return Pending']
        if status_value not in valid_statuses:
            return Response(
                {"detail": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate orders exist
        orders = Order.objects.filter(id__in=order_ids)
        if orders.count() != len(order_ids):
            return Response(
                {"detail": "One or more orders not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        updated_orders = []
        for order in orders:
            if order.order_status != status_value:
                order.order_status = status_value
                order.save()
                updated_orders.append({
                    "order_id": order.id,
                    "order_code": order.order_code,
                    "previous_status": order.order_status,
                    "new_status": status_value,
                    "updated_at": order.updated_at
                })

        return Response({
            "message": f"Successfully updated status for {len(updated_orders)} orders",
            "updated_orders": updated_orders
        }, status=status.HTTP_200_OK)


class FranchisePaymentDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, franchise_id):
        """API endpoint showing payment details for a specific franchise"""

        # Get franchise
        franchise = get_object_or_404(Franchise, id=franchise_id)

        # Orders
        orders = Order.objects.filter(franchise=franchise, logistics="YDM")

        total_order_amount = (
            orders.aggregate(total=Sum("total_amount"))[
                "total"] or Decimal("0")
        )

        total_orders = orders.count()
        total_deduction = Decimal("100") * total_orders
        gross_amount = total_order_amount - total_deduction

        # Payments
        total_paid = (
            FranchisePaymentLog.objects.filter(franchise=franchise).aggregate(
                total=Sum("amount_paid")
            )["total"]
            or Decimal("0")
        )

        pending_amount = gross_amount - total_paid

        return Response(
            {
                "total_orders": total_orders,
                "total_order_amount": str(total_order_amount),
                "total_deduction": str(total_deduction),
                "gross_amount": str(gross_amount),
                "total_paid": str(total_paid),
                "pending_amount": str(pending_amount),
            }
        )


class FranchisePaymentLogAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, franchise_id):
        """API endpoint showing payment details for a specific franchise"""

        # Get franchise
        franchise = get_object_or_404(Franchise, id=franchise_id)

        # Payments
        payments = FranchisePaymentLog.objects.filter(franchise=franchise)

        return Response(FranchisePaymentLogSerializer(payments, many=True).data)

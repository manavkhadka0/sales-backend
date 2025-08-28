# views.py
from rest_framework.views import APIView
from .serializers import AssignOrderSerializer
from .models import AssignOrder, Order, CustomUser
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
from .serializers import OrderChangeLogSerializer, OrderCommentSerializer, OrderCommentDetailSerializer, OrderCommentDetailSerializer
from rest_framework import generics
from .models import OrderComment
from account.models import CustomUser
from account.serializers import SmallUserSerializer
from rest_framework.filters import SearchFilter


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
        )

        # Helper function to get stats
        def get_status_stats(statuses):
            if isinstance(statuses, str):
                statuses = [statuses]
            filtered = orders.filter(order_status__in=statuses)
            result = filtered.aggregate(
                count=Count('id'),
                total=Sum('total_amount')
            )
            return {
                'nos': result['count'] or 0,
                'amount': float(result['total'] or 0)
            }

        # Calculate statistics
        data = {
            'order_processing': {
                'Order Placed': get_status_stats('Pending'),
                # Map to appropriate status
                'Order Picked': get_status_stats([]),
                # Map to appropriate status
                'Order Verified': get_status_stats([]),
                'Order Processing': get_status_stats('Processing'),
            },
            'order_dispatched': {
                # Map to appropriate status
                'Received At Branch': get_status_stats([]),
                # Map to appropriate status (excluding Sent to Dash)
                'Out For Delivery': get_status_stats('Out For Delivery'),
                'Rescheduled': get_status_stats('Rescheduled'),
            },
            'order_status': {
                'Delivered': get_status_stats('Delivered'),
                'Cancelled': get_status_stats('Cancelled'),
                'Pending RTV': get_status_stats(['Returned By Customer', 'Returned By Dash']),
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
        exclude_status = ['Sent to Dash',]

        # Base queryset - filter by user's organization
        orders = Order.objects.filter(franchise_id=franchise_id).exclude(
            order_status__in=exclude_status)
        user = request.user

        # Helper function to get stats
        def get_status_stats(statuses):
            if isinstance(statuses, str):
                statuses = [statuses]
            filtered = orders.filter(order_status__in=statuses)
            result = filtered.aggregate(
                count=Count('id'),
                total=Sum('total_amount')
            )
            return {
                'nos': result['count'] or 0,
                'amount': float(result['total'] or 0)
            }

        # Helper function for payment stats
        def get_payment_stats(payment_method, statuses=None):
            filtered = orders.filter(payment_method=payment_method)
            if statuses:
                if isinstance(statuses, str):
                    statuses = [statuses]
                filtered = filtered.filter(order_status__in=statuses)
            result = filtered.aggregate(
                count=Count('id'),
                total=Sum('total_amount')
            )
            return {
                'nos': result['count'] or 0,
                'amount': float(result['total'] or 0)
            }

        # Helper function for logistics stats
        def get_logistics_stats(logistics_type, statuses=None):
            filtered = orders.filter(logistics=logistics_type)
            if statuses:
                if isinstance(statuses, str):
                    statuses = [statuses]
                filtered = filtered.filter(order_status__in=statuses)
            result = filtered.aggregate(
                count=Count('id'),
                total=Sum('total_amount')
            )
            return {
                'nos': result['count'] or 0,
                'amount': float(result['total'] or 0)
            }

        # Calculate delivery performance percentages
        completed_orders = orders.filter(
            order_status__in=['Delivered', 'Cancelled']).count()
        delivered_count = orders.filter(order_status='Delivered').count()
        cancelled_count = orders.filter(order_status='Cancelled').count()

        delivered_percentage = round(
            (delivered_count / completed_orders) * 100, 2) if completed_orders > 0 else 0
        cancelled_percentage = round(
            (cancelled_count / completed_orders) * 100, 2) if completed_orders > 0 else 0

        # Today's orders queryset
        todays_orders = orders.filter(date=today)

        # Complete dashboard data
        data = {
            'overall_statistics': {
                'Total Orders': get_status_stats(['Pending', 'Processing', 'Delivered', 'Cancelled', 'Rescheduled', 'Out For Delivery', 'Returned By Customer', 'Returned By Dash']),
                'Total COD': get_payment_stats('Cash on Delivery'),
                'Total RTV': get_status_stats(['Returned By Customer', 'Returned By Dash', 'Return Pending']),
                'Total Delivery Charge': {
                    'nos': orders.count(),
                    'amount': float(orders.aggregate(total=Sum('delivery_charge'))['total'] or 0)
                },
                'Total Pending COD': get_payment_stats('Cash on Delivery', ['Pending', 'Processing', 'Out For Delivery', 'Rescheduled']),
            },

            'todays_statistics': {
                'Todays Orders': todays_orders.count(),
                'Todays Delivery': todays_orders.filter(order_status='Delivered').count(),
                'Todays Rescheduled': todays_orders.filter(order_status='Rescheduled').count(),
                'Todays Cancellation': todays_orders.filter(order_status='Cancelled').count(),
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
    in the current month only (no missing days filled).
    """
    today = date.today()
    year, month = today.year, today.month

    qs = (
        Order.objects
        .filter(franchise_id=franchise_id, logistics='YDM', date__year=year, date__month=month)
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )

    return Response({
        "franchise_id": franchise_id,
        "days": list(qs),
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
        skipped = []

        for order in orders:
            existing_assignment = order.assign_orders.first()
            if existing_assignment:
                rider_name = existing_assignment.user.first_name or existing_assignment.user.username
                skipped.append({
                    "order_code": order.order_code,
                    "assigned_to": rider_name,
                })
            else:
                assignment = AssignOrder.objects.create(order=order, user=user)
                assignments.append(assignment)

        return Response({
            "assigned": AssignOrderSerializer(assignments, many=True).data,
            "skipped": skipped,
        }, status=status.HTTP_201_CREATED)

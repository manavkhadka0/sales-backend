
# views.py
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
from .serializers import OrderChangeLogSerializer, OrderCommentSerializer
from rest_framework import generics
from .models import OrderComment


class OrderCommentListCreateView(generics.ListCreateAPIView):
    queryset = OrderComment.objects.all()
    serializer_class = OrderCommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


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
    order_comment = OrderCommentSerializer(
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

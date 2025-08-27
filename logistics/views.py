
# views.py
from rest_framework.decorators import api_view
from django.db.models import Sum, Count
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
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

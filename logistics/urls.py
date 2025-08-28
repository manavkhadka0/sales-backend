from django.urls import path

from .views import track_order, get_franchise_order_stats, OrderCommentListCreateView, OrderCommentRetrieveUpdateDestroyView, get_complete_dashboard_stats, daily_orders_by_franchise

urlpatterns = [
    path('track-order/', track_order, name='track-order'),
    path('logistics/franchise/<int:franchise_id>/order-stats/',
         get_franchise_order_stats, name='franchise_stats_function'),
    path('logistics/order-comment/', OrderCommentListCreateView.as_view(),
         name='order-comment-list-create'),
    path('logistics/order-comment/<int:pk>/',
         OrderCommentRetrieveUpdateDestroyView.as_view(), name='order-comment-detail'),
    path('logistics/franchise/<int:franchise_id>/dashboard-stats/',
         get_complete_dashboard_stats, name='complete_dashboard_stats'),
    path('logistics/franchise/<int:franchise_id>/daily-stats/',
         daily_orders_by_franchise, name='daily_stats_by_franchise'),
]

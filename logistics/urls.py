from django.urls import path

from .views import track_order, get_franchise_order_stats, OrderCommentListCreateView, OrderCommentRetrieveUpdateDestroyView, get_complete_dashboard_stats, daily_orders_by_franchise, AssignOrderView, GetYDMRiderView, FranchisePaymentDashboardAPIView, FranchisePaymentLogAPIView, UpdateOrderStatusView, UpdateOrderStatusView, calculate_delivery_charges

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
    path('logistics/assign-order/', AssignOrderView.as_view(), name='assign-order'),
    path('logistics/ydm-riders/', GetYDMRiderView.as_view(), name='ydm-rider'),
    path('logistics/franchise/<int:franchise_id>/payment-dashboard/',
         FranchisePaymentDashboardAPIView.as_view(), name='franchise_payment_dashboard'),
    path('logistics/franchise/<int:franchise_id>/payment-log/',
         FranchisePaymentLogAPIView.as_view(), name='franchise_payment_log'),
    path('logistics/update-order-status/', UpdateOrderStatusView.as_view(), name='update-order-status'),
    path('delivery-charges/', calculate_delivery_charges, name='delivery-charges'),

]

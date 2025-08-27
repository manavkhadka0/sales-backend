from django.urls import path

from .views import track_order, get_franchise_order_stats, OrderCommentListCreateView, OrderCommentRetrieveUpdateDestroyView

urlpatterns = [
    path('track-order/', track_order, name='track-order'),
    path('logistics/franchise/<int:franchise_id>',
         get_franchise_order_stats, name='franchise_stats_function'),
    path('logistics/order-comment/', OrderCommentListCreateView.as_view(),
         name='order-comment-list-create'),
    path('logistics/order-comment/<int:pk>/',
         OrderCommentRetrieveUpdateDestroyView.as_view(), name='order-comment-detail'),

]

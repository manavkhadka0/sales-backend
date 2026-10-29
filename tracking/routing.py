"""
WebSocket URL routing for tracking app.
Used only when running Daphne/ASGI with channels.
"""

from django.urls import path

from tracking.consumers import SalesPersonLocationConsumer

websocket_urlpatterns = [
    path("ws/tracking/salesperson/", SalesPersonLocationConsumer.as_asgi() if hasattr(SalesPersonLocationConsumer, "as_asgi") else None),
]
# Filter out None routes in WSGI
websocket_urlpatterns = [p for p in websocket_urlpatterns if p is not None]

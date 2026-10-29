"""
WebSocket consumers for real-time tracking if Daphne/Channels is configured.
Gracefully disabled in standard WSGI/Gunicorn environments.
"""

try:
    from channels.generic.websocket import AsyncJsonWebsocketConsumer
    HAS_CHANNELS = True
except ImportError:
    AsyncJsonWebsocketConsumer = object
    HAS_CHANNELS = False


class SalesPersonLocationConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer stub for real-time location streaming.
    Active only when Django Channels is installed and running via ASGI.
    """

    async def connect(self):
        if not HAS_CHANNELS:
            return
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive_json(self, content, **kwargs):
        pass

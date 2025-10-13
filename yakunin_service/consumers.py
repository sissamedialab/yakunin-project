import json

from channels.generic.websocket import AsyncWebsocketConsumer


class EchoConsumer(AsyncWebsocketConsumer):
    """Echoes back any message it receives."""

    async def connect(self):
        """Accept connection."""
        await self.accept()

    async def disconnect(self, close_code):
        """Disconnect."""

    async def receive(self, text_data=None, bytes_data=None):
        """
        Receive message and echo it back.

        Args:
            text_data: text data received
            bytes_data: bytes data received

        """
        if text_data:
            await self.send(text_data=text_data)
        if bytes_data:
            await self.send(bytes_data=bytes_data)


class FeedbackConsumer(AsyncWebsocketConsumer):
    """Forwards messages to the client."""

    async def connect(self):
        """Accept connection and join group."""
        self.feedback_wsname = self.scope["url_route"]["kwargs"]["feedback_wsname"]
        self.feedback_group_name = f"feedback_{self.feedback_wsname}"

        # Join room group
        await self.channel_layer.group_add(
            self.feedback_group_name,
            self.channel_name,
        )
        await self.accept()

    async def disconnect(self, close_code):
        """Disconnect and leave group."""
        # Leave room group
        await self.channel_layer.group_discard(
            self.feedback_group_name,
            self.channel_name,
        )

    async def feedback_message(self, event):
        """
        Receive message from group and send to client.

        Args:
            event: event from channel layer

        """
        message = event["message"]

        # Send message to WebSocket
        await self.send(text_data=json.dumps({"message": message}))

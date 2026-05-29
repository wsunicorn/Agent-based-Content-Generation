"""Django Channels consumer for real-time job progress."""
import json
import logging

from django.conf import settings
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class JobProgressConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer that pushes job progress updates to the browser.

    Clients connect to: ws/jobs/<job_id>/
    Messages sent by the server:
      {"type": "progress", "agent": "research", "status": "running"}
      {"type": "completed", "qa_score": 82.5}
      {"type": "error", "message": "..."}
    """

    async def connect(self):
        user = self.scope.get("user")
        if not settings.DEBUG and (not user or not user.is_authenticated):
            await self.close(code=4401)
            return

        self.job_id = self.scope["url_route"]["kwargs"]["job_id"]
        self.group_name = f"job_{self.job_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug("WS connected: job=%s", self.job_id)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Clients don't send data in this use case — no-op
        pass

    # ------------------------------------------------------------------ #
    # Handlers for messages sent to the channel group
    # ------------------------------------------------------------------ #

    async def job_progress(self, event):
        payload = {
            "type": "progress",
            "agent": event.get("agent"),
            "status": event.get("status"),
        }
        if event.get("detail") is not None:
            payload["detail"] = event.get("detail")
        await self.send(text_data=json.dumps(payload))

    async def job_completed(self, event):
        await self.send(text_data=json.dumps({
            "type": "completed",
            "qa_score": event.get("qa_score"),
        }))

    async def job_error(self, event):
        await self.send(text_data=json.dumps({
            "type": "error",
            "message": event.get("message"),
        }))

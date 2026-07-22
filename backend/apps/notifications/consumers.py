import json
from channels.generic.websocket import AsyncWebsocketConsumer
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self): await self.channel_layer.group_add("notifications",self.channel_name); await self.accept()
    async def disconnect(self,code): await self.channel_layer.group_discard("notifications",self.channel_name)
    async def event(self,event): await self.send(text_data=json.dumps(event.get("payload",{})))

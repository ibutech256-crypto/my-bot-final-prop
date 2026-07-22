import json
from channels.generic.websocket import AsyncWebsocketConsumer
class SystemHealthConsumer(AsyncWebsocketConsumer):
    async def connect(self): await self.channel_layer.group_add("system_health",self.channel_name); await self.accept()
    async def disconnect(self,code): await self.channel_layer.group_discard("system_health",self.channel_name)
    async def event(self,event): await self.send(text_data=json.dumps(event.get("payload",{})))

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Message
from .logger import logger

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        sender_id = self.scope['user_id']
        receiver_id = text_data_json['receiver_id']

        msg = Message.objects.create(
            sender_id=sender_id,
            receiver_id=receiver_id,
            tenant_id=self.scope['tenant_id'],
            content=message
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender_id': str(sender_id),
                'sent_at': msg.sent_at.isoformat()
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sent_at': event['sent_at']
        }))
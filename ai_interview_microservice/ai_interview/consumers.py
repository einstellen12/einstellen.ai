import json
from channels.generic.websocket import AsyncWebsocketConsumer
from aiortc import RTCPeerConnection, RTCSessionDescription
import asyncio
from .ai_engine import transcribe_audio, generate_follow_up_question, score_response
from .models import Transcript, QuestionAnswer

pcs = set()

class InterviewConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.interview_id = self.scope['url_route']['kwargs']['interview_id']
        self.room_group_name = f'interview_{self.interview_id}'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        for pc in pcs:
            await pc.close()
        pcs.clear()

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'offer':
            pc = RTCPeerConnection()
            pcs.add(pc)
            await pc.setRemoteDescription(RTCSessionDescription(sdp=data['sdp'], type=data['type']))
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            await self.send(json.dumps({
                'type': 'answer',
                'sdp': pc.localDescription.sdp
            }))
        elif message_type == 'code_update':
            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'broadcast_code', 'code': data['code']}
            )
        elif message_type == 'audio_chunk':
            audio_path = f"/tmp/{self.interview_id}_audio.wav"
            with open(audio_path, 'wb') as f:
                f.write(data['audio'].encode())
            transcript = transcribe_audio(audio_path)
            Transcript.objects.create(interview_id=self.interview_id, text=transcript)
            follow_up = generate_follow_up_question(transcript)
            QuestionAnswer.objects.create(interview_id=self.interview_id, question=follow_up)
            await self.send(json.dumps({
                'type': 'follow_up_question',
                'question': follow_up,
                'transcript': transcript
            }))
        elif message_type == 'submit_answer':
            qa = QuestionAnswer.objects.filter(interview_id=self.interview_id, answer__isnull=True).last()
            if qa:
                qa.answer = data.get('answer', '')
                qa.code = data.get('code', '')
                qa.is_deviated = data.get('is_deviated', False)
                score, feedback = score_response(qa.question, qa.answer, qa.code)
                qa.score = score
                qa.save()
                await self.send(json.dumps({
                    'type': 'answer_scored',
                    'score': score,
                    'feedback': feedback
                }))

    async def broadcast_code(self, event):
        await self.send(json.dumps({
            'type': 'code_update',
            'code': event['code']
        }))
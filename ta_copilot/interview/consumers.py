# interview/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
from transformers import pipeline
from .models import Transcript, Question, Report, Interview
from .services.code_eval import evaluate_code
import logging
import os
import requests
from django.conf import settings

logger = logging.getLogger('interview')

# Defer whisper loading until needed
whisper_model = None

MODEL_DIR = os.path.join(os.path.dirname(__file__), '../../models/tinyllama')
if not os.path.exists(MODEL_DIR):
    logger.info("Downloading TinyLlama model...")
    tinyllama = pipeline('text-generation', model='TinyLlama/TinyLlama-1.1B-Chat-v1.0', device=0, local_files_only=False)
    tinyllama.model.save_pretrained(MODEL_DIR)
    tinyllama.tokenizer.save_pretrained(MODEL_DIR)
else:
    logger.info("Using local TinyLlama model...")
    tinyllama = pipeline('text-generation', model=MODEL_DIR, device=0, local_files_only=True)

async def verify_token_async(token):
    """Async wrapper for token verification."""
    try:
        auth_service_url = f"{settings.AUTH_SERVICE_URL}/verify-token/"
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.post(auth_service_url, headers=headers, timeout=5)
        response.raise_for_status()
        return response.json().get('auth_info', {})
    except requests.RequestException as e:
        logger.error(f"Token verification failed: {e}")
        return None

class InterviewConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.interview_id = self.scope['url_route']['kwargs']['interview_id']
        self.group_name = f'interview_{self.interview_id}'

        # Extract token from query string or headers
        token = self.scope['query_string'].decode().split('token=')[-1] if 'token=' in self.scope['query_string'].decode() else ''
        if not token:
            token = dict(self.scope['headers']).get(b'authorization', b'').decode().replace('Bearer ', '')

        auth_info = await verify_token_async(token)
        if not auth_info or 'user' not in auth_info:
            logger.warning(f"Unauthorized WebSocket connection attempt for interview {self.interview_id}")
            await self.close()
            return

        self.user_id = auth_info['user']['id']

        # Check interview access
        interview = await database_sync_to_async(Interview.objects.get)(id=self.interview_id)
        provided_link = self.scope['query_string'].decode().split('link=')[-1] if 'link=' in self.scope['query_string'].decode() else ''
        if str(provided_link) != str(interview.link) and str(interview.interviewer_id) != str(self.user_id) and str(interview.candidate_id) != str(self.user_id):
            logger.warning(f"Unauthorized WebSocket connection for interview {self.interview_id} by user {self.user_id}")
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"WebSocket connected for interview {self.interview_id} by user {self.user_id}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"WebSocket disconnected for interview {self.interview_id}")

    async def receive(self, text_data=None, bytes_data=None):
        global whisper_model
        if whisper_model is None:
            try:
                import whisper
                whisper_model = whisper.load_model('base', device='cuda')
            except Exception as e:
                logger.error(f"Failed to load whisper model: {e}")
                await self.send(text_data=json.dumps({'error': 'Whisper model unavailable'}))
                return

        interview = await database_sync_to_async(Interview.objects.get)(id=self.interview_id)

        if bytes_data:
            try:
                transcript = whisper_model.transcribe(bytes_data, fp16=True)['text']
                speaker_type = 'candidate' if str(self.user_id) != str(interview.interviewer_id) else 'interviewer'
                await database_sync_to_async(Transcript.objects.create)(
                    interview_id=self.interview_id, speaker_type=speaker_type, content=transcript
                )
                await self.channel_layer.group_send(
                    self.group_name, {'type': 'transcript_update', 'transcript': transcript}
                )

                prompt = f"Based on this transcript: '{transcript}', generate a technical interview question."
                question = tinyllama(prompt, max_length=50, num_return_sequences=1)[0]['generated_text']
                q = await database_sync_to_async(Question.objects.create)(interview_id=self.interview_id, content=question)
                await self.channel_layer.group_send(
                    self.group_name, {'type': 'question_update', 'question': question, 'question_id': q.id}
                )
                logger.info(f"Real-time transcript: {transcript}, question: {question}")
            except Exception as e:
                logger.error(f"Transcription failed: {e}")
                await self.send(text_data=json.dumps({'error': 'Transcription failed'}))
        elif text_data:
            data = json.loads(text_data)
            if 'code' in data:
                evaluation = evaluate_code(data['code'])
                await database_sync_to_async(Report.objects.update_or_create)(
                    interview_id=self.interview_id, candidate_id=interview.candidate_id,
                    defaults={'ai_evaluation': evaluation}
                )
                await self.send(text_data=json.dumps({'evaluation': evaluation}))
                logger.info(f"Code evaluated for interview {self.interview_id}: {evaluation}")

    async def transcript_update(self, event):
        await self.send(text_data=json.dumps({'transcript': event['transcript']}))

    async def question_update(self, event):
        await self.send(text_data=json.dumps({'question': event['question'], 'question_id': event['question_id']}))
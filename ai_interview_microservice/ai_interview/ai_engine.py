import os
import requests
from transformers import AutoModelForCausalLM, AutoTokenizer, AutoModelForSequenceClassification
import torch
from faster_whisper import WhisperModel
from django.conf import settings
from .logger import logger

AZURE_QUESTION_ENDPOINT = settings.AZURE_QUESTION_ENDPOINT
AZURE_SCORING_ENDPOINT = settings.AZURE_SCORING_ENDPOINT
AZURE_API_KEY = settings.AZURE_API_KEY
RESUME_SERVICE_URL = settings.RESUME_SERVICE_URL
JOB_SERVICE_URL = settings.JOB_SERVICE_URL

LOCAL_MODEL_DIR = settings.LOCAL_MODEL_DIR
QUESTION_MODEL_PATH = os.path.join(LOCAL_MODEL_DIR, 'question_model')
SCORING_MODEL_PATH = os.path.join(LOCAL_MODEL_DIR, 'scoring_model')
DEFAULT_QUESTION_MODEL = settings.DEFAULT_QUESTION_MODEL
DEFAULT_SCORING_MODEL = settings.DEFAULT_SCORING_MODEL

try:
    whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
except Exception as e:
    logger.error(f"Failed to load Faster Whisper: {e}")
    whisper_model = None

def download_model(model_name, target_path):
    if not os.path.exists(target_path):
        os.makedirs(target_path, exist_ok=True)
        logger.info(f"Downloading {model_name} to {target_path}")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name) if "gpt" in model_name else AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=1)
        tokenizer.save_pretrained(target_path)
        model.save_pretrained(target_path)
    else:
        logger.info(f"Model already exists at {target_path}")

def load_local_model(model_path, default_model, is_scoring=False):
    try:
        if not os.path.exists(model_path):
            download_model(default_model, model_path)
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForSequenceClassification.from_pretrained(model_path, num_labels=1) if is_scoring else AutoModelForCausalLM.from_pretrained(model_path)
        return model, tokenizer
    except Exception as e:
        logger.error(f"Failed to load local model: {e}")
        return None, None

def fetch_resume(candidate_id):
    try:
        response = requests.get(f"{RESUME_SERVICE_URL}/resumes/{candidate_id}")
        if response.status_code == 200:
            return response.json().get('resume', '')
        logger.warning(f"Failed to fetch resume for {candidate_id}: {response.status_code}")
        return ''
    except Exception as e:
        logger.error(f"Resume fetch failed: {e}")
        return ''

def fetch_job_description(job_id):
    try:
        response = requests.get(f"{JOB_SERVICE_URL}/jds/{job_id}")
        if response.status_code == 200:
            return response.json().get('job_description', '')
        logger.warning(f"Failed to fetch JD for {job_id}: {response.status_code}")
        return ''
    except Exception as e:
        logger.error(f"JD fetch failed: {e}")
        return ''

def generate_initial_question(candidate_id, job_id):
    resume = fetch_resume(candidate_id)
    job_description = fetch_job_description(job_id)
    prompt = f"Based on the resume: '{resume[:500]}' and job description: '{job_description[:500]}', generate a challenging coding interview question."

    if AZURE_QUESTION_ENDPOINT and AZURE_API_KEY:
        try:
            response = requests.post(
                AZURE_QUESTION_ENDPOINT,
                json={"prompt": prompt},
                headers={"Authorization": f"Bearer {AZURE_API_KEY}"}
            )
            if response.status_code == 200:
                return response.json().get('question', "Write a function to reverse a linked list.")
        except Exception as e:
            logger.warning(f"Azure question endpoint failed: {e}")

    model, tokenizer = load_local_model(QUESTION_MODEL_PATH, DEFAULT_QUESTION_MODEL)
    if model and tokenizer:
        try:
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=50)
            outputs = model.generate(**inputs, max_length=100, num_return_sequences=1)
            question = tokenizer.decode(outputs[0], skip_special_tokens=True).split('\n')[0].strip()
            return question if question else "Write a function to sort an array."
        except Exception as e:
            logger.error(f"Local question generation failed: {e}")

    return "Write a function to reverse a linked list."

def generate_follow_up_question(transcript):
    prompt = f"Based on the response: '{transcript}', generate a follow-up coding question."

    if AZURE_QUESTION_ENDPOINT and AZURE_API_KEY:
        try:
            response = requests.post(
                AZURE_QUESTION_ENDPOINT,
                json={"prompt": prompt},
                headers={"Authorization": f"Bearer {AZURE_API_KEY}"}
            )
            if response.status_code == 200:
                return response.json().get('question', "Explain your solution.")
        except Exception as e:
            logger.warning(f"Azure question endpoint failed: {e}")

    model, tokenizer = load_local_model(QUESTION_MODEL_PATH, DEFAULT_QUESTION_MODEL)
    if model and tokenizer:
        try:
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=50)
            outputs = model.generate(**inputs, max_length=100, num_return_sequences=1)
            question = tokenizer.decode(outputs[0], skip_special_tokens=True).split('\n')[0].strip()
            return question if question else "Explain your solution."
        except Exception as e:
            logger.error(f"Local follow-up generation failed: {e}")

    return "Explain your solution."

def score_response(question, response, code=None):
    input_text = f"{question} {response} {code or ''}"

    if AZURE_SCORING_ENDPOINT and AZURE_API_KEY:
        try:
            response = requests.post(
                AZURE_SCORING_ENDPOINT,
                json={"input": input_text},
                headers={"Authorization": f"Bearer {AZURE_API_KEY}"}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('score', 5.0) * 10, data.get('feedback', "Evaluated by Azure.")
        except Exception as e:
            logger.warning(f"Azure scoring endpoint failed: {e}")

    model, tokenizer = load_local_model(SCORING_MODEL_PATH, DEFAULT_SCORING_MODEL, is_scoring=True)
    if model and tokenizer:
        try:
            inputs = tokenizer(input_text, return_tensors='pt', truncation=True, padding='max_length', max_length=512)
            with torch.no_grad():
                outputs = model(**inputs)
            score = outputs.logits.item() * 10
            feedback = "Evaluated by local model."
            return min(max(score, 0), 10), feedback
        except Exception as e:
            logger.error(f"Local scoring failed: {e}")

    score = 5.0
    if response:
        score += 2.5
    if code and ("def " in code or "function" in code):
        score += 2.5
    return min(score, 10), "Heuristic evaluation."

def transcribe_audio(audio_path):
    if not whisper_model:
        logger.warning("Faster Whisper not available, using mock transcription.")
        return "Mock transcription of candidate response."

    try:
        segments, _ = whisper_model.transcribe(audio_path, beam_size=5)
        return " ".join(segment.text for segment in segments)
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return "Error in transcription."
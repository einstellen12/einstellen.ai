from transformers import pipeline
import os
import logging

logger = logging.getLogger('interview')
MODEL_DIR = os.path.join(os.path.dirname(__file__), '../../models/tinyllama')

def get_tinyllama():
    if not os.path.exists(MODEL_DIR):
        logger.info("Downloading TinyLlama model...")
        tinyllama = pipeline('text-generation', model='TinyLlama/TinyLlama-1.1B-Chat-v1.0', device=0, local_files_only=False)
        tinyllama.model.save_pretrained(MODEL_DIR)
        tinyllama.tokenizer.save_pretrained(MODEL_DIR)
    else:
        logger.info("Using local TinyLlama model...")
        tinyllama = pipeline('text-generation', model=MODEL_DIR, device=0, local_files_only=True)
    return tinyllama
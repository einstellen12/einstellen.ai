import whisper

class WhisperSTT:
    def __init__(self):
        self.model = whisper.load_model('base', device='cuda')

    def transcribe(self, audio_data):
        return self.model.transcribe(audio_data, fp16=True)['text']
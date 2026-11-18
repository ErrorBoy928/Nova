"""
voice package for AI Desktop Assistant
"""
from voice.tts import tts, TTSEngine, clean_text_for_speech, is_urdu_text
from voice.stt import SingleShotVoiceWorker, ContinuousVoiceWorker, transcribe_audio_bytes

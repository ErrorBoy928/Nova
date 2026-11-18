"""
voice/stt.py

Speech-to-Text (STT) system with:
1. Dynamic ambient noise calibration & audio pre-processing.
2. Continuous Hands-Free Background Listener with Urdu and English recognition.
3. Single-shot voice recording with auto-resetting state.
Direct, natural listening without requiring any wake word.
"""

from __future__ import annotations

import io
import time
import wave
import numpy as np
from PySide6.QtCore import QObject, Signal

from utils.logger import get_logger

log = get_logger(__name__)


def transcribe_audio_bytes(audio_bytes: bytes, preferred_language: str = "auto") -> str:
    """Transcribes WAV audio using Google Speech API with Urdu & English bilingual recognition."""
    import speech_recognition as sr

    wav_io = io.BytesIO(audio_bytes)
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 280

    with sr.AudioFile(wav_io) as source:
        audio_data = recognizer.record(source)

    recognized_text = ""
    # Try Urdu first if preferred or auto
    if preferred_language in ("ur", "auto"):
        try:
            recognized_text = recognizer.recognize_google(audio_data, language="ur-PK")
        except Exception:
            try:
                recognized_text = recognizer.recognize_google(audio_data, language="en-US")
            except Exception:
                pass
    else:
        try:
            recognized_text = recognizer.recognize_google(audio_data, language="en-US")
        except Exception:
            try:
                recognized_text = recognizer.recognize_google(audio_data, language="ur-PK")
            except Exception:
                pass

    return (recognized_text or "").strip()


class SingleShotVoiceWorker(QObject):
    listening_started = Signal()
    transcription_ready = Signal(str)
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, preferred_language: str = "auto", record_seconds: int = 5):
        super().__init__()
        self.preferred_language = preferred_language
        self.record_seconds = record_seconds
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            import sounddevice as sd

            self.listening_started.emit()
            samplerate = 16000
            channels = 1

            recording = sd.rec(
                int(self.record_seconds * samplerate),
                samplerate=samplerate,
                channels=channels,
                dtype="int16"
            )
            sd.wait()

            if self._is_cancelled:
                return

            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)
                wf.setframerate(samplerate)
                wf.writeframes(recording.tobytes())
            audio_bytes = wav_io.getvalue()

            text = transcribe_audio_bytes(audio_bytes, self.preferred_language)
            if text:
                self.transcription_ready.emit(text)
            else:
                self.error_occurred.emit("No speech recognized. Please try again.")
        except Exception as exc:
            log.warning("Single-shot voice error: {}", exc)
            self.error_occurred.emit(f"Microphone error: {exc}")
        finally:
            self.finished.emit()


class ContinuousVoiceWorker(QObject):
    """Continuous background listener with dynamic noise calibration for natural hands-free voice."""

    speech_detected = Signal(str)
    status_changed = Signal(str)

    def __init__(self, preferred_language: str = "auto"):
        super().__init__()
        self.preferred_language = preferred_language
        self._running = True
        self._paused = False

    def stop(self):
        self._running = False

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def run(self):
        import sounddevice as sd

        samplerate = 16000
        block_duration = 0.25  # seconds
        block_samples = int(samplerate * block_duration)
        channels = 1

        log.info("Continuous voice listening thread starting...")
        self.status_changed.emit("Calibrating microphone...")

        try:
            with sd.InputStream(samplerate=samplerate, channels=channels, dtype="int16") as stream:
                # Dynamic ambient noise calibration
                ambient_samples = []
                for _ in range(2):
                    blk, _ = stream.read(block_samples)
                    ambient_samples.append(blk.flatten())
                floor_rms = float(np.sqrt(np.mean(np.concatenate(ambient_samples).astype(np.float32) ** 2)))
                silence_threshold = max(380.0, min(1400.0, floor_rms * 2.2 + 180.0))
                log.info("Calibrated silence threshold: {:.1f}", silence_threshold)

                silence_blocks_limit = int(1.3 / block_duration)  # 1.3s silence ends utterance
                max_record_blocks = int(14.0 / block_duration)   # 14s max utterance

                self.status_changed.emit("Listening in background...")

                while self._running:
                    if self._paused:
                        time.sleep(0.2)
                        continue

                    data, _ = stream.read(block_samples)
                    samples = data.flatten()
                    # Filter DC offset
                    samples_float = samples.astype(np.float32) - np.mean(samples)
                    rms = np.sqrt(np.mean(samples_float ** 2)) if len(samples_float) > 0 else 0

                    if rms > silence_threshold:
                        self.status_changed.emit("Listening to you...")
                        speech_buffer = [data.copy()]
                        silence_count = 0

                        while self._running and len(speech_buffer) < max_record_blocks:
                            if self._paused:
                                break
                            chunk, _ = stream.read(block_samples)
                            chunk_samples = chunk.flatten().astype(np.float32) - np.mean(chunk)
                            c_rms = np.sqrt(np.mean(chunk_samples ** 2)) if len(chunk_samples) > 0 else 0
                            speech_buffer.append(chunk.copy())

                            if c_rms < silence_threshold:
                                silence_count += 1
                                if silence_count >= silence_blocks_limit:
                                    break
                            else:
                                silence_count = 0

                        if not self._running or self._paused:
                            continue

                        # Minimum speech check (~0.75s)
                        if len(speech_buffer) > 2:
                            self.status_changed.emit("Processing speech...")
                            full_recording = np.concatenate(speech_buffer, axis=0)

                            wav_io = io.BytesIO()
                            with wave.open(wav_io, "wb") as wf:
                                wf.setnchannels(channels)
                                wf.setsampwidth(2)
                                wf.setframerate(samplerate)
                                wf.writeframes(full_recording.tobytes())
                            audio_bytes = wav_io.getvalue()

                            recognized = transcribe_audio_bytes(audio_bytes, self.preferred_language)
                            if recognized and len(recognized) > 1:
                                log.info("Continuous voice recognized: '{}'", recognized)
                                self.status_changed.emit(f"Heard: '{recognized}'")
                                self.speech_detected.emit(recognized)
                            else:
                                self.status_changed.emit("Listening in background...")
                        else:
                            self.status_changed.emit("Listening in background...")
        except Exception as exc:
            log.warning("Continuous voice listener exception: {}", exc)
            self.status_changed.emit("Microphone paused.")

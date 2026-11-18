"""
voice/tts.py

High-quality Text-to-Speech system with English and Urdu voice support.
Uses Microsoft Edge TTS (natural neural voices) with automatic language detection
and fallback to offline pyttsx3.
"""

from __future__ import annotations

# Python 3.15 lazy_import safeguard for concurrent.futures and asyncio
import concurrent.futures
from concurrent.futures.thread import ThreadPoolExecutor
concurrent.futures.ThreadPoolExecutor = ThreadPoolExecutor
import asyncio.base_events
asyncio.base_events.concurrent.futures.ThreadPoolExecutor = ThreadPoolExecutor

import asyncio
import os
import re
import threading
import time
from pathlib import Path

from utils.app_paths import user_data_dir
from utils.logger import get_logger

log = get_logger(__name__)

# Standard natural neural voices
VOICE_EN = "en-US-AriaNeural"
VOICE_UR_FEMALE = "ur-PK-UzmaNeural"
VOICE_UR_MALE = "ur-PK-AsadNeural"
VOICE_UR = VOICE_UR_FEMALE


def is_urdu_text(text: str) -> bool:
    """Detects whether text contains Urdu / Arabic characters."""
    urdu_chars = len(re.findall(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]", text))
    total_letters = len(re.findall(r"[a-zA-Z\u0600-\u06FF]", text))
    if total_letters == 0:
        return False
    return (urdu_chars / total_letters) > 0.15


def clean_text_for_speech(text: str) -> str:
    """Cleans text so that the neural TTS engine reads it fluently and naturally."""
    if not text:
        return ""

    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", " Code block provided on screen. ", text)
    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove action tags like [action:...] or <action:...>
    text = re.sub(r"\[action:[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<action:[^>]*>", "", text, flags=re.IGNORECASE)
    # Remove markdown links [title](url) -> title
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Remove raw URLs
    text = re.sub(r"https?://\S+|www\.\S+", " link ", text)
    # Remove paths like E:\AI_Assistant\... -> file path
    text = re.sub(r"[a-zA-Z]:\\[a-zA-Z0-9_\-\\]+", " specified path ", text)
    # Remove thinking tags
    text = re.sub(r"<(think|thinking|reasoning)>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove markdown bullets, headers, bold, italics
    text = re.sub(r"[\*\_#\>~\|]", " ", text)
    # Replace common abbreviations for smooth speech
    text = text.replace("&", " and ")
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


class TTSEngine:
    is_urdu_text = staticmethod(is_urdu_text)
    clean_text_for_speech = staticmethod(clean_text_for_speech)

    def __init__(self):
        self._is_speaking = False
        self._lock = threading.Lock()
        self._temp_dir = user_data_dir() / "temp_audio"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_old_temp_files()

    def _cleanup_old_temp_files(self):
        """Purge temporary audio files older than 30 minutes."""
        try:
            now = time.time()
            for p in self._temp_dir.glob("tts_*.mp3"):
                if now - p.stat().st_mtime > 1800:
                    try:
                        p.unlink()
                    except OSError:
                        pass
        except Exception:
            pass

    def is_speaking(self) -> bool:
        return self._is_speaking

    def stop(self) -> None:
        """Immediately stops any currently playing audio."""
        self._is_speaking = False
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass

    def speak(self, text: str, voice: str | None = None, on_finished=None) -> None:
        """Speaks the text in a separate background thread."""
        cleaned = clean_text_for_speech(text)
        if not cleaned:
            if on_finished:
                on_finished()
            return

        thread = threading.Thread(
            target=self._run_tts,
            args=(cleaned, voice, on_finished),
            daemon=True
        )
        thread.start()

    def _run_tts(self, text: str, custom_voice: str | None, callback) -> None:
        with self._lock:
            self._is_speaking = True

        try:
            selected_voice = custom_voice
            if not selected_voice:
                selected_voice = VOICE_UR_FEMALE if is_urdu_text(text) else VOICE_EN

            # Try Edge TTS first for realistic human voices
            success = self._speak_edge_tts(text, selected_voice)
            if not success:
                # Fallback to offline SAPI5
                self._speak_pyttsx3(text)
        except Exception as e:
            log.warning("TTS generation encountered error: {}", e)
        finally:
            with self._lock:
                self._is_speaking = False
            if callback:
                try:
                    callback()
                except Exception:
                    pass

    def _speak_edge_tts(self, text: str, voice: str) -> bool:
        try:
            import edge_tts
            output_file = self._temp_dir / f"tts_{os.getpid()}_{threading.get_ident()}_{int(time.time()*1000)}.mp3"

            async def _synthesize():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(str(output_file))

            # Run asynchronous edge-tts in a new event loop for this worker thread
            asyncio.run(_synthesize())

            if not output_file.exists() or output_file.stat().st_size == 0:
                return False

            self._play_audio_file(output_file)
            try:
                output_file.unlink(missing_ok=True)
            except Exception:
                pass
            return True
        except Exception as e:
            log.warning("Edge TTS failed ({}), trying pyttsx3 fallback.", e)
            return False

    def _speak_pyttsx3(self, text: str) -> None:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 170)
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            log.warning("pyttsx3 fallback failed: {}", e)

    def _play_audio_file(self, audio_path: Path) -> None:
        """Plays the audio file cleanly via sounddevice + soundfile."""
        try:
            import soundfile as sf
            import sounddevice as sd
            data, fs = sf.read(str(audio_path), dtype='float32')
            sd.play(data, fs)
            sd.wait()
        except Exception as exc:
            log.warning("sounddevice playback issue: {}, trying shell player fallback", exc)
            import subprocess
            cmd = f'''
            $player = New-Object -ComObject WMPlayer.OCX
            $player.URL = "{audio_path}"
            $player.controls.play()
            while ($player.playState -ne 1) {{ Start-Sleep -Milliseconds 100 }}
            '''
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)


# Global singleton
tts = TTSEngine()

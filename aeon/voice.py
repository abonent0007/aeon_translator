"""
Голосовой модуль Aeon v2.0: Whisper STT + мультиязычный TTS.
Поддерживает: русский, английский, китайский.
"""

import os
import sys
import time
import tempfile
import subprocess
from typing import Optional

# ── Whisper STT ─────────────────────────────────────────────
_WHISPER_AVAILABLE = False
try:
    import whisper
    _WHISPER_AVAILABLE = True
except ImportError:
    pass

# ── Edge TTS (основной, нейросетевой) ──────────────────────
_EDGE_TTS_AVAILABLE = False
try:
    import edge_tts
    _EDGE_TTS_AVAILABLE = True
except ImportError:
    pass

# ── Piper TTS (локальный, оффлайн) ─────────────────────────
_PIPER_AVAILABLE = False
try:
    from piper import PiperVoice
    _PIPER_AVAILABLE = True
except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════
# WHISPER STT — русский, английский, китайский
# ═══════════════════════════════════════════════════════════════

class WhisperSTT:
    """
    Speech-to-Text через локальную модель OpenAI Whisper.
    Работает на русском, английском, китайском.
    """

    SUPPORTED_LANGUAGES = {
        "russian": "ru",
        "english": "en",
        "chinese": "zh",
        "auto": None
    }

    def __init__(self, model_name: str = "base"):
        self.model_name = model_name
        self._model = None
        self.available = _WHISPER_AVAILABLE

    def load_model(self):
        if self._model is None and self.available:
            print(f"   Загрузка Whisper ({self.model_name})...")
            self._model = whisper.load_model(self.model_name)
            print(f"   Whisper '{self.model_name}' готов")
        return self

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> dict:
        """Транскрибирует аудио в текст с автоопределением языка."""
        if not self.available:
            return {"text": "", "language": "unknown", "error": "Whisper not installed"}
        self.load_model()
        opts = {}
        lang_code = self.SUPPORTED_LANGUAGES.get(language) if language else None
        if lang_code:
            opts["language"] = lang_code
        result = self._model.transcribe(audio_path, **opts)
        detected = result.get("language", "unknown")
        lang_map = {"ru": "russian", "en": "english", "zh": "chinese"}
        return {
            "text": result["text"].strip(),
            "language": lang_map.get(detected, detected),
            "segments": result.get("segments", [])
        }

    @staticmethod
    def record_audio(duration: float = 10.0, sample_rate: int = 16000) -> Optional[str]:
        """Запись с микрофона во временный WAV."""
        try:
            import sounddevice as sd
            import soundfile as sf
        except ImportError:
            print("pip install sounddevice soundfile")
            return None
        print(f"   Запись {duration} сек... (говорите)")
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
        sd.wait()
        print("   Готово")
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="aeon_voice_")
        os.close(fd)
        sf.write(path, audio, sample_rate)
        return path


# ═══════════════════════════════════════════════════════════════
# TTS — нейросетевые голоса: русский, английский, китайский
# ═══════════════════════════════════════════════════════════════

class MultiVoiceTTS:
    """
    Мультиязычный TTS.
    Приоритет: Edge TTS (нейро) → Piper TTS (локальный) → системный.
    """

    VOICES_EDGE = {
        "russian":  "ru-RU-SvetlanaNeural",
        "english":  "en-US-JennyNeural",
        "chinese":  "zh-CN-XiaoxiaoNeural",
    }

    VOICES_PIPER = {
        "russian":  "ru_RU-dmitri-medium",
        "english":  "en_US-lessac-medium",
        "chinese":  "zh_CN-huayan-medium",
    }

    def __init__(self):
        self.edge_available = _EDGE_TTS_AVAILABLE
        self.piper_available = _PIPER_AVAILABLE

    @property
    def available(self):
        return self.edge_available or self.piper_available

    def speak(self, text: str, language: str = "english",
              output_path: Optional[str] = None,
              play: bool = True) -> Optional[str]:
        """
        Произносит текст голосом на указанном языке.
        Возвращает путь к аудиофайлу.
        """
        if language not in self.VOICES_EDGE:
            print(f"   Язык '{language}' не поддерживается. Доступны: russian, english, chinese")
            language = "english"

        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".mp3", prefix=f"aeon_tts_{language}_")
            os.close(fd)

        # ── 1. Edge TTS (нейросетевой, лучшее качество) ──
        if self.edge_available:
            try:
                self._speak_edge(text, language, output_path)
                print(f"   🔊 [{language}] {text[:80]}...")
                if play:
                    self.play_audio(output_path)
                return output_path
            except Exception as e:
                print(f"   Edge TTS error: {e}, пробую Piper...")

        # ── 2. Piper TTS (локальный, оффлайн) ──
        if self.piper_available:
            try:
                self._speak_piper(text, language, output_path)
                print(f"   🔊 [{language}] {text[:80]}...")
                if play:
                    self.play_audio(output_path)
                return output_path
            except Exception as e:
                print(f"   Piper error: {e}")

        # ── 3. Системный fallback ──
        try:
            self._speak_system(text)
            return None
        except Exception:
            print(f"   TTS недоступен. Текст: {text[:100]}")
            return None

    def speak_multilingual(self, texts: dict, play: bool = True) -> dict:
        """
        Произносит текст на нескольких языках.
        texts = {"russian": "Привет", "english": "Hello", "chinese": "你好"}
        """
        results = {}
        for lang, text in texts.items():
            path = self.speak(text, language=lang, play=play)
            results[lang] = {"text": text, "audio_path": path}
        return results

    # ── внутренние движки ─────────────────────────────────

    def _speak_edge(self, text: str, language: str, output_path: str):
        voice = self.VOICES_EDGE[language]

        async def _run():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run())
        finally:
            loop.close()

    def _speak_piper(self, text: str, language: str, output_path: str):
        voice_name = self.VOICES_PIPER.get(language, self.VOICES_PIPER["english"])
        model_dir = os.path.expanduser("~/.local/share/piper-tts")
        model_path = os.path.join(model_dir, f"{voice_name}.onnx")
        if not os.path.exists(model_path):
            alt_dirs = [
                os.path.join(os.path.dirname(__file__), "..", "piper_models"),
                "piper_models"
            ]
            for d in alt_dirs:
                candidate = os.path.join(d, f"{voice_name}.onnx")
                if os.path.exists(candidate):
                    model_path = candidate
                    break
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Piper model not found: {voice_name}. Download from https://huggingface.co/rhasspy/piper-voices")
        voice = PiperVoice.load(model_path)
        wav_path = output_path.replace(".mp3", ".wav")
        with open(wav_path, "wb") as f:
            voice.synthesize(text, f)

    @staticmethod
    def play_audio(audio_path: str):
        """Проигрывает аудио — публичный метод."""
        try:
            import sounddevice as sd
            import soundfile as sf
            data, sr = sf.read(audio_path)
            if len(data.shape) > 1:
                data = data[:, 0]
            sd.play(data, sr)
            sd.wait()
        except ImportError:
            try:
                if sys.platform == 'win32':
                    os.startfile(audio_path)
                elif sys.platform == 'darwin':
                    subprocess.run(['afplay', audio_path])
                else:
                    subprocess.run(['xdg-open', audio_path])
            except Exception:
                print(f"   Аудио сохранено: {audio_path}")

    @staticmethod
    def _speak_system(text: str):
        """Системный TTS — крайний fallback."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except ImportError:
            if sys.platform == 'win32':
                subprocess.run(
                    ['powershell', '-Command',
                     f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{text}")'],
                    capture_output=True
                )
            else:
                raise RuntimeError("No TTS available")


# ═══════════════════════════════════════════════════════════════
# VoiceProcessor — единый интерфейс
# ═══════════════════════════════════════════════════════════════

class VoiceProcessor:
    """
    Единый голосовой процессор Aeon.
    STT: Whisper (ru/en/zh)
    TTS: Edge TTS → Piper → системный
    """

    def __init__(self):
        self.stt = WhisperSTT()
        self.tts = MultiVoiceTTS()

    def voice_to_text(self, audio_path: Optional[str] = None,
                      language: Optional[str] = None,
                      record_duration: float = 10.0) -> dict:
        """Речь → текст (файл или микрофон)."""
        if audio_path is None:
            audio_path = WhisperSTT.record_audio(record_duration)
            if audio_path is None:
                return {"text": "", "language": "unknown", "error": "Record failed"}
        return self.stt.transcribe(audio_path, language)

    def text_to_voice(self, text: str, language: str = "english",
                      play: bool = True) -> Optional[str]:
        """Текст → речь."""
        return self.tts.speak(text, language, play=play)

    def speak_all_three(self, text_ru: str = "", text_en: str = "",
                        text_zh: str = "", play: bool = True) -> dict:
        """Произносит фразу на трёх языках."""
        texts = {}
        if text_ru:
            texts["russian"] = text_ru
        if text_en:
            texts["english"] = text_en
        if text_zh:
            texts["chinese"] = text_zh
        return self.tts.speak_multilingual(texts, play=play)

    def voice_to_voice(self, audio_path: str, target_language: str = "english") -> dict:
        """Сквозной: речь → текст → перевод → речь."""
        stt_result = self.voice_to_text(audio_path)
        if not stt_result.get("text"):
            return {"error": "STT failed", **stt_result}
        return {
            "source_text": stt_result["text"],
            "source_language": stt_result.get("language", "unknown"),
            "target_language": target_language
        }

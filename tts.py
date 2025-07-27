"""
TTS Manager for Alibaba Cloud DashScope CosyVoice

This module handles speech synthesis using the DashScope SDK.
It is designed to be efficient by caching generated speech and using a robust
MP3 playback library (pygame).
"""

import os
import time
import hashlib
import json
import dashscope
import pyaudio
from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat, ResultCallback
import importlib.resources

# --- Configuration ---
TEMP_MP3_PATH = os.path.join(os.path.dirname(__file__), "temp_tts_output.mp3")
TTS_CACHE_DIR = os.path.join(os.path.dirname(__file__), "tts_cache")
TTS_CACHE_EN_DIR = os.path.join(TTS_CACHE_DIR, "en")
TTS_CACHE_ZH_DIR = os.path.join(TTS_CACHE_DIR, "zh")
TTS_PROMPTS = {}


def _load_alibaba_api_key():
    """
    Load Alibaba API key from environment variables.

    Returns:
        str or None: The Alibaba API key if found, None otherwise.
    """
    # Get the key from environment variables
    api_key = os.environ.get("ALIBABA_API_KEY")
    if api_key:
        print("[TTS Manager] Using Alibaba API key from environment variable")
        return api_key

    print("[TTS Manager] ALIBABA_API_KEY environment variable not set")
    return None


# DashScope CosyVoice Speaker Mapping
COSVOICE_VOICE_MAP = {
    "ZH": "longxiaochun_v2",
    "EN": "longxiaochun_v2",  # Using the same voice for both languages for now
}

# --- Initialization Status ---
TTS_INITIALIZED = False

# Global PyAudio instance
PYAUDIO_INSTANCE = None


def initialize_tts():
    """
    Initializes the DashScope SDK. This should be
    called once when the application starts.
    """
    global TTS_INITIALIZED, PYAUDIO_INSTANCE
    print("[TTS Manager] Initializing Text-to-Speech service...")
    start_time = time.time()

    load_tts_prompts()

    # Load Alibaba API key from secrets.json
    alibaba_api_key = _load_alibaba_api_key()
    if not alibaba_api_key:
        print(
            "[TTS Manager] CRITICAL ERROR: 'alibaba_api_key' not found in secrets.json."
        )
        TTS_INITIALIZED = False
        return False

    dashscope.api_key = alibaba_api_key
    print("[TTS Manager] Alibaba API Key found and set for DashScope.")
    TTS_INITIALIZED = True

    # Initialize PyAudio
    try:
        PYAUDIO_INSTANCE = pyaudio.PyAudio()
        print("[TTS Manager] PyAudio initialized.")
    except Exception as e:
        print(f"[TTS Manager] CRITICAL ERROR: Failed to initialize PyAudio: {e}")
        return False

    duration = time.time() - start_time
    print(f"[TTS Manager] TTS initialization complete in {duration:.2f} seconds.")
    return True


def load_tts_prompts():
    # Load TTS prompts from the file system
    global TTS_PROMPTS
    try:
        import os

        # Try to find the data file in the file system
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_file_path = os.path.join(base_dir, "data", "generated_tts_prompts.json")
        # If not found, try in the current directory
        if not os.path.exists(data_file_path):
            data_file_path = os.path.join(
                os.getcwd(), "data", "generated_tts_prompts.json"
            )
        with open(data_file_path, "r", encoding="utf-8") as f:
            TTS_PROMPTS = json.load(f).get("tts_prompts", {})
        print("[TTS Manager] Loaded TTS prompts from file system.")
    except Exception as e:
        print(f"[TTS Manager] WARNING: Failed to load TTS prompts: {e}")
        TTS_PROMPTS = {}


def get_tts_prompt(key: str, default: str | None = None) -> str:
    return TTS_PROMPTS.get(key, default or f"Prompt not found: {key}")


def _get_cache_dir(language: str) -> str:
    return TTS_CACHE_EN_DIR if language.upper() == "EN" else TTS_CACHE_ZH_DIR


def _get_cached_file_path(text: str, language: str, key: str | None = None) -> str:
    text_hash = hashlib.md5((key or text).encode("utf-8")).hexdigest()
    cache_dir = _get_cache_dir(language)
    return os.path.join(cache_dir, f"{text_hash}.wav")  # Note .wav extension


def _play_audio_file(file_path: str):
    """Play an audio file using pygame.mixer (blocking)."""
    # Since we're using PyAudio for streaming, this function is kept for compatibility
    # but won't be used in the new implementation
    pass


class Callback(ResultCallback):
    _player = None
    _stream = None
    _completed = False
    _error = None

    def __init__(self, player):
        self._player = player
        self.audio_data = bytearray()

    def on_open(self):
        print("[TTS Callback] Connection established")
        # Create stream when connection opens
        if self._player is not None:
            self._stream = self._player.open(
                format=pyaudio.paInt16, channels=1, rate=22050, output=True
            )
        else:
            print("[TTS Callback] Warning: Player is None, skipping stream creation")
            # Create a mock stream object for testing
            self._stream = None
        self._completed = False
        self._error = None

    def on_complete(self):
        print("[TTS Callback] Speech synthesis complete")
        self._completed = True

    def on_error(self, message: str):
        print(f"[TTS Callback] Speech synthesis error: {message}")
        self._error = message
        self._completed = True

    def on_close(self):
        print("[TTS Callback] Connection closing")
        # Stop and close stream
        if self._stream:
            print("[TTS Callback] Stopping and closing audio stream")
            # Wait a bit to ensure all audio data has finished playing
            import time

            time.sleep(0.1)  # Small delay to allow buffer to drain
            self._stream.stop_stream()
            self._stream.close()
            print("[TTS Callback] Audio stream closed")
        self._completed = True

    def on_event(self, message):
        pass

    def on_data(self, data: bytes) -> None:
        print(f"[TTS Callback] Received audio data, length: {len(data)}")
        # Store audio data for saving to file
        self.audio_data.extend(data)
        # Play audio data
        if self._stream:
            # Set volume to 100% before playing audio (only once per stream)
            if not hasattr(self, "_volume_set"):
                try:
                    # Attempt to set system volume to 100%
                    if hasattr(self, "_volume_set") and not self._volume_set:
                        # Platform-specific volume setting would go here
                        # For now, we'll just mark it as set
                        self._volume_set = True
                except Exception as e:
                    print(f"[TTS Callback] Warning: Could not set system volume: {e}")
                    self._volume_set = True  # Prevent repeated attempts

            print("[TTS Callback] Playing audio data")
            self._stream.write(data)
            print("[TTS Callback] Finished playing audio data")

    def is_completed(self):
        return self._completed

    def get_error(self):
        return self._error


def speak(text: str, language: str, speed: float = 1.0, key: str | None = None):
    """Generates and plays speech using DashScope CosyVoice."""
    global PYAUDIO_INSTANCE

    if not TTS_INITIALIZED:
        print(f"[TTS Manager] CRITICAL: TTS not initialized. Fallback: {text}")
        return

    # Check cache first
    cached_file_path = _get_cached_file_path(text, language, key)
    if os.path.exists(cached_file_path):
        print(f"[TTS Manager] Using cached file: {cached_file_path}")
        # For cached files, we can play them with simpleaudio
        try:
            # Set volume to 100% before playing audio
            try:
                # Attempt to set system volume to 100%
                # Platform-specific volume setting would go here
                pass
            except Exception as e:
                print(f"[TTS Manager] Warning: Could not set system volume: {e}")

            import simpleaudio as sa

            wave_obj = sa.WaveObject.from_wave_file(cached_file_path)
            play_obj = wave_obj.play()
            play_obj.wait_done()  # Wait until sound has finished playing
        except Exception as e:
            print(
                f"[TTS Manager] Error playing cached audio file {cached_file_path}: {e}"
            )
        return

    try:
        # Create callback with PyAudio instance
        callback = Callback(PYAUDIO_INSTANCE)

        # Create synthesizer instance
        synthesizer = SpeechSynthesizer(
            model="cosyvoice-v2",
            voice=COSVOICE_VOICE_MAP[language.upper()],
            format=AudioFormat.PCM_22050HZ_MONO_16BIT,
            callback=callback,
        )

        # Call the synthesizer with text
        synthesizer.call(text)

        # Wait for completion
        import time

        while not callback.is_completed():
            time.sleep(0.1)

        # Check for errors
        if callback.get_error():
            print(f"[TTS Manager] DashScope synthesis error: {callback.get_error()}")
            return

        # Save to cache
        if len(callback.audio_data) > 0:
            cache_dir = _get_cache_dir(language)
            os.makedirs(cache_dir, exist_ok=True)

            # Convert PCM to WAV for caching
            import wave

            with wave.open(cached_file_path, "wb") as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(22050)  # 22050 Hz
                wav_file.writeframes(callback.audio_data)
            print(f"[TTS Manager] Cached generated speech to: {cached_file_path}")

    except Exception as e:
        print(f"[TTS Manager] DashScope synthesis error: {e}")


def pregenerate_fixed_strings():
    print("[TTS Manager] Pre-generating fixed strings...")
    for key, prompt_text in TTS_PROMPTS.items():
        language = (
            "ZH" if key.endswith("_zh") else "EN" if key.endswith("_en") else None
        )
        if language:
            print(
                f"[TTS Manager] Generating: '{prompt_text}' ({language}) for key '{key}'"
            )
            speak(prompt_text, language, key=key)
    print("[TTS Manager] Pre-generation complete.")

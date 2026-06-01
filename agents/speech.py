"""Speech-to-Text (Groq Whisper) and Text-to-Speech (gTTS) utilities."""

import io
import os
import time
from pathlib import Path

from gtts import gTTS
from groq import Groq

from config import GROQ_WHISPER_MODEL, FILLER_WORDS

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


def transcribe_audio(audio_path: str | Path) -> dict:
    """Transcribe an audio file using Groq Whisper. Returns transcript + speech metrics."""
    start = time.time()
    with open(audio_path, "rb") as f:
        result = _get_client().audio.transcriptions.create(
            file=f,
            model=GROQ_WHISPER_MODEL,
            response_format="verbose_json",
        )
    duration_sec = time.time() - start

    transcript: str = result.text.strip()
    words = transcript.split()
    word_count = len(words)
    audio_duration = getattr(result, "duration", duration_sec) or duration_sec
    wpm = (word_count / audio_duration * 60) if audio_duration > 0 else 0

    lower_words = [w.lower().strip(".,!?") for w in words]
    filler_count = sum(1 for w in lower_words if w in FILLER_WORDS)
    filler_rate = filler_count / word_count if word_count > 0 else 0.0

    return {
        "transcript": transcript,
        "word_count": word_count,
        "duration_sec": round(audio_duration, 2),
        "wpm": round(wpm, 1),
        "filler_count": filler_count,
        "filler_rate": round(filler_rate, 4),
    }


def synthesize_speech(text: str, output_path: str | Path) -> Path:
    """Convert text to speech using gTTS and save to output_path."""
    tts = gTTS(text=text, lang="en", slow=False)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tts.save(str(output_path))
    return output_path

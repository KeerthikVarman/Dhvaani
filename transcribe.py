"""
DhVaani - Audio Transcription Module (Speech-to-Text)
Transcribes audio files into text using Whisper / Faster-Whisper.
"""

import argparse
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOCAL_MODEL_DIR = Path(
    os.path.expanduser("~/.cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120")
)


def transcribe_audio(audio_path: str, model_size_or_path: str = None, language: str = None):
    """
    Transcribes an audio file (.wav, .mp3, etc.) into text.

    Args:
        audio_path (str): Path to audio file.
        model_size_or_path (str, optional): Whisper model name or local path.
        language (str, optional): Optional language code (e.g. 'en', 'hi').

    Returns:
        str: Transcribed text string.
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Check if faster-whisper is available
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("[!] 'faster-whisper' is not installed in this environment.")
        print("[!] Install it with: pip install faster-whisper")
        print("[!] Or use the Dictation / Web Speech API built into 'web_app.py'.")
        return None

    # Use local cached model if available
    if model_size_or_path is None:
        if LOCAL_MODEL_DIR.is_dir():
            model_size_or_path = str(LOCAL_MODEL_DIR)
        else:
            model_size_or_path = "small"

    print(f"Loading Whisper transcription model ({model_size_or_path})...")
    model = WhisperModel(model_size_or_path, device="cpu", compute_type="int8")

    print(f"Transcribing '{audio_path}'...")
    segments, info = model.transcribe(audio_path, language=language, beam_size=5)

    full_text = " ".join([segment.text.strip() for segment in segments])
    print(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
    print(f"\nTranscription:\n{full_text}")
    return full_text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DhVaani - Transcribe Speech to Text")
    parser.add_argument("audio", type=str, help="Path to audio file to transcribe")
    parser.add_argument("--model", type=str, default=None, help="Model size or local path")
    parser.add_argument("--language", type=str, default=None, help="Language code (e.g., en, hi)")

    args = parser.parse_args()
    transcribe_audio(args.audio, model_size_or_path=args.model, language=args.language)


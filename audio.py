"""
DhVaani - Audio Generation Script using ZipVoice
Synthesizes speech from input text using the ZipVoice flow matching model.
"""

import argparse
import math
import os
import struct
import subprocess
import sys
import wave
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ZIPVOICE_DIR = BASE_DIR / "ZipVoice"
ASSETS_DIR = BASE_DIR / "assets"
OUTPUTS_DIR = BASE_DIR / "outputs"

ASSETS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def get_python_executable():
    """Return the venv python executable if available, otherwise fallback to sys.executable"""
    venv_py = BASE_DIR / "venv" / "Scripts" / "python.exe"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable


def devanagari_to_roman(text: str) -> str:
    """
    Transliterate Devanagari (Hindi) script into phonetic Latin characters
    so that models expecting English/Latin alphabets can synthesize it naturally.
    """
    if not any("\u0900" <= c <= "\u097f" for c in text):
        return text

    vowels = {
        "\u0904": "a", "\u0905": "a", "\u0906": "aa", "\u0907": "i", "\u0908": "ee",
        "\u0909": "u", "\u090a": "oo", "\u090b": "ri", "\u090c": "li", "\u090e": "e",
        "\u090f": "e", "\u0910": "ai", "\u0911": "o", "\u0912": "o", "\u0913": "o",
        "\u0914": "au", "\u0960": "ri", "\u0961": "li"
    }
    matras = {
        "\u093e": "aa", "\u093f": "i", "\u0940": "ee", "\u0941": "u",
        "\u0942": "oo", "\u0943": "ri", "\u0944": "ri", "\u0946": "e",
        "\u0947": "e", "\u0948": "ai", "\u0949": "o", "\u094a": "o",
        "\u094b": "o", "\u094c": "au", "\u0962": "li", "\u0963": "li"
    }
    consonants = {
        "\u0915": "k", "\u0916": "kh", "\u0917": "g", "\u0918": "gh", "\u0919": "ng",
        "\u091a": "ch", "\u091b": "chh", "\u091c": "j", "\u091d": "jh", "\u091e": "ny",
        "\u091f": "t", "\u0920": "th", "\u0921": "d", "\u0922": "dh", "\u0923": "n",
        "\u0924": "t", "\u0925": "th", "\u0926": "d", "\u0927": "dh", "\u0928": "n",
        "\u092a": "p", "\u092b": "ph", "\u092c": "b", "\u092d": "bh", "\u092e": "m",
        "\u092f": "y", "\u0930": "r", "\u0932": "l", "\u0933": "l", "\u0935": "v",
        "\u0936": "sh", "\u0937": "sh", "\u0938": "s", "\u0939": "h",
        "\u0958": "q", "\u0959": "kh", "\u095a": "g", "\u095b": "z", "\u095c": "r",
        "\u095d": "rh", "\u095e": "f", "\u095f": "y"
    }
    digits = {
        "\u0966": "0", "\u0967": "1", "\u0968": "2", "\u0969": "3", "\u096a": "4",
        "\u096b": "5", "\u096c": "6", "\u096d": "7", "\u096e": "8", "\u096f": "9"
    }
    virama = "\u094d"
    anusvara = "\u0902"
    chandrabindu = "\u0901"
    visarga = "\u0903"
    purna_virama = "\u0964"
    dirgha_virama = "\u0965"

    result = []
    n = len(text)
    i = 0
    while i < n:
        c = text[i]
        if c in consonants:
            base = consonants[c]
            if i + 1 < n:
                next_c = text[i+1]
                if next_c == virama:
                    result.append(base)
                    i += 2
                    continue
                elif next_c in matras:
                    result.append(base + matras[next_c])
                    i += 2
                    continue
                elif next_c in (anusvara, chandrabindu):
                    result.append(base + "an")
                    i += 2
                    continue
            if i + 1 == n or text[i+1] in " \t\n.,!?":
                result.append(base)
            else:
                result.append(base + "a")
            i += 1
        elif c in vowels:
            result.append(vowels[c])
            i += 1
        elif c in matras:
            result.append(matras[c])
            i += 1
        elif c in (anusvara, chandrabindu):
            result.append("n")
            i += 1
        elif c == visarga:
            result.append("h")
            i += 1
        elif c in (purna_virama, dirgha_virama):
            result.append(".")
            i += 1
        elif c in digits:
            result.append(digits[c])
            i += 1
        elif c == virama:
            i += 1
        else:
            result.append(c)
            i += 1
    return "".join(result)


def ensure_default_prompt():
    """Generates a default reference voice prompt if none exists."""
    prompt_wav = ASSETS_DIR / "default_prompt.wav"
    if not prompt_wav.exists():
        sample_rate = 24000
        duration = 2.0  # seconds
        num_samples = int(sample_rate * duration)

        with wave.open(str(prompt_wav), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)

            values = []
            for i in range(num_samples):
                t = i / sample_rate
                # 220Hz harmonic voice envelope
                sample = (
                    0.5 * math.sin(2 * math.pi * 220 * t)
                    + 0.3 * math.sin(2 * math.pi * 440 * t)
                    + 0.15 * math.sin(2 * math.pi * 660 * t)
                ) * math.exp(-0.5 * (t - 1.0) ** 2)
                val = int(sample * 16384.0)
                values.append(struct.pack("<h", max(-32768, min(32767, val))))

            wav_file.writeframes(b"".join(values))
    return str(prompt_wav)


def synthesize_speech(
    text: str,
    output_path: str = "output.wav",
    prompt_wav: str = None,
    prompt_text: str = "Hello and welcome.",
    model_name: str = "zipvoice",
    speed: float = 1.0,
    num_step: int = 8,
    num_thread: int = None,
):
    """
    Synthesize speech using ZipVoice.

    Args:
        text (str): The text to be synthesized into audio.
        output_path (str): Destination path for the generated WAV file.
        prompt_wav (str, optional): Reference audio file for voice cloning.
        prompt_text (str): Transcription of the reference prompt.
        model_name (str): 'zipvoice' or 'zipvoice_distill'.
        speed (float): Speed factor (default: 1.0).
        num_step (int): Number of inference flow matching steps (default: 8).
        num_thread (int, optional): CPU threads for multi-threading (default: 4).
    """
    if not prompt_wav or not os.path.isfile(prompt_wav):
        prompt_wav = ensure_default_prompt()

    # Transliterate Hindi Devanagari script to phonetic Latin if present
    text = devanagari_to_roman(text)
    prompt_text = devanagari_to_roman(prompt_text)

    if num_thread is None:
        cpu_count = os.cpu_count() or 4
        num_thread = min(max(cpu_count // 2, 2), 6)

    output_abs_path = Path(output_path).resolve()
    prompt_abs_path = Path(prompt_wav).resolve()

    # Configure environment with ZipVoice in PYTHONPATH
    env = os.environ.copy()
    pythonpath = str(ZIPVOICE_DIR)
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{pythonpath};{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = pythonpath

    command = [
        get_python_executable(),
        "-m",
        "zipvoice.bin.infer_zipvoice",
        "--model-name",
        model_name,
        "--prompt-wav",
        str(prompt_abs_path),
        "--prompt-text",
        prompt_text,
        "--text",
        text,
        "--res-wav-path",
        str(output_abs_path),
        "--speed",
        str(speed),
        "--num-step",
        str(num_step),
        "--num-thread",
        str(num_thread),
    ]

    print("Running ZipVoice speech synthesis...")
    print(f"  Input text: '{text}'")
    print(f"  Model: {model_name}")
    print(f"  Output: {output_abs_path}")

    result = subprocess.run(command, cwd=str(ZIPVOICE_DIR), env=env, check=True)
    print(f"\n[+] Audio saved successfully to: {output_abs_path}")
    return str(output_abs_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DhVaani - Text to Speech using ZipVoice")
    parser.add_argument(
        "--text",
        type=str,
        default="Hello! This is generated using Python code and ZipVoice.",
        help="Text to synthesize",
    )
    parser.add_argument(
        "--prompt-wav",
        type=str,
        default=None,
        help="Path to prompt WAV file for voice cloning",
    )
    parser.add_argument(
        "--prompt-text",
        type=str,
        default="Hello and welcome.",
        help="Transcription of the prompt WAV file",
    )
    parser.add_argument(
        "--res-wav-path",
        type=str,
        default="output.wav",
        help="Path where output WAV should be saved",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        choices=["zipvoice", "zipvoice_distill"],
        default="zipvoice",
        help="ZipVoice model variant",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Speech speed factor (default: 1.0)",
    )
    parser.add_argument(
        "--num-step",
        type=int,
        default=8,
        help="Number of inference steps (default: 8)",
    )

    args = parser.parse_args()

    synthesize_speech(
        text=args.text,
        output_path=args.res_wav_path,
        prompt_wav=args.prompt_wav,
        prompt_text=args.prompt_text,
        model_name=args.model_name,
        speed=args.speed,
        num_step=args.num_step,
    )

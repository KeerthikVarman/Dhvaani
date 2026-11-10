"""
DhVaani - Interactive CLI Application for ZipVoice Text-to-Speech
"""

import os
import sys
from audio import synthesize_speech, ensure_default_prompt

def main():
    print("=" * 60)
    print("      DhVaani - ZipVoice Speech Synthesis Studio (CLI)      ")
    print("=" * 60)
    print("ZipVoice is a fast zero-shot text-to-speech model with flow matching.\n")

    # Prompt user for input text
    while True:
        try:
            text = input("Enter text to synthesize (or press Enter for default):\n> ").strip()
        except EOFError:
            text = ""
        if not text:
            text = "Hello! Welcome to DhVaani, powered by ZipVoice zero-shot speech synthesis."
            print(f"Using default text: '{text}'\n")
            break
        else:
            break

    # Voice selection
    print("\nVoice reference options:")
    print("1. Use default voice prompt")
    print("2. Specify custom reference WAV file for voice cloning")
    choice = input("Choice [1/2] (default 1): ").strip()

    prompt_wav = None
    prompt_text = "Hello and welcome."

    if choice == "2":
        custom_wav = input("Enter full path to your reference WAV file:\n> ").strip().strip('"')
        if os.path.isfile(custom_wav):
            prompt_wav = custom_wav
            p_text = input("Enter the words spoken in this audio (prompt transcription):\n> ").strip()
            if p_text:
                prompt_text = p_text
        else:
            print(f"File not found: '{custom_wav}'. Falling back to default voice.\n")

    # Model selection
    print("\nModel variants:")
    print("1. ZipVoice (Higher quality, default)")
    print("2. ZipVoice-Distill (Faster inference)")
    model_choice = input("Choice [1/2] (default 1): ").strip()
    model_name = "zipvoice_distill" if model_choice == "2" else "zipvoice"

    # Speed
    speed_input = input("Speed factor [0.5 - 2.0] (default 1.0): ").strip()
    try:
        speed = float(speed_input) if speed_input else 1.0
    except ValueError:
        speed = 1.0

    output_filename = input("Output file path (default: outputs/output.wav): ").strip()
    if not output_filename:
        output_filename = "outputs/output.wav"

    print("\nStarting generation...")
    try:
        output_path = synthesize_speech(
            text=text,
            output_path=output_filename,
            prompt_wav=prompt_wav,
            prompt_text=prompt_text,
            model_name=model_name,
            speed=speed,
        )
        print(f"\nSUCCESS! Audio generated at: {output_path}")
    except Exception as e:
        print(f"\nError during speech synthesis: {e}")

if __name__ == "__main__":
    main()


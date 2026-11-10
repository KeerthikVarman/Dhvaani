# DhVaani ⚡ ZipVoice TTS Studio

**DhVaani** is a dedicated Text-to-Speech (TTS) studio powered by **ZipVoice** (fast, high-quality zero-shot speech synthesis with flow matching).

---

## Features

- 📝 **Natural Text-to-Speech**: Type any text in English, Hindi (Devanagari or Hinglish), or Chinese and convert it into human speech.
- 🇮🇳 **Automatic Hindi Transliteration**: Devanagari script (e.g. `नमस्ते आप कैसे हैं`) is automatically converted into phonetic Latin for seamless ZipVoice synthesis.
- ⭐ **Instant Built-in Voice**: Works out-of-the-box with a clean harmonic reference speaker—no extra setup needed.
- 🎙️ **Zero-Shot Voice Cloning**: Optionally upload or record a 2–5 second WAV clip to clone any speaker's voice.
- ⚙️ **Fine-Tuning Controls**: Adjust speed (0.5x – 2.0x), sampling steps (4 – 20), and model variants (`zipvoice` / `zipvoice_distill`).
- 🔊 **Built-in Player**: Instant in-browser playback with 1-click WAV download.

---

## Step-by-Step Instructions to Run

### Step 1: Open Terminal in Project Directory
Make sure your terminal is inside `E:\DhVaani`:
```powershell
cd E:\DhVaani
```

### Step 2: Start the Web App

#### Option A (Easiest — 1-Click Batch File):
Double-click `run_app.bat` in File Explorer, or run:
```cmd
.\run_app.bat
```

#### Option B (Via PowerShell):
```powershell
.\venv\Scripts\python.exe web_app.py
```

### Step 3: Open in Browser
Open your browser and navigate to:
```
http://localhost:7860
```

### Step 4: Generate Speech
1. Enter your text into the **"Text to Speak"** box (or click one of the quick suggestions).
2. Leave **"Default Voice"** selected (or switch to Upload / Record if you want to clone a custom voice).
3. Click **"⚡ Synthesize Voice Audio"**.
4. Listen to the generated speech directly in the browser and download the `.wav` file!

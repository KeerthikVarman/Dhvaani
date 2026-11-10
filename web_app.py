"""
DhVaani - Dedicated Web Application for Text-to-Speech (TTS) using ZipVoice
"""

import base64
import http.server
import json
import math
import os
import re
import socketserver
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
ZIPVOICE_DIR = BASE_DIR / "ZipVoice"
OUTPUTS_DIR = BASE_DIR / "outputs"
UPLOADS_DIR = BASE_DIR / "uploads"
ASSETS_DIR = BASE_DIR / "assets"

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

PORT = 7860


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


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DhVaani | ZipVoice Text-to-Speech Studio</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: rgba(20, 27, 45, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --accent: #6366f1;
      --accent-glow: rgba(99, 102, 241, 0.35);
      --accent-hover: #4f46e5;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --success: #10b981;
      --error: #ef4444;
      --font-main: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background: radial-gradient(circle at top center, #1e1b4b 0%, var(--bg) 70%);
      color: var(--text);
      font-family: var(--font-main);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2.5rem 1rem 4rem;
    }

    .container {
      width: 100%;
      max-width: 860px;
    }

    header {
      text-align: center;
      margin-bottom: 2rem;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.35rem 0.85rem;
      background: rgba(99, 102, 241, 0.15);
      border: 1px solid rgba(99, 102, 241, 0.3);
      border-radius: 9999px;
      font-size: 0.8rem;
      font-weight: 600;
      color: #a5b4fc;
      margin-bottom: 1rem;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }

    h1 {
      font-size: 2.5rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      background: linear-gradient(135deg, #ffffff 40%, #a5b4fc 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 0.5rem;
    }

    header p {
      color: var(--text-muted);
      font-size: 1.05rem;
      max-width: 580px;
      margin: 0 auto;
    }

    .card {
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: 1.25rem;
      padding: 2rem;
      margin-bottom: 1.5rem;
      box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    }

    .card-title {
      font-size: 1.15rem;
      font-weight: 700;
      margin-bottom: 1rem;
      display: flex;
      align-items: center;
      gap: 0.6rem;
      color: #f1f5f9;
    }

    .form-group {
      margin-bottom: 1.25rem;
    }

    label {
      display: block;
      font-size: 0.88rem;
      font-weight: 600;
      margin-bottom: 0.5rem;
      color: #e2e8f0;
    }

    textarea, input[type="text"], select {
      width: 100%;
      background: rgba(11, 15, 25, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 0.75rem;
      padding: 0.85rem 1rem;
      color: white;
      font-family: inherit;
      font-size: 0.95rem;
      outline: none;
      transition: all 0.2s;
    }

    textarea:focus, input[type="text"]:focus, select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-glow);
    }

    textarea {
      min-height: 110px;
      resize: vertical;
      line-height: 1.5;
    }

    .quick-prompts {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-top: 0.65rem;
    }

    .quick-pill {
      font-size: 0.78rem;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.08);
      padding: 0.3rem 0.65rem;
      border-radius: 0.5rem;
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.2s;
    }

    .quick-pill:hover {
      background: rgba(99, 102, 241, 0.15);
      color: #c7d2fe;
      border-color: rgba(99, 102, 241, 0.3);
    }

    .tabs {
      display: flex;
      gap: 0.5rem;
      background: rgba(11, 15, 25, 0.6);
      padding: 0.35rem;
      border-radius: 0.75rem;
      margin-bottom: 1rem;
    }

    .tab-btn {
      flex: 1;
      padding: 0.6rem;
      background: transparent;
      border: none;
      border-radius: 0.5rem;
      color: var(--text-muted);
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }

    .tab-btn.active {
      background: var(--accent);
      color: white;
      box-shadow: 0 2px 8px var(--accent-glow);
    }

    .tab-content {
      display: none;
    }

    .tab-content.active {
      display: block;
    }

    .default-speaker-info {
      background: rgba(11, 15, 25, 0.4);
      padding: 1rem 1.25rem;
      border-radius: 0.75rem;
      border: 1px solid rgba(255, 255, 255, 0.05);
      font-size: 0.9rem;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .audio-recorder {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.85rem;
      padding: 1.25rem;
      border: 2px dashed rgba(255, 255, 255, 0.15);
      border-radius: 0.85rem;
      background: rgba(11, 15, 25, 0.4);
      text-align: center;
    }

    .record-btn {
      width: 54px;
      height: 54px;
      border-radius: 50%;
      background: #ef4444;
      border: none;
      color: white;
      font-size: 1.4rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
      box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);
    }

    .record-btn.recording {
      animation: pulse 1.2s infinite;
      background: #dc2626;
    }

    @keyframes pulse {
      0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
      70% { transform: scale(1.08); box-shadow: 0 0 0 14px rgba(239, 68, 68, 0); }
      100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
    }

    .settings-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
      margin-top: 1rem;
      margin-bottom: 1.5rem;
    }

    .range-wrap {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .range-wrap span {
      font-family: var(--font-mono);
      font-size: 0.85rem;
      min-width: 40px;
      text-align: right;
      color: #a5b4fc;
    }

    input[type="range"] {
      flex: 1;
      accent-color: var(--accent);
    }

    .primary-btn {
      width: 100%;
      background: linear-gradient(135deg, var(--accent) 0%, #4338ca 100%);
      color: white;
      border: none;
      padding: 1rem;
      border-radius: 0.85rem;
      font-size: 1.1rem;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.6rem;
      transition: all 0.2s;
      box-shadow: 0 6px 20px var(--accent-glow);
    }

    .primary-btn:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(99, 102, 241, 0.5);
    }

    .primary-btn:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    .spinner {
      border: 3px solid rgba(255, 255, 255, 0.2);
      border-top: 3px solid #ffffff;
      border-radius: 50%;
      width: 22px;
      height: 22px;
      animation: spin 0.8s linear infinite;
      display: none;
    }

    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }

    #result-box {
      display: none;
      margin-top: 1.5rem;
      border-top: 1px solid var(--card-border);
      padding-top: 1.5rem;
    }

    audio {
      width: 100%;
      margin: 1rem 0;
      border-radius: 0.5rem;
    }

    .audio-actions {
      display: flex;
      gap: 0.75rem;
    }

    .secondary-btn {
      flex: 1;
      padding: 0.75rem;
      border-radius: 0.65rem;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.12);
      color: white;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.4rem;
      transition: all 0.2s;
    }

    .secondary-btn:hover {
      background: rgba(255, 255, 255, 0.15);
    }

    .log-box {
      background: #050811;
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 0.75rem;
      padding: 1rem;
      margin-top: 1.5rem;
      font-family: var(--font-mono);
      font-size: 0.8rem;
      color: #94a3b8;
      max-height: 160px;
      overflow-y: auto;
      white-space: pre-wrap;
    }

    footer {
      text-align: center;
      margin-top: 2rem;
      font-size: 0.85rem;
      color: var(--text-muted);
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="badge">✨ DhVaani AI Studio</div>
      <h1>ZipVoice Speech Studio</h1>
      <p>Clean, fast Text-to-Speech (TTS) with zero-shot voice cloning.</p>
    </header>

    <div class="card">
      <div class="card-title">📝 1. Text to Speak</div>
      <div class="form-group">
        <label for="text-input">Enter text to convert to natural human speech (English, Hindi, or Chinese):</label>
        <textarea id="text-input" placeholder="Type text here in English, Hindi (नमस्ते or Namaste), or Chinese...">नमस्ते! ध्वाणि में आपका स्वागत है।</textarea>
        <div class="quick-prompts">
          <span style="font-size: 0.78rem; color: var(--text-muted); align-self: center;">Quick suggestions:</span>
          <div class="quick-pill" onclick="setText('नमस्ते! ध्वाणि में आपका स्वागत है।')">🇮🇳 Hindi (Devanagari)</div>
          <div class="quick-pill" onclick="setText('Namaste! DhVaani me aapka swaagat hai, kaise hain aap?')">🇮🇳 Hindi (Hinglish)</div>
          <div class="quick-pill" onclick="setText('Welcome to DhVaani, an intelligent voice and speech generation workspace.')">🇬🇧 English Welcome</div>
          <div class="quick-pill" onclick="setText('ZipVoice is a fast and high-quality zero-shot text-to-speech model.')">⚡ ZipVoice Overview</div>
        </div>
      </div>

      <div class="card-title" style="margin-top: 2rem;">🎙️ 2. Speaker Voice (Voice Cloning)</div>
      
      <div class="tabs">
        <button id="btn-tab-default" class="tab-btn active" onclick="switchTab('default')">⭐ Default Voice</button>
        <button id="btn-tab-upload" class="tab-btn" onclick="switchTab('upload')">📁 Upload WAV</button>
        <button id="btn-tab-mic" class="tab-btn" onclick="switchTab('mic')">🔴 Record Mic</button>
      </div>

      <div id="tab-default" class="tab-content active">
        <div class="default-speaker-info">
          <span style="font-size: 1.25rem;">✨</span>
          <div>
            <strong>Built-in Clean Reference Voice</strong>
            <p style="font-size: 0.82rem; margin-top: 2px;">Using standard speaker prompt from DhVaani assets. No upload required.</p>
          </div>
        </div>
      </div>

      <div id="tab-upload" class="tab-content">
        <div class="form-group">
          <label>Select a short WAV reference audio file (1-5 seconds):</label>
          <input type="file" id="prompt-file-input" accept=".wav,audio/wav" onchange="handleFileSelect(event)">
        </div>
      </div>

      <div id="tab-mic" class="tab-content">
        <div class="audio-recorder">
          <button id="record-btn" class="record-btn" onclick="toggleRecording()" title="Record voice">🎙️</button>
          <div id="record-status" style="font-size: 0.9rem; color: var(--text-muted);">
            Click the red button to record 2 to 5 seconds of speaking
          </div>
          <audio id="recorded-preview" controls style="display: none;"></audio>
        </div>
      </div>

      <div class="form-group" style="margin-top: 1.25rem;">
        <label for="prompt-text-input">Prompt Transcription (optional):</label>
        <input type="text" id="prompt-text-input" placeholder="Words spoken in reference voice audio (default: 'Hello and welcome.')" value="Hello and welcome.">
      </div>

      <div class="card-title" style="margin-top: 2rem;">⚙️ 3. Settings</div>
      <div class="settings-grid">
        <div class="form-group">
          <label for="model-select">Model Variant:</label>
          <select id="model-select">
            <option value="zipvoice" selected>ZipVoice (Higher Quality)</option>
            <option value="zipvoice_distill">ZipVoice-Distill (Faster Speed)</option>
          </select>
        </div>

        <div class="form-group">
          <label for="speed-slider">Speed:</label>
          <div class="range-wrap">
            <input type="range" id="speed-slider" min="0.5" max="2.0" step="0.1" value="1.0" oninput="document.getElementById('speed-val').innerText = this.value + 'x'">
            <span id="speed-val">1.0x</span>
          </div>
        </div>

        <div class="form-group">
          <label for="steps-slider">Sampling Steps:</label>
          <div class="range-wrap">
            <input type="range" id="steps-slider" min="4" max="20" step="2" value="8" oninput="document.getElementById('steps-val').innerText = this.value">
            <span id="steps-val">8</span>
          </div>
        </div>
      </div>

      <button id="generate-btn" class="primary-btn" onclick="generateSpeech()">
        <span class="spinner" id="spinner"></span>
        <span id="btn-text">⚡ Synthesize Voice Audio</span>
      </button>

      <div id="result-box">
        <div class="card-title" style="color: var(--success); font-size: 1.15rem;">🎉 Audio Generated Successfully!</div>
        <div id="hindi-notice" style="display:none; background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 0.6rem; padding: 0.65rem 0.9rem; font-size: 0.85rem; color: #c7d2fe; margin-bottom: 0.75rem;"></div>
        <audio id="output-audio" controls></audio>
        <div class="audio-actions">
          <a id="download-link" class="secondary-btn" download="generated_speech.wav">⬇️ Download WAV</a>
          <button class="secondary-btn" onclick="playAudioAgain()">🔁 Replay</button>
        </div>
      </div>

      <div class="log-box" id="log-box" style="display:none;"></div>
    </div>

    <footer>
      DhVaani TTS &bull; Powered by ZipVoice (k2-fsa) Flow Matching Model
    </footer>
  </div>

  <script>
    let mediaRecorder = null;
    let audioChunks = [];
    let recordedAudioBase64 = null;
    let activeTab = 'default';

    function setText(text) {
      document.getElementById('text-input').value = text;
    }

    function switchTab(tab) {
      activeTab = tab;
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

      document.getElementById('btn-tab-' + tab).classList.add('active');
      document.getElementById('tab-' + tab).classList.add('active');
    }

    async function toggleRecording() {
      const recordBtn = document.getElementById('record-btn');
      const recordStatus = document.getElementById('record-status');

      if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        recordBtn.classList.remove('recording');
        recordStatus.innerText = 'Recording saved!';
        return;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = e => {
          if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
          const blob = new Blob(audioChunks, { type: 'audio/wav' });
          const preview = document.getElementById('recorded-preview');
          preview.src = URL.createObjectURL(blob);
          preview.style.display = 'block';

          const reader = new FileReader();
          reader.readAsDataURL(blob);
          reader.onloadend = () => {
            recordedAudioBase64 = reader.result;
          };
          stream.getTracks().forEach(t => t.stop());
        };

        mediaRecorder.start();
        recordBtn.classList.add('recording');
        recordStatus.innerText = 'Recording... Speak now (3-5 seconds), then click again to finish';
      } catch (err) {
        console.error('Mic access error:', err);
        alert('Could not access microphone: ' + err.message);
      }
    }

    function handleFileSelect(event) {
      const file = event.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onloadend = () => {
        recordedAudioBase64 = reader.result;
      };
    }

    function playAudioAgain() {
      const audio = document.getElementById('output-audio');
      audio.currentTime = 0;
      audio.play();
    }

    async function generateSpeech() {
      const text = document.getElementById('text-input').value.trim();
      if (!text) {
        alert('Please enter text to synthesize.');
        return;
      }

      const promptText = document.getElementById('prompt-text-input').value.trim();
      const modelName = document.getElementById('model-select').value;
      const speed = parseFloat(document.getElementById('speed-slider').value);
      const numSteps = parseInt(document.getElementById('steps-slider').value);

      const generateBtn = document.getElementById('generate-btn');
      const spinner = document.getElementById('spinner');
      const btnText = document.getElementById('btn-text');
      const resultBox = document.getElementById('result-box');
      const logBox = document.getElementById('log-box');

      generateBtn.disabled = true;
      spinner.style.display = 'inline-block';
      btnText.innerText = 'Synthesizing with ZipVoice... (Please wait)';
      logBox.style.display = 'block';
      logBox.innerText = 'Starting inference request...';

      const payload = {
        text: text,
        prompt_text: promptText,
        prompt_audio: (activeTab === 'default') ? null : recordedAudioBase64,
        source_mode: activeTab,
        model_name: modelName,
        speed: speed,
        num_step: numSteps
      };

      try {
        const response = await fetch('/api/synthesize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (data.status === 'success') {
          resultBox.style.display = 'block';
          const hindiNotice = document.getElementById('hindi-notice');
          if (data.transliterated) {
            hindiNotice.innerText = '💡 Hindi (Devanagari) automatically converted to phonetic Latin: "' + data.transliterated + '"';
            hindiNotice.style.display = 'block';
          } else {
            hindiNotice.style.display = 'none';
          }

          const audio = document.getElementById('output-audio');
          audio.src = data.audio_url + '?t=' + new Date().getTime();
          audio.load();
          audio.play().catch(e => console.log('Autoplay blocked:', e));

          const downloadLink = document.getElementById('download-link');
          downloadLink.href = data.audio_url;

          logBox.innerText = 'Generation complete! Audio file: ' + data.audio_url;
        } else {
          alert('Error during synthesis: ' + (data.message || 'Unknown error'));
          logBox.innerText = 'Error:\\n' + (data.log || data.message);
        }
      } catch (err) {
        console.error('Synthesis failed:', err);
        alert('Request failed: ' + err.message);
        logBox.innerText = 'Request error: ' + err.message;
      } finally {
        generateBtn.disabled = false;
        spinner.style.display = 'none';
        btnText.innerText = '⚡ Synthesize Voice Audio';
      }
    }
  </script>
</body>
</html>
"""


class StudioHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        path = url.path

        if path in ("", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(HTML_PAGE.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        if path.startswith("/outputs/"):
            filename = os.path.basename(path)
            file_path = OUTPUTS_DIR / filename
            if file_path.is_file():
                self.serve_audio(file_path)
                return

        if path.startswith("/assets/"):
            filename = os.path.basename(path)
            file_path = ASSETS_DIR / filename
            if file_path.is_file():
                self.serve_audio(file_path)
                return

        if path == "/api/status":
            self.send_json({
                "status": "ready",
                "zipvoice_dir": str(ZIPVOICE_DIR),
                "python_executable": get_python_executable()
            })
            return

        super().do_GET()

    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/api/synthesize":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                self.handle_synthesize(data)
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, status=500)
            return

        self.send_error(404, "Endpoint not found")

    def serve_audio(self, file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, data, status=200):
        response_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def handle_synthesize(self, data):
        text = data.get("text", "").strip()
        prompt_text = data.get("prompt_text", "").strip() or "Hello and welcome."
        prompt_audio_b64 = data.get("prompt_audio")
        source_mode = data.get("source_mode", "default")
        model_name = data.get("model_name", "zipvoice")
        speed = float(data.get("speed", 1.0))
        num_step = int(data.get("num_step", 8))

        # Automatic Devanagari Hindi transliteration to phonetic Latin
        raw_text = text
        text = devanagari_to_roman(text)
        prompt_text = devanagari_to_roman(prompt_text)
        is_hindi_transliterated = (text != raw_text)

        timestamp = int(time.time())
        prompt_path = None

        if source_mode != "default" and prompt_audio_b64:
            if "," in prompt_audio_b64:
                prompt_audio_b64 = prompt_audio_b64.split(",", 1)[1]
            raw_audio = base64.b64decode(prompt_audio_b64)
            prompt_path = UPLOADS_DIR / f"prompt_{timestamp}.wav"
            with open(prompt_path, "wb") as f:
                f.write(raw_audio)
        else:
            default_candidates = [
                ASSETS_DIR / "default_prompt.wav",
                ASSETS_DIR / "sample_prompt.wav"
            ]
            for candidate in default_candidates:
                if candidate.is_file():
                    prompt_path = candidate
                    break

            if not prompt_path:
                prompt_path = ASSETS_DIR / "default_prompt.wav"
                self.create_clean_prompt_wav(prompt_path)

        output_filename = f"speech_{timestamp}.wav"
        output_path = OUTPUTS_DIR / output_filename

        env = os.environ.copy()
        pythonpath = str(ZIPVOICE_DIR)
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{pythonpath};{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = pythonpath

        cmd = [
            get_python_executable(),
            "-m",
            "zipvoice.bin.infer_zipvoice",
            "--model-name",
            model_name,
            "--prompt-wav",
            str(prompt_path),
            "--prompt-text",
            prompt_text,
            "--text",
            text,
            "--res-wav-path",
            str(output_path),
            "--speed",
            str(speed),
            "--num-step",
            str(num_step),
        ]

        print(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=str(ZIPVOICE_DIR),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        log_output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        print(log_output)

        if result.returncode != 0 or not output_path.is_file():
            self.send_json({
                "status": "error",
                "message": f"Inference failed with exit code {result.returncode}",
                "log": log_output
            }, status=500)
            return

        self.send_json({
          "status": "success",
          "audio_url": f"/outputs/{output_filename}",
          "filename": output_filename,
          "transliterated": text if is_hindi_transliterated else None,
          "log": log_output
        })

    def create_clean_prompt_wav(self, target_path):
        """Creates a simple standard WAV file as fallback prompt"""
        sample_rate = 24000
        duration = 2.0
        num_samples = int(sample_rate * duration)

        with wave.open(str(target_path), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)

            values = []
            for i in range(num_samples):
                t = i / sample_rate
                sample = (
                    0.5 * math.sin(2 * math.pi * 220 * t) +
                    0.3 * math.sin(2 * math.pi * 440 * t) +
                    0.15 * math.sin(2 * math.pi * 660 * t)
                ) * math.exp(-0.5 * (t - 1.0) ** 2)
                val = int(sample * 16384.0)
                values.append(struct.pack("<h", max(-32768, min(32767, val))))

            wav_file.writeframes(b"".join(values))


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def run_server(port=PORT):
    server_address = ("", port)
    py_exec = get_python_executable()
    try:
        with ReusableTCPServer(server_address, StudioHandler) as httpd:
            print("=" * 60)
            print(" DhVaani TTS Studio (ZipVoice) is running!")
            print(f" Access in your browser: http://localhost:{port}")
            print(f" Python backend: {py_exec}")
            print(" Press Ctrl+C to stop the server.")
            print("=" * 60)
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")
    except OSError as e:
        print(f"\n[ERROR] Could not start server on port {port}: {e}")
        print(f"Tip: If port {port} is already in use, run: python web_app.py {port + 1}")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run_server(port)

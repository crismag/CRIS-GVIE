# CRIS-GVIE

**Cognitive Reasoning Intelligent Speech — General Voice Interaction Engine**

CRIS-GVIE is a minimal, local-first voice interaction runtime MVP.
It demonstrates a clean and extensible architecture for a standalone voice loop:

1. Record microphone input
2. Transcribe locally
3. Send transcript to local Ollama
4. Generate AI response
5. Convert response to speech with local Piper
6. Play audio response
7. Persist transcript/session history

> This project is intentionally **not** a chatbot platform and does not include cloud infrastructure.

---

## MVP Architecture

`gvie/runtime.py` orchestrates replaceable providers:

- `gvie/recorder.py` — microphone recording (`sounddevice` + WAV output)
- `gvie/stt.py` — local speech-to-text (`faster-whisper`)
- `gvie/llm.py` — local Ollama REST client
- `gvie/tts.py` — Piper synthesis + local playback
- `gvie/session.py` — JSONL transcript persistence
- `gvie/models.py` — transcript entry schema
- `gvie/config.py` — runtime configuration models

Session format:

```text
sessions/
  session_<timestamp>/
    transcript.jsonl
    metadata.json
```

Transcript entries:

```json
{
  "timestamp": "...",
  "speaker": "user",
  "text": "..."
}
```

---

## Repository Structure

```text
cris-gvie/
├── README.md
├── requirements.txt
├── .gitignore
├── examples/
│   └── local_interviewer.py
├── gvie/
│   ├── __init__.py
│   ├── runtime.py
│   ├── recorder.py
│   ├── stt.py
│   ├── llm.py
│   ├── tts.py
│   ├── session.py
│   ├── models.py
│   └── config.py
├── sessions/
└── docs/
```

---

## Requirements

- Python 3.11+
- Local Ollama installation
- Local Piper installation
- Microphone + speakers

Install Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Ollama Setup

Install Ollama and pull the default model:

```bash
ollama pull qwen2.5:14b
```

Ensure Ollama is running locally (default: `http://localhost:11434`).

---

## Piper Setup

Install Piper and download a voice model (example):

- `en_US-lessac-medium.onnx`
- matching config JSON if required by your Piper distribution

By default, CRIS-GVIE expects `en_US-lessac-medium.onnx` to be available locally.
You can update paths in `gvie/config.py`.

---

## Run MVP

```bash
python examples/local_interviewer.py
```

Runtime flow:

- Press Enter to start recording
- Speak
- Press Enter to stop
- Runtime transcribes, sends text to Ollama, speaks response, and saves transcript
- Repeat loop

Quit with `q` at the prompt.

---

## Limitations (MVP)

- Single-user local CLI runtime only
- No web UI
- No cloud deployment
- No advanced memory/RAG/vector DB
- No orchestration/distributed components
- Error handling remains lightweight for demonstrability

---

## Future Roadmap

- Provider swapping (STT/TTS/LLM) via config
- Better device selection for audio input/output
- Optional SQLite storage backend
- Push-to-talk controls
- More robust runtime diagnostics and retries


# CRIS-GVIE

**Cognitive Reasoning Intelligent Speech — General Voice Interaction Engine**

CRIS-GVIE is a minimal, local-first voice interaction runtime with automatic Voice Activity Detection (VAD).
It listens continuously, detects when you speak, transcribes, generates an AI response, and plays it back — no key presses required.

1. Automatic speech detection via silero-vad
2. Transcribe locally with faster-whisper
3. Generate response with local Ollama
4. Synthesize speech with local Piper
5. Play audio response
6. Persist transcript and audio references per turn
7. Return to listening state

> This project is intentionally **not** a chatbot platform and does not include cloud infrastructure.

---

## Runtime Flow

```text
[LISTENING]
→ user speaks → [SPEECH_STARTED] → [RECORDING]
→ silence detected → [SILENCE_DETECTED] → [TURN_COMPLETED]
→ [TRANSCRIBING] → [GENERATING_RESPONSE] → [SPEAKING]
→ [LISTENING]
```

---

## Architecture

`gvie/runtime.py` orchestrates replaceable providers:

| Module | Responsibility |
|---|---|
| `gvie/vad.py` | silero-vad speech probability classifier |
| `gvie/audio_stream.py` | continuous non-blocking microphone capture |
| `gvie/turn_manager.py` | LISTENING → RECORDING → TURN_COMPLETED state machine |
| `gvie/silence_detector.py` | configurable silence timeout detection |
| `gvie/stream_buffer.py` | thread-safe rolling audio buffer + WAV export |
| `gvie/audio_events.py` | `AudioEventType` enum and event payloads |
| `gvie/stt.py` | local speech-to-text (`faster-whisper`) |
| `gvie/llm.py` | local Ollama REST client |
| `gvie/tts.py` | Piper synthesis + local playback |
| `gvie/session.py` | JSONL transcript persistence |
| `gvie/models.py` | transcript and turn entry schemas |
| `gvie/config.py` | runtime configuration models |

Session format:

```text
sessions/
  session_<timestamp>/
    transcript.jsonl
    metadata.json
    turn_001.wav
    turn_002.wav
    ...
```

Turn records in `transcript.jsonl`:

```json
{"turn_id": 1, "speaker": "user", "audio_file": "turn_001.wav", "text": "hello", "started_at": "...", "ended_at": "..."}
{"turn_id": 1, "speaker": "assistant", "audio_file": null, "text": "Hi there!", "started_at": "...", "ended_at": "..."}
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
│   ├── vad.py
│   ├── audio_stream.py
│   ├── turn_manager.py
│   ├── silence_detector.py
│   ├── stream_buffer.py
│   ├── audio_events.py
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

> **Note:** `silero-vad` installs PyTorch as a transitive dependency.
> First run downloads the VAD model weights (~2 MB) automatically.

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

## Run

```bash
python examples/local_interviewer.py
```

The runtime starts listening immediately.  Speak naturally and pause for ~1.5 seconds to end your turn.  Press **Ctrl-C** to exit.

---

## Configuration

All tuneable parameters live in `gvie/config.py`:

| Setting | Default | Description |
|---|---|---|
| `VADConfig.threshold` | `0.5` | Speech probability threshold (0–1) |
| `VADConfig.silence_timeout` | `1.5` | Seconds of silence before turn ends |
| `VADConfig.chunk_size` | `512` | Audio frames per VAD call (256 or 512) |
| `VADConfig.max_recording_duration` | `60.0` | Hard recording limit per turn (seconds) |
| `AudioConfig.sample_rate` | `16000` | Microphone sample rate |
| `STTConfig.model_size` | `small` | faster-whisper model size |
| `OllamaConfig.model` | `qwen2.5:14b` | Ollama model name |

Example customisation:

```python
from gvie import RuntimeConfig, VADConfig, VoiceRuntime

config = RuntimeConfig(
    vad=VADConfig(threshold=0.4, silence_timeout=2.0),
)
VoiceRuntime(config=config).run()
```

---

## Limitations

- Single-user local CLI runtime only
- No web UI
- No cloud deployment
- No advanced memory/RAG/vector DB
- No wake word detection
- No full-duplex / interruption support (foundation is in place)

---

## Future Roadmap

- Streaming STT and TTS for lower latency
- Interruption handling (foundation already wired via `AudioEventType`)
- Provider swapping (STT/TTS/LLM) via config
- Optional SQLite storage backend
- Web interface


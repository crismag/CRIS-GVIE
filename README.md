# CRIS-GVIE

**Cognitive Reasoning Intelligent Speech — General Voice Interaction Engine**

CRIS-GVIE is a minimal, local-first conversational voice runtime with automatic Voice Activity Detection (VAD).
It listens continuously, detects when you speak, streams partial transcripts live, routes turns through a plugin, generates a response, and plays it back — no key presses required.

1. Automatic speech detection via silero-vad
2. Stream transcription locally with faster-whisper
3. Emit partial transcript updates in real time
4. Route finalized turns through a plugin
5. Generate response with local Ollama or plugin logic
6. Synthesize speech with local Piper
7. Persist transcript, events, and turn records
8. Return to listening state

> This project is intentionally **not** a chatbot platform and does not include cloud infrastructure.

---

## Runtime Flow

```text
[LISTENING]
→ user speaks → [SPEECH_STARTED] → [STREAMING]
→ partial transcript updates
→ silence detected → [FINAL_TRANSCRIPT]
→ plugin processes turn → [RESPONSE_GENERATED]
→ [SPEAKING]
→ [LISTENING]
```

---

## Architecture

`gvie/runtime/workflow_runtime.py` orchestrates the plugin-driven runtime:

| Module | Responsibility |
|---|---|
| `gvie/vad.py` | silero-vad speech probability classifier |
| `gvie/audio_stream.py` | continuous non-blocking microphone capture |
| `gvie/runtime/` | runtime orchestration, state, and event routing |
| `gvie/streaming_stt.py` | rolling-buffer streaming transcription |
| `gvie/transcript_stream.py` | live transcript event emission and ordering |
| `gvie/transcript_state.py` | partial/final transcript state |
| `gvie/incremental_decoder.py` | transcript merge helpers |
| `gvie/partial_result_manager.py` | partial confidence and stability heuristics |
| `gvie/events/` | transcript, audio, and runtime event types |
| `gvie/turn_manager.py` | legacy LISTENING → RECORDING → TURN_COMPLETED state machine |
| `gvie/silence_detector.py` | configurable silence timeout detection |
| `gvie/stream_buffer.py` | thread-safe rolling audio buffer + WAV export |
| `gvie/plugins/` | plugin contract, registry, and shared context models |
| `gvie/adapters/` | convenience runtime builders for adopter workflows |
| `gvie/examples/` | simple chat and interviewer plugin examples |
| `gvie/stt.py` | local speech-to-text (`faster-whisper`) |
| `gvie/llm.py` | local Ollama REST client |
| `gvie/tts.py` | Piper synthesis + local playback |
| `gvie/session.py` | JSONL transcript and event persistence |
| `gvie/models.py` | transcript and turn entry schemas |
| `gvie/config.py` | runtime configuration models |

Session format:

```text
sessions/
  session_<timestamp>/
    transcript.jsonl
    events.jsonl
    metadata.json
    turn_001.wav
    turn_002.wav
    ...
```

Turn records in `transcript.jsonl`:

```json
{"turn_id": 1, "speaker": "user", "plugin": "interviewer", "audio_file": "turn_001.wav", "text": "hello", "started_at": "...", "ended_at": "...", "partial_history": ["he", "hello"]}
{"turn_id": 1, "speaker": "assistant", "plugin": "interviewer", "audio_file": null, "text": "Hi there!", "started_at": "...", "ended_at": "..."}
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
│   ├── stream_runtime.py
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── event_router.py
│   │   ├── orchestrator.py
│   │   ├── runtime_state.py
│   │   └── workflow_runtime.py
│   ├── plugins/
│   │   ├── base.py
│   │   ├── context.py
│   │   ├── loader.py
│   │   └── registry.py
│   ├── events/
│   │   ├── audio_events.py
│   │   ├── conversation_events.py
│   │   └── transcript_events.py
│   ├── adapters/
│   │   ├── interviewer_adapter.py
│   │   └── local_chat_adapter.py
│   ├── examples/
│   │   ├── interviewer_plugin.py
│   │   └── simple_chat_plugin.py
│   ├── vad.py
│   ├── audio_stream.py
│   ├── streaming_stt.py
│   ├── transcript_stream.py
│   ├── transcript_state.py
│   ├── transcript_events.py
│   ├── incremental_decoder.py
│   ├── partial_result_manager.py
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

The example starts the interviewer workflow immediately. Speak naturally and pause for ~1.5 seconds to finalize your turn. Press **Ctrl-C** to exit.

---

## Configuration

All tuneable parameters live in `gvie/config.py`:

| Setting | Default | Description |
|---|---|---|
| `RuntimeConfig.active_plugin` | `simple_chat` | Default active plugin name |
| `RuntimeConfig.default_ollama_model` | `qwen2.5:14b` | Default Ollama model for plugins |
| `RuntimeConfig.enable_streaming_transcript` | `True` | Enable live transcript updates |
| `RuntimeConfig.enable_tts` | `True` | Enable speech playback |
| `RuntimeConfig.session_storage_path` | `sessions` | Session storage directory |
| `VADConfig.threshold` | `0.5` | Speech probability threshold (0–1) |
| `VADConfig.silence_timeout` | `1.5` | Seconds of silence before turn ends |
| `VADConfig.chunk_size` | `512` | Audio frames per VAD call (256 or 512) |
| `VADConfig.max_recording_duration` | `60.0` | Hard recording limit per turn (seconds) |
| `AudioConfig.sample_rate` | `16000` | Microphone sample rate |
| `STTConfig.model_size` | `small` | faster-whisper model size |
| `STTConfig.compute_type` | `int8` | faster-whisper compute type |
| `StreamingSTT.partial_update_interval_ms` | `250` | Partial transcript cadence |
| `StreamingSTT.max_stream_buffer_seconds` | `30.0` | Rolling STT buffer limit |
| `OllamaConfig.model` | `qwen2.5:14b` | Ollama model name |

Example customisation:

```python
from gvie import RuntimeConfig, VADConfig
from gvie.adapters import create_interviewer_runtime

config = RuntimeConfig(vad=VADConfig(threshold=0.4, silence_timeout=2.0))
create_interviewer_runtime(config).run()
```

---

## Limitations

- Single-user local CLI runtime only
- No web UI
- No cloud deployment
- No advanced memory/RAG/vector DB
- No wake word detection
- No multi-plugin orchestration yet
- No full-duplex / interruption support (foundation is in place)

---

## Future Roadmap

- Streaming STT and TTS for lower latency
- Plugin routing beyond one active plugin
- Interruption handling (foundation already wired via runtime events)
- Provider swapping (STT/TTS/LLM) via config
- Optional SQLite storage backend
- Web interface

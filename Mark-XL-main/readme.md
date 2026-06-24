# 🌌 ANDROMEDA — Sovereign Enterprise Autopilot

> **Sovereign Node Orchestration** — A cross-platform, local-first AI assistant with enterprise-grade orchestration capabilities and a deep-space telemetry HUD.

---

## Overview

ANDROMEDA is a fully local, real-time voice and visual AI agent designed for privacy, speed, and autonomous task execution. It removes cloud dependencies by leveraging locally hosted LLMs (via Ollama or OpenAI-compatible APIs), offline speech recognition, and high-fidelity text-to-speech.

The system features a custom-built **Galaxy Engine HUD**, providing real-time system telemetry and a secure zero-trust sandbox for file processing.

---

## Architecture

```
Microphone → Acoustic Sensor (Whisper / Vosk)
                        ↓
           Cognitive Engine (Ollama / OpenAI API)
                        ↓
         Tool Orchestration (OS, Browser, Files, RPA)
                        ↓
           Voice Synthesis (EdgeTTS / Kokoro / ElevenLabs)
                        ↓
                    Speaker
```

### Core Components

| Layer | Technology | Notes |
|-------|-----------|-------|
| **STT** | faster-whisper / Vosk | Fully offline. Multi-language support with auto-detection. |
| **LLM** | Ollama / OpenAI-compatible | Supports Qwen, Llama, Mistral, etc. with streaming & tool calling. |
| **TTS** | EdgeTTS / Kokoro / ElevenLabs | Kokoro offers high-quality, fully offline synthesis. |
| **UI** | PyQt6 (Galaxy Engine) | Deep-space HUD with live telemetry, log panel, and secure dropzone. |
| **Agent** | Autonomous Task Queue | Multi-step planning, error recovery, and long-term memory. |

---

## Key Features

- **Galaxy Engine HUD** — A dynamic, high-performance UI with starfield animations and neural constellation maps.
- **Live Telemetry** — Real-time monitoring of CPU, Memory, Network, GPU, and Temperature.
- **Zero-Trust Sandbox** — Secure file dropzone for processing images, PDFs, CSVs, and more without data leaks.
- **Streaming Orchestration** — Voice synthesis begins at the first generated sentence for near-zero latency.
- **Autonomous Tool Calling** — 20 built-in tools for browser automation, file management, system control, and dev ops.
- **Long-Term Memory** — Automatically captures and recalls personal context across sessions.
- **Dynamic Reconfiguration** — Change engines, models, and voices on-the-fly via the ⚙ CONFIGURE panel.
- **Ollama Integration** — Auto-starts the Ollama server and warms up models for peak performance.

---

## Requirements

- Python 3.11 or 3.12
- [Ollama](https://ollama.com) (recommended) or an OpenAI-compatible local server.
- Hardware: Microphone and speakers.

---

## Quick Start

```bash
# 1. Install Ollama → https://ollama.com
#    Then pull the recommended model:
ollama pull qwen2.5:7b

# 2. Clone the repository and launch
cd Mark-XL-main
python main.py
```

### Initialisation Sequence
1. **Auto-Bootstrap**: On first run, Andromeda installs core UI packages and restarts.
2. **Initialization Overlay**: Select your STT, LLM, and TTS engines.
3. **Engine Setup**: Andromeda downloads necessary model weights (Whisper/Vosk/Kokoro) in the background.
4. **Systems Online**: The HUD activates, and the autopilot becomes ready for commands.

---

## Configuration (`config/api_keys.json`)

```json
{
    "stt_engine": "whisper",
    "stt_model": "base",
    "stt_language": "auto",
    "llm_provider": "ollama",
    "llm_url": "http://localhost:11434",
    "llm_model": "qwen2.5:7b",
    "tts_engine": "edgetts",
    "tts_voice": "en-US-GuyNeural",
    "tts_speed": "1.0",
    "elevenlabs_api_key": ""
}
```

| Key | Description | Default / Options |
|-----|-------------|-------------------|
| `stt_engine` | Speech recognition engine | `whisper`, `vosk` |
| `stt_model` | Model size/path | `tiny` to `large-v3` (Whisper) or local path (Vosk) |
| `llm_provider`| LLM backend | `ollama`, `openai` (for LM Studio / LocalAI) |
| `tts_engine` | Voice synthesis engine | `edgetts`, `kokoro`, `elevenlabs` |
| `tts_voice` | Selected voice profile | Varies by engine (e.g., `af_heart` for Kokoro) |

---

## Built-in Tools

| Tool | Capability |
|------|------------|
| `open_app` | Launches applications and URLs |
| `web_search` | Search and comparison mode via DuckDuckGo |
| `browser_control` | Full Playwright automation (click, type, scrape) |
| `file_controller` | Advanced file/folder CRUD and disk telemetry |
| `file_processor` | Secure processing of dropped files (Resize, Trim, Filter) |
| `code_helper` | Write, run, and explain code in the sandbox |
| `dev_agent` | Build complete multi-file projects from scratch |
| `agent_task` | Multi-step autonomous goal execution |
| `computer_control` | Mouse/Keyboard control and element detection |
| `screen_process` | Vision-based screen and webcam analysis |
| `youtube_video` | Playback, summarization, and trending analytics |
| `send_message` | WhatsApp and Telegram orchestration |
| `game_updater` | Steam and Epic Games management |
| `flight_finder` | Real-time Google Flights search |
| `reminder` | OS-level task scheduling |
| `weather_report` | Global weather telemetry |
| `desktop_control` | Wallpaper and desktop organization |
| `computer_settings`| System volume, brightness, and power management |
| `save_memory` | Permanent fact storage |
| `shutdown_jarvis` | Terminates the autopilot sequence and shuts down the assistant |

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `F4` | Mute / Unmute Acoustic Sensor |
| `F11` | Toggle Fullscreen Mode |

---

## License

MIT — FatihMakes Industries / Meteor Group

# 🌌 ANDROMEDA — Sovereign Enterprise Autopilot

[English](#english) | [Bahasa Melayu](#bahasa-melayu)

---

<a name="english"></a>
## 🇬🇧 English

> **Sovereign Node Orchestration** — A cross-platform, local-first AI assistant with enterprise-grade orchestration capabilities and a deep-space telemetry HUD.

### Overview
ANDROMEDA is a fully local, real-time voice and visual AI agent designed for privacy, speed, and autonomous task execution. It removes cloud dependencies by leveraging locally hosted LLMs (via Ollama or OpenAI-compatible APIs), offline speech recognition, and high-fidelity text-to-speech.

### Key Features
- **Galaxy Engine HUD** — A dynamic UI with starfield animations and neural constellation maps.
- **Live Telemetry** — Real-time monitoring of CPU, Memory, Network, GPU, and Temperature.
- **Zero-Trust Sandbox** — Secure file dropzone for processing images, PDFs, CSVs, and more.
- **Streaming Orchestration** — Voice synthesis begins at the first generated sentence.
- **Autonomous Tool Calling** — 20 built-in tools for browser automation, file management, and system control.

### Quick Start
```bash
# 1. Install Ollama and pull model
ollama pull qwen2.5:7b

# 2. Launch
cd Mark-XL-main
python main.py
```

---

<a name="bahasa-melayu"></a>
## 🇲🇾 Bahasa Melayu

> **Orkestrasi Nod Berdaulat** — Pembantu AI tempatan silang-platform dengan keupayaan orkestrasi gred perusahaan dan HUD telemetri angkasa lepas.

### Ringkasan
ANDROMEDA ialah ejen AI suara dan visual masa nyata tempatan sepenuhnya yang direka untuk privasi, kelajuan, dan pelaksanaan tugas autonomi. Ia menghapuskan kebergantungan awan dengan menggunakan LLM hos tempatan (melalui Ollama atau API serasi OpenAI), pengecaman pertuturan luar talian, dan sintesis teks-ke-suara kesetiaan tinggi.

### Ciri-ciri Utama
- **HUD Galaxy Engine** — Antara muka dinamik dengan animasi medan bintang dan peta buruj neural.
- **Telemetri Langsung** — Pemantauan masa nyata untuk CPU, Memori, Rangkaian, GPU, dan Suhu.
- **Sandbox Zero-Trust** — Zon drop fail selamat untuk memproses imej, PDF, CSV, dan lain-lain.
- **Orkestrasi Penstriman** — Sintesis suara bermula pada ayat pertama yang dijana.
- **Panggilan Alatan Autonomi** — 20 alatan terbina untuk automasi pelayar, pengurusan fail, dan kawalan sistem.

### Permulaan Pantas
```bash
# 1. Pasang Ollama dan muat turun model
ollama pull qwen2.5:7b

# 2. Lancarkan
cd Mark-XL-main
python main.py
```

---

## 🛠 Built-in Tools / Alatan Terbina

| Tool / Alatan | Description / Penerangan |
|------|------------|
| `open_app` | Launches applications and URLs / Melancarkan aplikasi dan URL |
| `web_search` | Search via DuckDuckGo / Carian melalui DuckDuckGo |
| `browser_control` | Playwright automation / Automasi Playwright |
| `file_controller` | File/folder CRUD / Pengurusan fail/folder |
| `file_processor` | Secure processing of dropped files / Pemprosesan fail selamat |
| `code_helper` | Write, run, and explain code / Tulis, lari, dan terangkan kod |
| `agent_task` | Autonomous goal execution / Pelaksanaan matlamat autonomi |
| `screen_process` | Vision-based analysis / Analisis berasaskan penglihatan |
| `computer_control` | Mouse/Keyboard control / Kawalan Tetikus/Papan Kekunci |
| `game_updater` | Steam & Epic Games management / Pengurusan Steam & Epic Games |
| `save_memory` | Permanent fact storage / Penyimpanan fakta kekal |
| `shutdown_jarvis` | Terminate autopilot / Tamatkan autopilot |

---

## ⚙ Configuration / Konfigurasi (`config/api_keys.json`)

| Key / Kunci | Description / Penerangan |
|-----|-------------|
| `stt_engine` | `whisper`, `vosk` |
| `llm_provider`| `ollama`, `openai` |
| `tts_engine` | `edgetts`, `kokoro`, `elevenlabs` |

---

## ⌨ Shortcuts / Pintasan

| Key / Kekunci | Action / Tindakan |
|-----|--------|
| `F4` | Mute/Unmute Sensor / Senyap/Aktifkan Sensor |
| `F11` | Fullscreen / Skrin Penuh |

---

## License / Lesen
MIT — FatihMakes Industries / Meteor Group

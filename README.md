<div align="center">
  <img src="https://img.shields.io/badge/OS-Assistant-0052FF?style=for-the-badge&logo=windows&logoColor=white" alt="OS Assistant Logo">
  <h1>🤖 OS Assistant: Your Intelligent Native Desktop AI Agent</h1>
  <p><i>Transform your operating system into an intelligent, autonomous environment with advanced AI vision, C++ native processing, and multi-provider support.</i></p>

  <a href="https://github.com/ArunasishRoychowdhuty/os_assistant/issues"><img src="https://img.shields.io/github/issues/ArunasishRoychowdhuty/os_assistant" alt="Issues"></a>
  <a href="https://github.com/ArunasishRoychowdhuty/os_assistant/network/members"><img src="https://img.shields.io/github/forks/ArunasishRoychowdhuty/os_assistant" alt="Forks"></a>
  <a href="https://github.com/ArunasishRoychowdhuty/os_assistant/stargazers"><img src="https://img.shields.io/github/stars/ArunasishRoychowdhuty/os_assistant" alt="Stars"></a>
</div>

---

## 🌟 Overview

**OS Assistant** is a powerful, production-grade native desktop agent designed to manage, monitor, and interact with your operating system. It acts as a bridge between advanced Large Language Models (LLMs) and your local computer.

With the latest major upgrades, OS Assistant now features a **Blazing-Fast C++ Native Engine**, advanced **Live Perception Modules**, **Action Verification**, and an entire **Algorithmic Trading Lab**.

## ✨ What's New in the Latest Major Upgrade?

- **🧠 Event-Driven Orchestrator Spine:** Transitioned from a monolithic loop to a fully decoupled `Observer -> Planner -> Executor -> Learner` architecture using queues for zero-latency streaming execution.
- **⚡ Execution Adapters (Terminal-First Architecture):** Replaced legacy PyAutoGUI actions with modular adapters (`InputAdapter`, `SystemAdapter`). The system now launches applications instantly via PowerShell instead of slow GUI clicking.
- **🎮 Game-Ready DirectInput:** Upgraded keyboard and mouse interactions to use `pydirectinput`, allowing the AI to play and interact with DirectX/OpenGL games (e.g., Free Fire, Valorant) flawlessly.
- **🗣️ Wake Word & TTS Engine:** The assistant now listens for "Hey Jarvis" natively via `openwakeword` and speaks its actions out loud using a threaded `pyttsx3` engine.
- **🛡️ Adaptive Resource Manager (ARM):** Intelligently throttles background screen monitoring when heavy apps or games are detected, saving CPU and RAM automatically.
- **📈 Fully-Featured Trading Lab (`trading_lab/`):** A robust automated trading framework integrated right into the project with Broker Integrations, Paper Trading, and Risk Management.

## ✨ Core Features

- **Multi-Provider AI Vision:** Seamlessly switch between `GPT-4o`, `Claude 3.5 Sonnet`, and `Gemini 2.5 Flash`.
- **Advanced Long-Term Memory:** Utilizes local Vector Databases and `memory_store.py` to remember preferences and context over long periods.
- **Bulletproof Safety Mechanisms:** Built-in safeguards automatically block destructive commands (`format`, `rm -rf`) and prompt for human confirmation.
- **Proactive System Monitoring:** Continuously monitors system health and resource usage using native Windows APIs.

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+** installed on your system.
- **C++ Build Tools** (Optional, for compiling the native engine).
- An API key from at least one supported AI provider (OpenAI, Anthropic, or Google).
- Git installed on your system.

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/ArunasishRoychowdhuty/os_assistant.git
cd os_assistant
```

**2. Create a virtual environment** (Highly Recommended)
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r os_assistant/requirements.txt
```

**4. Compile Native Engine (Optional but Recommended)**
```bash
cd native_engine
cmake .
cmake --build . --config Release
cd ..
```

**5. Environment Setup**
Copy the template configuration file:
```bash
cp os_assistant/.env.example os_assistant/.env
```
Open `.env` and securely add your API keys.

## 🛠️ Configuration

Fine-tune the assistant by editing `os_assistant/config.py` or your `.env` file:

- `AI_PROVIDER`: Set your preferred brain (`nvidia`, `openai`, `anthropic`, or `gemini`).
- `CONFIRM_DESTRUCTIVE`: Toggle human-in-the-loop safety confirmations `True`/`False`.
- `MAX_RETRIES`: Adjust the agent's persistence on failed tasks.

## 🕹️ Usage

Ignite the assistant by running the main entry point:

```bash
python os_assistant/native_app.py
```
*Sit back as the OS Assistant begins analyzing its environment and awaits your instructions!*

## 🤝 Contributing

We welcome contributions! If you're looking to improve the architecture, add new AI providers, or squash bugs:

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---
<div align="center">
  <b>Built with ❤️ for an intelligent future.</b>
</div>

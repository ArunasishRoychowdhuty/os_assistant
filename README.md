<div align="center">
  <img src="https://img.shields.io/badge/OS-Assistant-0052FF?style=for-the-badge&logo=windows&logoColor=white" alt="OS Assistant Logo">
  <h1>🤖 OS Assistant: Your Intelligent Native Desktop AI Agent</h1>
  <p><i>Transform your operating system into an intelligent, autonomous environment with advanced AI vision and multi-provider support.</i></p>

  <a href="https://github.com/ArunasishRoychowdhuty/os_assistant/issues"><img src="https://img.shields.io/github/issues/ArunasishRoychowdhuty/os_assistant" alt="Issues"></a>
  <a href="https://github.com/ArunasishRoychowdhuty/os_assistant/network/members"><img src="https://img.shields.io/github/forks/ArunasishRoychowdhuty/os_assistant" alt="Forks"></a>
  <a href="https://github.com/ArunasishRoychowdhuty/os_assistant/stargazers"><img src="https://img.shields.io/github/stars/ArunasishRoychowdhuty/os_assistant" alt="Stars"></a>
</div>

---

## 🌟 Overview

**OS Assistant** is a powerful, production-grade native desktop agent designed to manage, monitor, and interact with your operating system. It acts as a bridge between advanced Large Language Models (LLMs) and your local computer, utilizing cutting-edge **Computer Vision** and **System API** integrations to understand your screen and execute actions seamlessly.

Whether you're automating repetitive tasks, performing system diagnostics, or simply looking for a hands-free desktop companion, OS Assistant brings context-aware AI right to your desktop.

## ✨ Key Features

- **👁️ Multi-Provider AI Vision:** Seamlessly switch between the industry's best models for screen understanding:
  - `GPT-4o` (OpenAI)
  - `Claude 3.5 Sonnet` (Anthropic)
  - `Gemini 2.5 Flash` (Google)
- **🧠 Advanced Long-Term Memory:** Utilizes local Vector Databases to remember user preferences, learn from past interactions, and retain context over long periods.
- **🛡️ Bulletproof Safety Mechanisms:** Built-in safeguards automatically block destructive commands (e.g., `format`, `del /s`) and prompt for human confirmation before high-risk operations.
- **⚡ Proactive System Monitoring:** Continuously monitors system health, resource usage, and background processes using robust native Windows APIs.
- **⚙️ Native OS Automation:** Executes native UI interactions, captures high-quality screenshots, and manages files with a resilient, multi-threaded architecture.

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+** installed on your system.
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

**4. Environment Setup**
Copy the template configuration file:
```bash
cp os_assistant/.env.example os_assistant/.env
```
Open the newly created `.env` file and securely add your API keys.

## 🛠️ Configuration

Fine-tune the assistant by editing `os_assistant/config.py` or your `.env` file:

- `AI_PROVIDER`: Set your preferred brain (`openai`, `anthropic`, or `gemini`).
- `CONFIRM_DESTRUCTIVE`: Toggle human-in-the-loop safety confirmations `True`/`False`.
- `MAX_RETRIES`: Adjust the agent's persistence on failed tasks.

*Note: The assistant automatically manages its screenshot cache and vector databases within your local AppData directory.*

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

# OS Assistant

A powerful, native desktop agent designed to manage and monitor your operating system. OS Assistant integrates advanced AI vision providers (OpenAI, Anthropic, Gemini) to understand your screen and interact seamlessly with your environment.

## Features

- **Multi-Provider AI Vision**: Supports OpenAI (`gpt-4o`), Anthropic (`claude-sonnet-4`), and Google Gemini (`gemini-2.5-flash-preview`).
- **Safety First**: Built-in protections block destructive commands (like `format`, `del /s`) and ask for confirmation before executing high-risk operations.
- **Intelligent Memory Management**: Handles short-term context and long-term memory to learn from interactions and errors.
- **Native OS Interactions**: Integrates robust screenshotting, delayed action execution, and clean directory management.

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd "my ai"
   ```

2. **Set up a virtual environment (Recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r os_assistant/requirements.txt
   ```

4. **Environment Configuration:**
   Copy the example environment file and configure your API keys.
   ```bash
   cp os_assistant/.env.example os_assistant/.env
   ```
   Open `os_assistant/.env` and set your preferred `AI_PROVIDER` and corresponding API keys.

## Configuration Highlights

Edit `os_assistant/config.py` (or set corresponding environment variables in `.env`) to customize behavior:
- `AI_PROVIDER`: "openai", "anthropic", or "gemini".
- `CONFIRM_DESTRUCTIVE`: Enable/disable safety prompts for dangerous commands.
- `MAX_RETRIES`: Number of retry attempts for agent actions.
- Directories for screenshots and memory are automatically managed in your local AppData folder.

## Usage

Start the assistant by running the native application entry point:
```bash
python os_assistant/native_app.py
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)

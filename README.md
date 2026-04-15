# ai-to-tgbot-port (Windows Branch)

Local Telegram bot runtime for GGUF models on Windows, built around `llama.cpp`.

This branch is the Windows-specific package. It is meant to be usable without any Linux-only files or Linux-specific setup steps mixed into the repository.

## What This Branch Is

This branch contains a Windows-focused package for running a Telegram bot on top of a local GGUF model.

The goal is straightforward:

* run a Telegram bot on a Windows machine;
* connect it to a local `.gguf` model;
* use `llama.cpp` / `llama-server` instead of a cloud API;
* keep the full runtime local;
* make installation and launch simple enough for normal desktop use.

This is not just a single `bot.py` file. The package includes:

* a Windows launcher;
* environment setup logic;
* model auto-discovery;
* `llama.cpp` discovery or download;
* the Telegram bot runtime;
* local SQLite helpers;
* health checks and restart logic for `llama-server`.

## What Is Inside

The root of this branch contains the Windows package directly.

Files:

* `install_and_launch.bat`
  Windows entrypoint for source-based setup and launch.

* `launcher_cli.py`
  Interactive installer / launcher logic. It can:
  * check Python availability;
  * inspect installed Python packages through `pip list`;
  * install missing dependencies;
  * find local GGUF models;
  * find local `llama-server.exe`;
  * download `llama.cpp` if needed;
  * build or update `.env`;
  * launch the Telegram bot.

* `bot.py`
  Main Telegram bot runtime. It:
  * validates configuration;
  * starts and monitors `llama-server`;
  * communicates with the model over HTTP;
  * queues requests to avoid overlapping generations;
  * stores state locally;
  * exposes bot commands such as `/status`, `/reset`, `/license`, `/source`, and `/ineedmore`.

* `bot_control_db.py`
  SQLite helper layer used by the runtime for local state and settings.

* `.env.example`
  Example environment file.

* `requirements.txt`
  Python dependency list.

* `LICENSE`
  Project license.

* `.gitignore`
  Ignore rules for runtime state, models, logs, databases, and local artifacts.

Optional:

* `HeyMate.exe`
  Windows one-file launcher artifact. This is not required to exist in the repository itself. It is usually better shipped through GitHub Releases.

## How It Works

The runtime has four practical layers:

1. Launcher layer
   Handles setup, dependency checks, model discovery, `llama.cpp` discovery, and `.env` generation.

2. Telegram layer
   The bot is built on `aiogram` and handles Telegram updates, commands, and callbacks.

3. Model layer
   A local `llama-server.exe` process serves the GGUF model through an OpenAI-compatible HTTP API.

4. Local state layer
   The package uses local files and SQLite for state, logs, and configuration helpers.

Request flow:

1. A Telegram user sends a message.
2. The bot validates limits and chat state.
3. The bot builds a prompt and short dialog context.
4. The bot enters a serialized model queue.
5. The runtime ensures `llama-server` is alive.
6. The prompt is sent to the local model over HTTP.
7. The streamed response is processed.
8. The final answer is sent back to Telegram.
9. Logs and dialog state are updated locally.

Why the queue exists:

* one local model instance is easier to keep stable than concurrent overlapping generations;
* replies become more predictable;
* auto-restart logic is easier to reason about;
* `/status` can show real queue state.

## Installation

### Option 1: Use the Windows source package

Requirements:

* Windows
* Python 3.11+
* a Telegram bot token from BotFather
* a GGUF model
* `llama.cpp` with `llama-server.exe` available locally, or allow the launcher to download it

Steps:

```powershell
git clone -b windows https://github.com/AlbertGithot/ai-to-tgbot-port.git
cd ai-to-tgbot-port
install_and_launch.bat
```

What the launcher does:

* checks Python;
* checks required Python packages;
* tries to find a local GGUF model;
* tries to find a local `llama-server.exe`;
* can download a recommended model if you want;
* can download `llama.cpp` if needed;
* creates or updates `.env`;
* launches the bot.

### Option 2: Use `HeyMate.exe`

If you publish a release artifact, Windows users can use `HeyMate.exe` instead of running the source package directly.

That is the simplest distribution format for non-technical users.

## Configuration

The runtime reads `.env` from the project root.

Important variables:

* `BOT_TOKEN`
  Telegram bot token.

* `MODEL_PATH`
  Path to the `.gguf` model.

* `LLAMA_CPP_DIR`
  Path to the `llama.cpp` directory.

* `LLAMA_SERVER_EXE`
  Path to `llama-server.exe`.

* `SOURCE_URL`
  Repository URL shown by the bot.

* `MAX_HISTORY_MESSAGES`
  Chat memory depth. `-1` means unlimited.

* `N_CTX`
  Context size for the model runtime.

* `MAX_TOKENS`
  Main generation token budget.

* `BRIEF_MAX_TOKENS`
  Short-answer token budget.

* `LLAMA_SERVER_AUTO_RESTART`
  Enables automatic restart attempts when the runtime fails.

* `LLAMA_SERVER_MAX_RESTART_ATTEMPTS`
  Number of restart attempts per failure window.

* `LLAMA_SERVER_RESTART_DELAY_SECONDS`
  Delay between restart attempts.

## Operational Notes

Runtime artifacts are local and should not be committed:

* `.env`
* `.launcher_state.json`
* `bot_logs/`
* `bot_control.db`
* `*.gguf`
* `llama.cpp/`
* `build/`
* `dist/`
* `__pycache__/`

Windows-specific note:

* `llama-server.exe` should exist either through a local `llama.cpp` installation or via the launcher's download flow.

## Publishing

If you publish a GitHub Release for Windows, the sensible release asset is:

* `HeyMate.exe`

GitHub already provides source archives automatically, so you do not need to upload the full source tree manually as a release asset.

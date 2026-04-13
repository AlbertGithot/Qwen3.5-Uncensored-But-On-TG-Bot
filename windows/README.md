# Windows Package

This folder contains the Windows-side source package.

## Files

* `install_and_launch.bat` - entrypoint for local setup and launch
* `launcher_cli.py` - interactive installer and launcher logic
* `bot.py` - Telegram bot runtime
* `bot_control_db.py` - SQLite helpers
* `.env.example` - environment template
* `requirements.txt` - Python dependencies

## Typical Setup

```powershell
cd windows
install_and_launch.bat
```

The launcher can:

* check Python packages with `pip list`
* find local GGUF models
* find or download `llama.cpp`
* generate `.env`
* start the Telegram bot

## Runtime Notes

* `HeyMate.exe` is a distributable build artifact, not a tracked repository file.
* Runtime data such as `.env`, `bot_logs/`, databases, downloaded models, and `llama.cpp/` stay ignored.

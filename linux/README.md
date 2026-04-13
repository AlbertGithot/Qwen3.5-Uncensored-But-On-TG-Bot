# Linux Package

This folder contains the Linux-side source package.

## Files

* `HeyMate` - main terminal-first launcher entrypoint
* `install_and_launch.sh` - entrypoint for setup and launch
* `launcher_cli.py` - interactive installer and launcher logic
* `bot.py` - Telegram bot runtime
* `bot_control_db.py` - SQLite helpers
* `.env.example` - environment template
* `requirements.txt` - Python dependencies

## Typical Setup

```bash
cd linux
chmod +x HeyMate install_and_launch.sh
./HeyMate
```

The launcher can:

* check Python dependencies
* find local GGUF models
* find or download `llama.cpp`
* generate `.env`
* install or remove a `systemd` service
* start, stop, and restart the `systemd` service
* show `systemd` status
* show service or runtime logs

## Server-Oriented Notes

This package is aimed at headless Linux usage.

For long-running deployments, prefer the launcher option that installs `heymate-bot.service` and then manage it through `systemctl` instead of keeping the bot in an interactive shell or `screen`.

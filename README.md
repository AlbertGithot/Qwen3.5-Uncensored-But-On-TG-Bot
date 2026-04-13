# ai-to-tgbot-port

Local Telegram bot for GGUF models powered by `llama.cpp`.

This repository is meant for running a Telegram bot on top of a local LLM instead of a cloud API. The bot talks to a local `llama-server`, uses GGUF models, and ships with platform-specific launchers for Windows and Linux.

This README covers four things in detail:

1. What this project is
2. What is inside the repository
3. How it works internally
4. How to install and run it

---

## 1. What this project is

`ai-to-tgbot-port` is a self-hosted Telegram bot stack for local GGUF models.

It is designed for cases where you want to:

* run a Telegram bot on your own machine or server;
* connect it to a local `.gguf` model;
* avoid external paid or restricted LLM APIs;
* keep control over the runtime, model path, logs, restart logic, and configuration;
* use the same core idea on both Windows and Linux.

This is not just a single bot script. It is a small local runtime package that includes:

* an installer / launcher;
* the Telegram bot runtime;
* a local SQLite-backed helper layer;
* platform-specific packaging for Windows and Linux;
* logic for finding models and `llama.cpp`;
* logic for generating and updating `.env`;
* health and restart handling for `llama-server`.

At a high level, the project does this:

* a user sends a message in Telegram;
* the bot receives it;
* the bot sends the prompt to a local `llama-server`;
* the model generates a reply;
* the bot returns the result to Telegram;
* logs, history, and runtime state are stored locally.

The goal is simple:

* local;
* practical;
* easy to deploy;
* usable from a desktop or a headless Linux server.

---

## 2. What is inside the repository

The repository root is intentionally minimal. Platform-specific runtime files live inside `windows/` and `linux/`.

### Repository root

* `windows/`  
  Windows package: batch launcher, bot runtime, installer logic, env template, dependencies.

* `linux/`  
  Linux package: shell entrypoints, bot runtime, installer logic, env template, dependencies, `systemd` helpers.

* `LICENSE`  
  Project license.

* `README.md`  
  This file.

* `.gitignore`  
  Ignores runtime artifacts such as `.env`, logs, databases, models, downloaded `llama.cpp`, caches, and build artifacts.

### What is inside `windows/`

* `install_and_launch.bat`  
  Main entrypoint when using the source package on Windows.

* `launcher_cli.py`  
  Interactive installer / launcher logic for Windows. It can:
  * find Python;
  * check installed packages with `pip list`;
  * install missing Python dependencies;
  * find local `.gguf` models;
  * find local `llama-server.exe`;
  * optionally download a recommended model;
  * optionally download `llama.cpp`;
  * create and update `.env`;
  * launch the bot.

* `bot.py`  
  Main Telegram bot runtime. It:
  * starts `aiogram`;
  * validates configuration;
  * starts `llama-server`;
  * sends prompts to the model over HTTP;
  * serializes access to the model through a queue;
  * logs runtime events;
  * handles bot commands.

* `bot_control_db.py`  
  SQLite helper layer used by the bot runtime.

* `.env.example`  
  Environment template.

* `requirements.txt`  
  Python dependencies.

* `README.md`  
  Short package-specific README for Windows.

Optional:

* `HeyMate.exe` can exist as a built launcher artifact, but it is not required to be tracked in the repository. The normal place for that file is a release artifact, not the source tree.

### What is inside `linux/`

* `HeyMate`  
  Main Linux entrypoint. This is the Linux equivalent of the standalone launcher concept. It is a terminal-first wrapper that launches the Python installer / launcher and is meant to be usable over SSH.

* `install_and_launch.sh`  
  Thin compatibility wrapper that delegates to `./HeyMate`.

* `launcher_cli.py`  
  Linux installer / launcher. It can:
  * find Python;
  * install missing Python dependencies;
  * find local `.gguf` models;
  * find or download `llama.cpp`;
  * create and update `.env`;
  * launch the bot in foreground;
  * install, start, stop, restart, and remove a `systemd` service;
  * show service status and logs.

* `bot.py`  
  Linux bot runtime. It is kept in sync with the Windows runtime logic.

* `bot_control_db.py`  
  SQLite helper layer.

* `.env.example`  
  Linux environment template.

* `requirements.txt`  
  Python dependencies.

* `README.md`  
  Short package-specific README for Linux.

### What is not supposed to be committed

These are runtime artifacts and should stay out of git:

* `.env`
* `.launcher_state.json`
* `bot_logs/`
* `bot_control.db`
* `*.gguf`
* downloaded `llama.cpp/`
* `__pycache__/`
* temporary build outputs
* release binaries

---

## 3. How it works

This section is intentionally practical. It describes the actual runtime flow, not a marketing summary.

### High-level architecture

The project has four main layers:

1. Launcher layer  
   Responsible for environment checks, dependency checks, model selection, `llama.cpp` discovery, and `.env` generation.

2. Telegram bot layer  
   Built on top of `aiogram`, receives messages and commands from Telegram users.

3. Model runtime layer  
   `llama-server` running on top of `llama.cpp`.

4. Local state layer  
   SQLite + log files for state, events, and runtime diagnostics.

### Request flow

When a Telegram user sends a message, the runtime flow is:

1. The bot receives the message.
2. The bot validates limits, chat state, and block rules.
3. The bot builds the prompt and relevant dialog context.
4. The bot places generation behind a serialized model lock.
5. The bot ensures `llama-server` is running.
6. The bot sends an OpenAI-compatible chat request to the local HTTP endpoint.
7. The bot reads the streamed response.
8. The bot assembles the final user-facing answer.
9. The answer is sent back to Telegram.
10. Events are logged and dialog memory is updated.

### Why a serialized model queue exists

There is one local model runtime behind the bot. Without queueing and serialization, concurrent requests quickly become messy:

* latency spikes;
* overlapping generation state;
* unstable streaming;
* harder failure recovery;
* harder debugging.

Because of that, the runtime uses a serialized model slot:

* one active generation at a time;
* pending requests wait in queue;
* `/status` exposes queue and active request information.

This is a deliberate tradeoff in favor of stability.

### How `llama-server` is used

The project does not bind directly to a Python model object. Instead:

* it launches `llama-server`;
* it talks to it over HTTP;
* it sends chat requests to `/v1/chat/completions`;
* it checks runtime health through health/models endpoints.

This has a few practical advantages:

* easier restart behavior;
* easier debugging;
* cleaner process isolation;
* the same basic runtime pattern on Windows and Linux.

### Health and restart handling

If `llama-server`:

* crashes;
* disconnects;
* fails to come up in time;
* returns an infrastructure-level transport/runtime error;

the bot can attempt a controlled restart and retry.

This is not a substitute for a real deployment process, but it improves survivability on local or semi-local deployments.

### What `/status` is for

`/status` is a runtime diagnostic command. It reports:

* whether AI is enabled;
* whether the `llama-server` API is reachable;
* whether the `llama-server` process is running;
* PID and exit code when available;
* selected model path;
* queued request count;
* current active request label;
* active request duration;
* number of dialogs currently kept in memory.

This is useful on a desktop machine and especially useful on a Linux server.

### How memory works

The bot keeps a bounded dialog history:

* history length is limited;
* each history entry is length-limited;
* this prevents context growth from becoming uncontrolled;
* normal chats use that memory;
* special flows such as `/ineedmore` can use their own handling rules.

### How `/ineedmore` works

`/ineedmore` is a grouped multi-request mode:

* the user prepares a multi-item template;
* the bot processes items one by one;
* the bot updates a status view;
* the bot assembles a final combined result.

This is useful when a single topic needs multiple sub-prompts without flooding the chat with separate manual requests.

### Why Linux uses `systemd` instead of `screen`

You mentioned `screen`, which can work, but it is not the best default for a server-oriented deployment.

For a headless Linux host, `systemd` is the better default because it gives:

* automatic restart after reboot;
* clean process supervision;
* consistent `status`, `start`, `stop`, `restart`;
* easier log inspection through `journalctl`;
* less manual terminal babysitting.

So the Linux package is built around this idea:

* foreground mode exists for direct testing;
* `systemd` mode is the preferred production path.

This is the simplest reliable option for SSH/server use.

---

## 4. Installation and setup

This section is written as a real deployment guide, not a minimal snippet.

### 4.1. Prerequisites

Regardless of platform, you need:

* a Telegram bot token from `BotFather`;
* a local GGUF model;
* `llama.cpp` / `llama-server`;
* Python 3.11+;
* internet access during initial setup if dependencies, `llama.cpp`, or models need to be downloaded.

### 4.2. What the launcher expects from the model

The project is designed around `.gguf` models.

The launcher and runtime can:

* search common local model directories;
* search common Hugging Face cache locations;
* list discovered `.gguf` files;
* update `MODEL_PATH` automatically in `.env`;
* auto-tune several runtime defaults based on detected model family.

### 4.3. Windows installation

#### Source-based setup

1. Clone or unpack the repository.
2. Open the `windows/` directory.
3. Run:

```powershell
install_and_launch.bat
```

From there the launcher will:

* locate Python;
* inspect Python dependencies;
* install missing packages such as `aiogram` and `aiohttp`;
* locate a local `llama-server.exe` if present;
* locate local `.gguf` models if present;
* offer model download if needed;
* generate `.env`;
* allow environment review;
* start the bot.

#### Optional executable launcher

If you distribute a built `HeyMate.exe`, the flow is similar, but the repository itself does not need to track that binary.

Recommended practice:

* keep the source repo clean;
* distribute `HeyMate.exe` through release artifacts if needed.

### 4.4. Linux installation

#### Terminal / SSH setup

1. Open the `linux/` directory.
2. Make the launcher executable:

```bash
chmod +x HeyMate install_and_launch.sh
```

3. Run the main Linux launcher:

```bash
./HeyMate
```

You can also run:

```bash
./install_and_launch.sh
```

but `./HeyMate` is the primary entrypoint.

The Linux launcher will:

* locate `python3`;
* install Python dependencies;
* find or download `llama.cpp`;
* find or help choose a `.gguf` model;
* create `.env`;
* let you review configuration;
* offer foreground run mode;
* offer `systemd` installation and management.

### 4.5. Important environment variables

The critical minimum set is:

* `BOT_TOKEN`  
  Telegram bot token.

* `MODEL_PATH`  
  Path to the `.gguf` model file.

* `LLAMA_CPP_DIR`  
  Path to the `llama.cpp` directory.

* `LLAMA_SERVER_EXE`  
  Path to `llama-server.exe` on Windows or `llama-server` on Linux.

* `SOURCE_URL`  
  Repository URL shown by the bot.

Important runtime settings:

* `LLAMA_SERVER_HOST`
* `LLAMA_SERVER_PORT`
* `LLAMA_SERVER_START_TIMEOUT`
* `LLAMA_SERVER_AUTO_RESTART`
* `LLAMA_SERVER_MAX_RESTART_ATTEMPTS`
* `LLAMA_SERVER_RESTART_DELAY_SECONDS`

Model / generation settings:

* `CHAT_FORMAT`
* `N_CTX`
* `N_BATCH`
* `N_GPU_LAYERS`
* `MAX_TOKENS`
* `BRIEF_MAX_TOKENS`
* `TEMPERATURE`
* `TOP_P`
* `TOP_K`
* `REPEAT_PENALTY`

Limits / memory settings:

* `MAX_HISTORY_MESSAGES`
* `MAX_HISTORY_ENTRY_CHARS`
* `MAX_ACTIVE_DIALOGS`
* `MAX_USER_TEXT_CHARS`
* `MAX_MULTI_REQUEST_TEXT_CHARS`
* `MAX_LOG_TEXT_CHARS`
* `MAX_MODEL_REPLY_CHARS`
* `MAX_TRACKED_BOT_MESSAGES`

Feature flags:

* `SHOW_MODEL_RAW`
* `USE_RAW_MODEL_REPLY`
* `ENABLE_REPAIR_PASS`
* `AI_ENABLED`

### 4.6. Recommended Linux production path

For a Linux server, the recommended path is:

1. run `./HeyMate`;
2. complete dependency and model setup;
3. generate `.env`;
4. install the `systemd` service from the launcher menu;
5. use launcher menu actions or `systemctl` to manage the bot;
6. use `journalctl` or the launcher log view for diagnostics.

This is preferable to `screen` because it is easier to supervise and more robust after disconnects or reboots.

### 4.7. Post-install validation

After setup, verify at least the following:

1. `.env` exists.
2. `MODEL_PATH` points to a real `.gguf`.
3. `llama-server` starts successfully.
4. `/start` works in Telegram.
5. `/status` reports a healthy runtime.
6. A simple user message gets a model response.

On Linux, additionally verify:

* `systemctl status heymate-bot.service`
* service restart behavior
* service survival after reboot if you use `systemd`

### 4.8. Updating the model later

When changing the model, you do not need to rebuild everything manually.

The launcher can:

* rediscover available models;
* let the user choose another `.gguf`;
* update `MODEL_PATH`;
* refresh related defaults in `.env`.

After changing the model, it is a good idea to check `/status` again.

---

## Summary

If you want the short version:

* this is a local Telegram bot for GGUF models;
* it runs through `llama.cpp` / `llama-server`;
* the repository is split into `windows/` and `linux/`;
* Linux now has a real terminal-first `HeyMate` entrypoint for SSH/server use;
* production use on Linux is expected to go through `systemd`, not `screen`.

See [LICENSE](LICENSE) for licensing details.

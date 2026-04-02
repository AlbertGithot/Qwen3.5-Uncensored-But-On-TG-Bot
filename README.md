# 🤖 Qwen3.5 Uncensored Telegram Bot

<img src="https://github.com/devicons/devicon/blob/master/icons/python/python-original.svg" title="Python"  alt="Python" width="40" height="40"/>&nbsp;
<img src="https://avatars.githubusercontent.com/u/33784865?s=280&v=4" title="Aiogram"  alt="Aiogram" width="40" height="40"/>&nbsp;
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><path fill="#0078d4" d="M128 92.399v19.015h-3.176V96.246s-1.09 1.006-3.885 1.735v-2.707c4.155-1.536 5.646-2.875 5.646-2.875zm-9.378 0v19.015h-3.176V96.246s-1.09 1.006-3.884 1.735v-2.707c4.154-1.536 5.645-2.875 5.645-2.875zm-12.217 15.308c0 2.965-2.688 4.12-5.383 4.12-1.755 0-3.502-.676-3.502-.676v-3.153s1.519 1.323 3.64 1.34c1.455 0 2.11-.459 2.11-1.332.037-.7-.39-1.087-.9-1.377-.35-.21-.898-.469-1.643-.775-.876-.377-1.53-.741-1.959-1.091a3.387 3.387 0 0 1-.946-1.236 4.03 4.03 0 0 1-.35-1.624c0-2.394 1.996-4.085 5.187-4.085 2.11 0 3.023.517 3.023.517v2.995s-1.499-1.036-3.056-1.045c-1.116 0-1.96.406-1.975 1.326-.008 1.185 1.444 1.763 2.31 2.113 1.262.508 2.186 1.051 2.703 1.673.517.622.741 1.249.741 2.31zm-13.56 3.707H89.42l-2.619-9.637-2.81 9.636h-3.324L76.793 98.14h3.25l2.53 10.312L85.53 98.14h3.05l2.635 10.285 2.466-10.285h2.98zm-16.66-6.717c0 4.612-2.757 7.11-6.897 7.11-4.501 0-6.808-2.694-6.808-6.82 0-4.722 2.764-7.178 7.137-7.178 4.006 0 6.567 2.561 6.567 6.888zm-3.234.105c0-2.052-.728-4.333-3.505-4.333-2.664 0-3.699 1.983-3.699 4.412 0 2.64 1.243 4.318 3.68 4.318 2.61 0 3.505-2.003 3.524-4.397zm-15.808 6.612v-1.715h-.053c-.964 1.622-2.931 1.995-4.303 1.995-4.077 0-5.573-3.167-5.573-6.537 0-2.235.556-4.022 1.669-5.363 1.122-1.35 2.62-1.934 4.495-1.934 2.92 0 3.712 1.624 3.712 1.624h.053V91.78h3.15v19.635zm.026-7.588c0-1.608-1.034-3.436-3.215-3.436-2.496 0-3.466 2.172-3.466 4.675 0 2.185.916 4.169 3.292 4.202 2.33 0 3.37-2.221 3.39-4.057zm-15.274 7.588V104c0-1.942-.603-3.618-2.56-3.618-1.946 0-3.18 1.753-3.18 3.526v7.505h-3.037V98.098h3.037v1.884h.052c1.008-1.56 2.463-2.108 4.364-2.108 1.429 0 2.533.351 3.313 1.263.788.91 1.135 2.295 1.135 4.153v8.123zM30.308 94.289c0 .499-.184.915-.552 1.248-.36.333-.798.5-1.314.5-.517 0-.956-.167-1.315-.5a1.632 1.632 0 0 1-.539-1.248c0-.509.18-.934.54-1.275a1.866 1.866 0 0 1 1.314-.513c.534 0 .977.175 1.327.526.36.35.539.77.539 1.262zm-3.465 17.124V98.098h3.105v13.315zm-6.454 0h-3.83l-3.734-14.215-3.775 14.215H5.135L.001 92.937h3.473l3.703 14.697 4.042-14.697h3.509l3.8 14.784 3.516-14.784h3.354zM65.56 47.731H94v28.44H65.56zm-31.559 0h28.44v28.44H34zm31.56-31.56h28.438v28.438H65.56zm-31.56 0h28.44v28.438H34z"/></svg>

Telegram bot for local GGUF models on top of `llama.cpp`.

This project includes a Telegram bot, a desktop control panel, a SQLite database for activity tracking, and a direct AI interaction interface — all managed from a single entrypoint.

---

## 📌 Description

This project provides a fully local AI-powered Telegram bot system with:

* local LLM inference via `llama.cpp`
* desktop control panel for management
* built-in SQLite database
* direct interaction with the model outside Telegram

Designed for full control, experimentation, and uncensored AI usage.

---

## ⚙️ Features

* `aiogram` Telegram bot
* Automatic `llama-server` startup
* Local GGUF model support
* Desktop control panel (tkinter)
* SQLite database for bot activity
* Dialog memory
* `/ineedmore` grouped requests
* Streamed responses in Telegram
* Raw model output in terminal logs

### 🧩 Control Panel Capabilities

* Enable / disable AI
* Start / stop Telegram worker
* Select `.gguf` model
* View users and dialogs
* Block / unblock users
* Send direct prompts to the model
* View runtime and model logs

---

## 📁 Project Structure

* `bot.py` — main entrypoint
* `bot_control_panel.py` — desktop control panel
* `bot_control_db.py` — SQLite helpers
* `bot_control.db` — runtime database (auto-created)

---

## 📦 Requirements

* Python 3.11+
* Windows build of `llama.cpp` with `llama-server.exe`
* Local GGUF model
* `tkinter` (for control panel)

Install dependencies:

```powershell
pip install -r requirements.txt
```

Optional:

```powershell
pip install pillow
```

---

## ⚙️ Configuration

Set environment variables before launch:

```powershell
$env:BOT_TOKEN="your_telegram_bot_token"
$env:MODEL_PATH="C:\Models\your-model.gguf"
$env:LLAMA_CPP_DIR="C:\Tools\llama.cpp\b8625"
$env:LLAMA_SERVER_EXE="C:\Tools\llama.cpp\b8625\llama-server.exe"
$env:SOURCE_URL="https://github.com/AlbertGithot/Qwen3.5-Uncensored-But-On-TG-Bot.git"
```

Additional settings are available in `.env.example`.

### 🔹 Notes

* `bot.py` does NOT depend on legacy config files
* Model path can be changed from the control panel
* Uses `llama-server` over HTTP (not `llama-cpp-python`)

---

## 🚀 Run

Default mode (control panel):

```powershell
python bot.py
```

Worker modes:

```powershell
python bot.py --server-worker
python bot.py --bot-worker
```

---

## 🖥️ Control Panel

Includes four main sections:

### Management

* Enable / disable AI
* Start / stop bot
* Select model
* Check status

### Database

* View users
* Inspect dialogs
* Block / unblock users

### Direct AI

* Send prompts directly to the model

### Terminal

* View runtime logs
* View `llama-server` output

---

## 🤖 Telegram Features

* Dialog reset
* `/ineedmore` grouped requests
* `/source` — source code link
* `/license` — license notice
* Streamed responses
* Optional raw output logging

---

## 📂 Runtime Data

Generated locally and usually not committed:

* `bot_control.db`
* `bot_logs/`
* `__pycache__/`

---

## 🧠 Model

Example configuration used during development:

**Model:**
HauhauCS/Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive
https://huggingface.co/HauhauCS/Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive

* Format: GGUF
* Quantization: Q5_K_M
* Size: ~24.8 GB

Licensed under the Apache License 2.0.

---

## ⚠️ Recommendations

This project is designed to run with **llama.cpp**.

Using alternatives like `llama-cpp-python` is **not recommended for inexperienced users**.
It may break the inference pipeline if used incorrectly.

---

## ⚠️ Disclaimer

`bot.py` and parts of the project were generated and adapted with the help of AI.
The code is not fully reviewed and may contain issues.

---

## 💸 Support the Author

If you like this project, you can support the author:

* **USDT (TON):**
  UQDCmDuVnhwvZ6EW6qv0J_nV1_7U9-IPCKYo3L279JId0qbU

* **TON:**
  UQBN03z--f0LsRcODzNLukobgrGIt6lo-MAn-FX7l1KBKZZI

* **BTC:**
  bc1q4tpzte0efcn9xsf67dcuzw6e749dahnm0j7f8m

---

## 📬 Contact

Telegram: @Default_Netion

---

## 📜 License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).

If you run this software as a network service, you must provide access to the source code.

---

## 🔗 Repository

https://github.com/AlbertGithot/Qwen3.5-Uncensored-But-On-TG-Bot.git


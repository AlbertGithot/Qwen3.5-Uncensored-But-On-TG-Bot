from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path
from tkinter import END, LEFT, RIGHT, VERTICAL, filedialog, messagebox
import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Any

from bot_control_db import (
    get_dialog_messages,
    get_setting,
    get_user,
    get_users,
    set_setting,
    set_user_blocked,
)

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - optional
    Image = None
    ImageTk = None

AVATAR_CACHE_DIR = Path(__file__).resolve().parent / "bot_logs" / "avatar_cache"


def env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


def current_model_path(default: Path) -> Path:
    return Path(get_setting("selected_model_path", str(default)) or str(default))


def ai_enabled() -> bool:
    return (get_setting("ai_enabled", "1") or "1").strip() not in {"0", "false", "False"}


def set_ai_enabled(enabled: bool) -> None:
    set_setting("ai_enabled", "1" if enabled else "0")


def llama_base_url() -> str:
    host = env_str("LLAMA_SERVER_HOST", "127.0.0.1")
    port = env_int("LLAMA_SERVER_PORT", 8080)
    return f"http://{host}:{port}"


def llama_ready() -> bool:
    url = f"{llama_base_url()}/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status == 200
    except Exception:
        return False


def discover_models(current_path: Path) -> list[Path]:
    roots: list[Path] = []
    if current_path.exists():
        roots.append(current_path.parent)
        if len(current_path.parents) >= 2:
            roots.append(current_path.parents[1])
    roots.append(Path.cwd())

    seen: set[Path] = set()
    models: list[Path] = []
    for root in roots:
        if not root.exists() or root in seen:
            continue
        seen.add(root)
        try:
            for path in root.rglob("*.gguf"):
                if path.is_file():
                    models.append(path)
        except Exception:
            continue
    return sorted(set(models))


def telegram_api_json(token: str, method: str, params: dict[str, Any]) -> dict[str, Any] | None:
    if not token:
        return None
    query = urllib.parse.urlencode(params)
    url = f"https://api.telegram.org/bot{token}/{method}?{query}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.load(response)
    except Exception:
        return None


def fetch_avatar_image(user_id: int, token: str, size: tuple[int, int] = (72, 72)) -> Any | None:
    if Image is None or ImageTk is None or not token:
        return None

    AVATAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = AVATAR_CACHE_DIR / f"{user_id}.png"

    if cache_path.is_file():
        try:
            image = Image.open(cache_path).convert("RGB")
            image.thumbnail(size)
            return ImageTk.PhotoImage(image)
        except Exception:
            pass

    photos = telegram_api_json(token, "getUserProfilePhotos", {"user_id": user_id, "limit": 1})
    if not photos or not photos.get("ok"):
        return None
    result = photos.get("result") or {}
    photos_list = result.get("photos") or []
    if not photos_list or not photos_list[0]:
        return None
    file_id = photos_list[0][-1].get("file_id")
    if not file_id:
        return None

    file_result = telegram_api_json(token, "getFile", {"file_id": file_id})
    if not file_result or not file_result.get("ok"):
        return None
    file_path = ((file_result.get("result") or {}).get("file_path")) or ""
    if not file_path:
        return None

    file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    try:
        with urllib.request.urlopen(file_url, timeout=10) as response:
            content = response.read()
        image = Image.open(BytesIO(content)).convert("RGB")
        image.thumbnail(size)
        image.save(cache_path, format="PNG")
        return ImageTk.PhotoImage(image)
    except Exception:
        return None


def direct_ai_request(prompt: str) -> str:
    if not ai_enabled():
        raise RuntimeError("ИИ выключен через панель управления.")
    url = f"{llama_base_url()}/v1/chat/completions"
    system_prompt = (
        "Ты локальный ассистент Telegram. "
        "Отвечай только на русском языке. "
        "Показывай только готовый финальный ответ пользователю."
    )

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": env_int("MAX_TOKENS", 3072),
        "temperature": env_float("TEMPERATURE", 0.6),
        "top_p": env_float("TOP_P", 0.95),
        "top_k": env_int("TOP_K", 20),
        "repeat_penalty": env_float("REPEAT_PENALTY", 1.1),
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.load(response)
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content") or choices[0].get("text") or ""
    return str(content).strip()


def launch_control_panel(script_path: Path, project_root: Path, model_path: Path) -> None:
    app = ControlPanelApp(script_path=script_path, project_root=project_root, model_path=model_path)
    app.run()


class ControlPanelApp:
    def __init__(self, *, script_path: Path, project_root: Path, model_path: Path) -> None:
        self.script_path = script_path
        self.project_root = project_root
        self.default_model_path = model_path
        self.python_executable = sys.executable

        if get_setting("selected_model_path", None) is None:
            set_setting("selected_model_path", str(model_path))
        if get_setting("ai_enabled", None) is None:
            set_setting("ai_enabled", "0")

        self.root = tk.Tk()
        self.root.title("Панель управления Telegram AI")
        self.root.geometry("1280x820")
        self.root.minsize(1100, 720)

        self.bot_process: subprocess.Popen[str] | None = None
        self.ai_process: subprocess.Popen[str] | None = None
        self.avatar_images: dict[int, Any] = {}

        self.status_var = tk.StringVar(value="Готово.")
        self.ai_status_var = tk.StringVar(value="ИИ: неизвестно")
        self.bot_status_var = tk.StringVar(value="ТГ бот: неизвестно")
        self.model_var = tk.StringVar(value=str(current_model_path(self.default_model_path)))

        self.section_frames: dict[str, ttk.Frame] = {}
        self.active_section = ""

        self._build_layout()
        self._build_management_section()
        self._build_database_section()
        self._build_direct_ai_section()
        self._build_terminal_section()

        self.show_section("management")
        self.refresh_status()
        self.refresh_users()
        self.refresh_terminal()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(2500, self.periodic_refresh)

    def run(self) -> None:
        self.root.mainloop()

    def _build_layout(self) -> None:
        nav_frame = ttk.Frame(self.root, padding=12)
        nav_frame.pack(fill="x")

        buttons = [
            ("Управление", "management"),
            ("БД", "database"),
            ("Запросы к ИИ напрямую", "direct_ai"),
            ("Терминал", "terminal"),
        ]
        for text, key in buttons:
            ttk.Button(
                nav_frame,
                text=text,
                command=lambda section=key: self.show_section(section),
            ).pack(side=LEFT, padx=6)

        status_bar = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        status_bar.pack(fill="x")
        ttk.Label(status_bar, textvariable=self.ai_status_var).pack(side=LEFT, padx=(0, 16))
        ttk.Label(status_bar, textvariable=self.bot_status_var).pack(side=LEFT, padx=(0, 16))
        ttk.Label(status_bar, textvariable=self.status_var).pack(side=LEFT)

        self.content_frame = ttk.Frame(self.root, padding=12)
        self.content_frame.pack(fill="both", expand=True)

    def show_section(self, key: str) -> None:
        for frame in self.section_frames.values():
            frame.pack_forget()
        frame = self.section_frames[key]
        frame.pack(fill="both", expand=True)
        self.active_section = key

    def _build_management_section(self) -> None:
        frame = ttk.Frame(self.content_frame)
        self.section_frames["management"] = frame

        actions = ttk.LabelFrame(frame, text="Управление", padding=16)
        actions.pack(fill="x", pady=(0, 12))

        self.ai_button = ttk.Button(actions, text="Вкл ИИ", command=self.toggle_ai)
        self.ai_button.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        self.bot_button = ttk.Button(actions, text="Запустить и подключить ТГ бота", command=self.toggle_bot)
        self.bot_button.grid(row=0, column=1, padx=8, pady=8, sticky="ew")

        ttk.Button(actions, text="Указать модель", command=self.open_model_selector).grid(
            row=0, column=2, padx=8, pady=8, sticky="ew"
        )
        ttk.Button(actions, text="Проверить статус бота и ИИ", command=self.refresh_status).grid(
            row=0, column=3, padx=8, pady=8, sticky="ew"
        )

        for column in range(4):
            actions.columnconfigure(column, weight=1)

        info = ttk.LabelFrame(frame, text="Текущие параметры", padding=16)
        info.pack(fill="x")
        self.management_info = scrolledtext.ScrolledText(info, height=12, wrap="word")
        self.management_info.pack(fill="both", expand=True)
        self.management_info.insert(
            "end",
            "Запусти ИИ и Telegram-бота отдельными кнопками.\n"
            "Модель меняется через выбор из найденных .gguf-файлов.\n"
            "Если ИИ уже запущен, после смены модели панель перезапустит только AI worker.\n",
        )
        self.management_info.configure(state="disabled")

    def _build_database_section(self) -> None:
        frame = ttk.Frame(self.content_frame)
        self.section_frames["database"] = frame

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Обновить список", command=self.refresh_users).pack(side=LEFT)

        self.user_canvas = tk.Canvas(frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient=VERTICAL, command=self.user_canvas.yview)
        self.user_cards_frame = ttk.Frame(self.user_canvas)

        self.user_cards_frame.bind(
            "<Configure>",
            lambda event: self.user_canvas.configure(scrollregion=self.user_canvas.bbox("all")),
        )
        self.user_canvas.create_window((0, 0), window=self.user_cards_frame, anchor="nw")
        self.user_canvas.configure(yscrollcommand=scrollbar.set)
        self.user_canvas.pack(side=LEFT, fill="both", expand=True)
        scrollbar.pack(side=RIGHT, fill="y")

    def _build_direct_ai_section(self) -> None:
        frame = ttk.Frame(self.content_frame)
        self.section_frames["direct_ai"] = frame

        ttk.Label(frame, text="Запрос к ИИ").pack(anchor="w")
        self.direct_prompt = scrolledtext.ScrolledText(frame, height=8, wrap="word")
        self.direct_prompt.pack(fill="x", pady=(4, 8))

        ttk.Button(frame, text="Отправить запрос", command=self.send_direct_prompt).pack(anchor="w")

        ttk.Label(frame, text="Ответ").pack(anchor="w", pady=(12, 0))
        self.direct_output = scrolledtext.ScrolledText(frame, wrap="word")
        self.direct_output.pack(fill="both", expand=True, pady=(4, 0))

    def _build_terminal_section(self) -> None:
        frame = ttk.Frame(self.content_frame)
        self.section_frames["terminal"] = frame

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Обновить логи", command=self.refresh_terminal).pack(side=LEFT)

        self.terminal_text = scrolledtext.ScrolledText(frame, wrap="none")
        self.terminal_text.pack(fill="both", expand=True)

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def refresh_status(self) -> None:
        if self.ai_process is not None and self.ai_process.poll() is not None:
            self.ai_process = None
        if self.bot_process is not None and self.bot_process.poll() is not None:
            self.bot_process = None

        ai_running = self.ai_process is not None and self.ai_process.poll() is None
        bot_running = self.bot_process is not None and self.bot_process.poll() is None
        ai_ready = llama_ready()

        self.ai_status_var.set(
            f"ИИ: {'вкл' if ai_enabled() else 'выкл'} | процесс: {'запущен' if ai_running else 'нет'} | API: {'готов' if ai_ready else 'недоступен'}"
        )
        self.bot_status_var.set(
            f"ТГ бот: {'запущен' if bot_running else 'остановлен'}"
        )
        self.ai_button.configure(text="Выкл ИИ" if ai_enabled() else "Вкл ИИ")
        self.bot_button.configure(
            text="Остановить ТГ бота" if bot_running else "Запустить и подключить ТГ бота"
        )
        self.model_var.set(str(current_model_path(self.default_model_path)))

    def toggle_ai(self) -> None:
        if ai_enabled():
            set_ai_enabled(False)
            if self.ai_process is not None and self.ai_process.poll() is None:
                self.ai_process.terminate()
                try:
                    self.ai_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.ai_process.kill()
            self.ai_process = None
            self.set_status("ИИ выключен.")
        else:
            set_ai_enabled(True)
            self.ai_process = subprocess.Popen(
                [self.python_executable, str(self.script_path), "--server-worker"],
                cwd=str(self.project_root),
            )
            self.set_status("ИИ включен и запускается.")
        self.refresh_status()

    def toggle_bot(self) -> None:
        if self.bot_process is not None and self.bot_process.poll() is None:
            self.bot_process.terminate()
            try:
                self.bot_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.bot_process.kill()
            self.bot_process = None
            self.set_status("Telegram-бот остановлен.")
        else:
            self.bot_process = subprocess.Popen(
                [self.python_executable, str(self.script_path), "--bot-worker"],
                cwd=str(self.project_root),
            )
            self.set_status("Telegram-бот запускается.")
        self.refresh_status()

    def open_model_selector(self) -> None:
        models = discover_models(current_model_path(self.default_model_path))
        dialog = tk.Toplevel(self.root)
        dialog.title("Выбор модели")
        dialog.geometry("900x500")

        ttk.Label(dialog, text="Найденные GGUF-модели").pack(anchor="w", padx=12, pady=(12, 4))
        listbox = tk.Listbox(dialog)
        listbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        current = str(current_model_path(self.default_model_path))
        selected_index = 0
        for index, model in enumerate(models):
            listbox.insert("end", str(model))
            if str(model) == current:
                selected_index = index
        if models:
            listbox.selection_set(selected_index)
            listbox.see(selected_index)

        def choose_selected() -> None:
            selection = listbox.curselection()
            if not selection:
                return
            model = Path(listbox.get(selection[0]))
            set_setting("selected_model_path", str(model))
            self.model_var.set(str(model))
            self.set_status(f"Выбрана модель: {model}")
            if self.ai_process is not None and self.ai_process.poll() is None:
                self.toggle_ai()
                self.toggle_ai()
            self.refresh_status()
            dialog.destroy()

        bottom = ttk.Frame(dialog)
        bottom.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(bottom, text="Выбрать", command=choose_selected).pack(side=LEFT)
        ttk.Button(bottom, text="Выбрать файл вручную", command=lambda: self._choose_model_file(dialog)).pack(
            side=LEFT, padx=(8, 0)
        )

    def _choose_model_file(self, parent: tk.Toplevel) -> None:
        selected = filedialog.askopenfilename(
            parent=parent,
            title="Выбери GGUF-модель",
            filetypes=[("GGUF models", "*.gguf")],
        )
        if not selected:
            return
        set_setting("selected_model_path", selected)
        self.model_var.set(selected)
        self.set_status(f"Выбрана модель: {selected}")
        if self.ai_process is not None and self.ai_process.poll() is None:
            self.toggle_ai()
            self.toggle_ai()
        self.refresh_status()
        parent.destroy()

    def refresh_users(self) -> None:
        for child in self.user_cards_frame.winfo_children():
            child.destroy()

        users = get_users()
        token = env_str("BOT_TOKEN")
        for user in users:
            card = ttk.Frame(self.user_cards_frame, padding=12, relief="groove")
            card.pack(fill="x", expand=True, pady=6)

            left = ttk.Frame(card)
            left.pack(side=LEFT, fill="both", expand=True)
            right = ttk.Frame(card)
            right.pack(side=RIGHT, fill="y")

            ttk.Label(
                left,
                text=user.get("full_name") or "Без имени",
                font=("Segoe UI", 11, "bold"),
            ).pack(anchor="w")
            ttk.Label(
                left,
                text=f"@{user.get('username')}" if user.get("username") else "username: —",
            ).pack(anchor="w")
            ttk.Label(left, text=f"ID: {user['user_id']}").pack(anchor="w")

            buttons = ttk.Frame(left)
            buttons.pack(anchor="w", pady=(8, 0))
            blocked = bool(user.get("blocked"))
            ttk.Button(
                buttons,
                text="Разблокировать доступ к боту" if blocked else "Заблокировать доступ к боту",
                command=lambda user_id=user["user_id"], blocked=blocked: self.toggle_user_block(user_id, blocked),
            ).pack(side=LEFT, padx=(0, 8))
            ttk.Button(
                buttons,
                text="Посмотреть список диалогов",
                command=lambda user_id=user["user_id"]: self.show_user_dialogs(user_id),
            ).pack(side=LEFT)

            avatar_label = ttk.Label(right, text="Аватарка\nнедоступна", width=14, anchor="center")
            avatar_label.pack()
            avatar = fetch_avatar_image(int(user["user_id"]), token)
            if avatar is not None:
                self.avatar_images[int(user["user_id"])] = avatar
                avatar_label.configure(image=avatar, text="")

        self.set_status(f"Пользователей в БД: {len(users)}")

    def toggle_user_block(self, user_id: int, currently_blocked: bool) -> None:
        set_user_blocked(user_id, not currently_blocked)
        self.refresh_users()
        self.set_status(f"Пользователь {user_id}: {'разблокирован' if currently_blocked else 'заблокирован'}")

    def show_user_dialogs(self, user_id: int) -> None:
        user = get_user(user_id)
        messages = get_dialog_messages(user_id)
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Диалоги пользователя {user_id}")
        dialog.geometry("900x650")

        text = scrolledtext.ScrolledText(dialog, wrap="word")
        text.pack(fill="both", expand=True)
        header = (
            f"Пользователь: {user.get('full_name') or '—'}\n"
            f"Username: @{user.get('username')}\n"
            f"ID: {user_id}\n\n"
        )
        text.insert("end", header)
        for item in messages:
            direction = item.get("direction") or "system"
            created_at = item.get("created_at") or ""
            body = item.get("text") or ""
            text.insert("end", f"[{created_at}] {direction.upper()}\n{body}\n\n")
        text.configure(state="disabled")

    def send_direct_prompt(self) -> None:
        prompt = self.direct_prompt.get("1.0", "end").strip()
        if not prompt:
            messagebox.showinfo("Пустой запрос", "Сначала напиши запрос для ИИ.")
            return

        self.direct_output.insert("end", f"\n[Ты]\n{prompt}\n\n[ИИ]\n")
        self.direct_output.see("end")
        self.set_status("Отправляю прямой запрос к ИИ...")

        def worker() -> None:
            try:
                reply = direct_ai_request(prompt)
            except Exception as exc:
                result = f"Ошибка: {exc}"
            else:
                result = reply or "Пустой ответ."

            def finish() -> None:
                self.direct_output.insert("end", f"{result}\n\n")
                self.direct_output.see("end")
                self.set_status("Прямой запрос завершён.")

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def refresh_terminal(self) -> None:
        paths = [
            self.project_root / "bot_logs" / "runtime.log",
            self.project_root / "bot_logs" / "llama_server.log",
        ]
        lines: list[str] = []
        for path in paths:
            lines.append(f"===== {path.name} =====")
            if path.is_file():
                content = path.read_text(encoding="utf-8", errors="ignore").splitlines()
                lines.extend(content[-120:])
            else:
                lines.append("Файл ещё не создан.")
            lines.append("")

        self.terminal_text.configure(state="normal")
        self.terminal_text.delete("1.0", END)
        self.terminal_text.insert("1.0", "\n".join(lines))
        self.terminal_text.configure(state="disabled")

    def periodic_refresh(self) -> None:
        self.refresh_status()
        if self.active_section == "database":
            self.refresh_users()
        if self.active_section == "terminal":
            self.refresh_terminal()
        self.root.after(2500, self.periodic_refresh)

    def on_close(self) -> None:
        if self.bot_process is not None and self.bot_process.poll() is None:
            self.bot_process.terminate()
        if self.ai_process is not None and self.ai_process.poll() is None:
            self.ai_process.terminate()
        set_ai_enabled(False)
        self.root.destroy()

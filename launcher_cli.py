from __future__ import annotations

import ctypes
import importlib.util
import itertools
import json
import os
import shutil
import string
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


REPO_URL = "https://github.com/AlbertGithot/ai-to-tgbot-port.git"
REPO_PAGE_URL = "https://github.com/AlbertGithot/ai-to-tgbot-port"
REPO_ZIP_URL = (
    "https://codeload.github.com/AlbertGithot/"
    "ai-to-tgbot-port/zip/refs/heads/main"
)
REPO_DIR_NAME = "ai-to-tgbot-port"
STATE_FILE_NAME = ".launcher_state.json"
ERROR_LOG_FILE_NAME = "launcher_error.log"
ENV_FILE_NAME = ".env"
ENV_EXAMPLE_FILE_NAME = ".env.example"
RECOMMENDED_MODEL_REPO = "HauhauCS/Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive"
RECOMMENDED_MODEL_FILE = "Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive-Q5_K_M.gguf"
LLAMA_RELEASE_API_URL = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
BOT_ENTRYPOINT = "bot.py"
LAUNCHER_EXE_NAME = "HeyMate.exe"
IS_FROZEN = bool(getattr(sys, "frozen", False))
UI_STEP_DELAY_SECONDS = 1.0
STD_INPUT_HANDLE = -10
ENABLE_INSERT_MODE = 0x0020
ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_EXTENDED_FLAGS = 0x0080


def ensure_utf8_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def enable_console_copy_paste() -> None:
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        if handle in (0, -1):
            return
        mode = ctypes.c_uint()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return
        desired_mode = mode.value | ENABLE_EXTENDED_FLAGS | ENABLE_QUICK_EDIT_MODE | ENABLE_INSERT_MODE
        kernel32.SetConsoleMode(handle, desired_mode)
    except Exception:
        return


def cls() -> None:
    os.system("cls")


def print_block(text: str) -> None:
    print(textwrap.dedent(text).strip() + "\n", flush=True)
    time.sleep(UI_STEP_DELAY_SECONDS)


def pause(prompt: str = "Нажми Enter, чтобы продолжить...") -> None:
    input(prompt)


def prompt_text(
    prompt: str,
    *,
    default: str | None = None,
    allow_empty: bool = False,
) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        if allow_empty:
            return ""
        print("Нужно что-то ввести.\n", flush=True)


def prompt_choice(title: str, options: list[str]) -> int:
    while True:
        print(title, flush=True)
        for index, option in enumerate(options, start=1):
            print(f"{index}. {option}", flush=True)
        raw = input("Выбор: ").strip()
        if raw.isdigit():
            value = int(raw)
            if 1 <= value <= len(options):
                return value
        print("Не понял выбор. Попробуй еще раз.\n", flush=True)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_error_log(project_root: Path, exc: BaseException) -> Path:
    log_path = project_root / ERROR_LOG_FILE_NAME
    log_path.write_text(
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        encoding="utf-8",
    )
    return log_path


def resolve_state_install_root(raw_value: Any) -> Path | None:
    if not raw_value:
        return None
    try:
        candidate = Path(str(raw_value)).expanduser().resolve()
    except Exception:
        return None
    if candidate.is_dir() and (candidate / BOT_ENTRYPOINT).is_file():
        return candidate
    return None


def normalize_launcher_state(project_root: Path) -> dict[str, Any]:
    state_path = project_root / STATE_FILE_NAME
    state = load_json(state_path)
    current_root_is_project = (project_root / BOT_ENTRYPOINT).is_file()
    install_root = resolve_state_install_root(state.get("install_root"))
    if install_root is not None:
        return state
    if not current_root_is_project:
        return state

    repaired_state = dict(state)
    repaired_state["installed"] = True
    repaired_state["install_root"] = str(project_root)
    launcher_copy = project_root / LAUNCHER_EXE_NAME
    if launcher_copy.is_file():
        repaired_state["launcher_copy"] = str(launcher_copy)
    save_json(state_path, repaired_state)
    return repaired_state


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def resolve_existing_file_path(
    raw_value: Any,
    project_root: Path,
    *,
    suffix: str | None = None,
) -> Path | None:
    if not raw_value:
        return None
    try:
        candidate = Path(str(raw_value)).expanduser()
        if not candidate.is_absolute():
            candidate = (project_root / candidate).resolve()
        else:
            candidate = candidate.resolve()
    except Exception:
        return None
    if not candidate.is_file():
        return None
    if suffix and candidate.suffix.lower() != suffix.lower():
        return None
    return candidate


def resolve_existing_dir_path(raw_value: Any, project_root: Path) -> Path | None:
    if not raw_value:
        return None
    try:
        candidate = Path(str(raw_value)).expanduser()
        if not candidate.is_absolute():
            candidate = (project_root / candidate).resolve()
        else:
            candidate = candidate.resolve()
    except Exception:
        return None
    if not candidate.is_dir():
        return None
    return candidate


def load_env_template(project_root: Path) -> tuple[list[str], dict[str, str]]:
    example_path = project_root / ENV_EXAMPLE_FILE_NAME
    env_path = project_root / ENV_FILE_NAME
    template_values = parse_env_file(example_path)
    current_values = parse_env_file(env_path)
    merged = dict(template_values)
    merged.update(current_values)

    order: list[str] = []
    if example_path.is_file():
        for raw_line in example_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if key and key not in order:
                order.append(key)

    for key in current_values:
        if key not in order:
            order.append(key)

    return order, merged


def write_env_file(project_root: Path, values: dict[str, str], order: list[str]) -> None:
    env_path = project_root / ENV_FILE_NAME
    output_lines: list[str] = []
    written: set[str] = set()
    for key in order:
        if key in values:
            output_lines.append(f"{key}={values[key]}")
            written.add(key)
    for key in sorted(values):
        if key not in written:
            output_lines.append(f"{key}={values[key]}")
    env_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")


def current_launcher_path() -> Path:
    if IS_FROZEN:
        return Path(sys.executable).resolve()
    return Path(__file__).resolve()


def resolve_project_root() -> Path:
    return current_launcher_path().parent


def python_command() -> list[str]:
    candidates: list[list[str]] = []
    executable_name = Path(sys.executable).name.lower()
    if not IS_FROZEN and executable_name.startswith(("python", "py")):
        candidates.append([sys.executable])
    candidates.extend(
        [
            ["py", "-3"],
            ["python"],
            ["python3"],
        ]
    )

    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        key = tuple(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            completed = subprocess.run(
                [*candidate, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except OSError:
            continue
        if completed.returncode == 0:
            return candidate

    raise RuntimeError(
        "Не удалось найти установленный Python 3. Поставь Python и перезапусти установщик."
    )


def run_command(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def is_module_installed(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def normalize_package_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def pip_installed_packages() -> set[str]:
    python = python_command()
    try:
        completed = subprocess.run(
            [*python, "-m", "pip", "list", "--format=json", "--disable-pip-version-check"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        payload = json.loads(completed.stdout or "[]")
        return {
            normalize_package_name(str(item.get("name", "")))
            for item in payload
            if isinstance(item, dict) and item.get("name")
        }
    except Exception:
        return set()


def ensure_python_dependencies(project_root: Path) -> None:
    required = {
        "aiogram": "aiogram>=3.0,<4.0",
        "aiohttp": "aiohttp>=3.9,<4.0",
    }
    installed_packages = pip_installed_packages()
    missing = [
        package
        for module, package in required.items()
        if (
            normalize_package_name(module) not in installed_packages
            and not is_module_installed(module)
        )
    ]
    if not missing:
        return

    print_block(
        """
        Я обнаружил что нету нужных для работы библиотек, сейчас все сделаю.....
        """
    )

    python = python_command()
    run_command(
        [*python, "-m", "pip", "install", "--disable-pip-version-check", *missing],
        cwd=project_root,
    )


def iter_drive_letters() -> list[str]:
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    result: list[str] = []
    for index, letter in enumerate(string.ascii_uppercase):
        if bitmask & (1 << index):
            result.append(letter)
    return result


def get_volume_label(root: str) -> str:
    volume_name_buffer = ctypes.create_unicode_buffer(1024)
    file_system_buffer = ctypes.create_unicode_buffer(1024)
    serial_number = ctypes.c_uint()
    max_component_length = ctypes.c_uint()
    file_system_flags = ctypes.c_uint()
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root),
        volume_name_buffer,
        ctypes.sizeof(volume_name_buffer),
        ctypes.byref(serial_number),
        ctypes.byref(max_component_length),
        ctypes.byref(file_system_flags),
        file_system_buffer,
        ctypes.sizeof(file_system_buffer),
    )
    if not ok:
        return ""
    return volume_name_buffer.value.strip()


def get_available_drives() -> list[dict[str, str]]:
    drives: list[dict[str, str]] = []
    for letter in iter_drive_letters():
        root = f"{letter}:\\"
        if not Path(root).exists():
            continue
        label = get_volume_label(root)
        display = f"{letter}: {label}" if label else f"{letter}: Диск"
        drives.append({"root": root, "display": display})
    return drives


def choose_install_root() -> Path:
    drives = get_available_drives()
    if not drives:
        raise RuntimeError("Не удалось найти доступные диски для установки.")
    if len(drives) == 1:
        return Path(drives[0]["root"]) / REPO_DIR_NAME

    if len(drives) == 2:
        title = "Ого, 2 диска. А ты не мелочишься :), в какую селим?"
    else:
        title = (
            "......ааааа.. братан ты че? Куда тебе столько дисков? "
            "Это компьютер или многоэтажка блин? Ну давай, товарищ управдом, "
            "сели меня в какой нибудь диск."
        )

    choice = prompt_choice(title, [drive["display"] for drive in drives])
    return Path(drives[choice - 1]["root"]) / REPO_DIR_NAME


def git_available() -> bool:
    return shutil.which("git") is not None


def download_file(url: str, destination: Path, label: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "QwenTGLauncher/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        total = int(response.headers.get("Content-Length", "0") or "0")
        written = 0
        chunk_size = 1024 * 1024
        with destination.open("wb") as handle:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                handle.write(chunk)
                written += len(chunk)
                if total > 0:
                    percent = written * 100 // total
                    print(
                        f"\r{label}: {written // (1024 * 1024)} / {total // (1024 * 1024)} MB ({percent}%)",
                        end="",
                        flush=True,
                    )
                else:
                    print(
                        f"\r{label}: {written // (1024 * 1024)} MB",
                        end="",
                        flush=True,
                    )
    print("", flush=True)


def extract_zip(zip_path: Path, target_dir: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(target_dir)


def clone_or_download_repo(target_dir: Path) -> Path:
    if (target_dir / BOT_ENTRYPOINT).is_file():
        return target_dir

    if target_dir.exists() and any(target_dir.iterdir()):
        reinstall = prompt_choice(
            "Папка для установки уже существует, но это не готовый проект. Что делаем?",
            [
                "Удаляем и ставим заново",
                "Отмена",
            ],
        )
        if reinstall != 1:
            raise RuntimeError("Установку отменили, потому что папка назначения занята.")
        shutil.rmtree(target_dir, ignore_errors=True)

    target_dir.parent.mkdir(parents=True, exist_ok=True)

    if git_available():
        run_command(["git", "clone", REPO_URL, str(target_dir)])
        if not (target_dir / BOT_ENTRYPOINT).is_file():
            raise RuntimeError("Репозиторий скачался, но bot.py в корне не найден.")
        return target_dir

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        zip_path = temp_path / "repo.zip"
        download_file(REPO_ZIP_URL, zip_path, "Качаю репозиторий")
        extract_zip(zip_path, temp_path)
        extracted_roots = [item for item in temp_path.iterdir() if item.is_dir()]
        if not extracted_roots:
            raise RuntimeError("Не удалось распаковать архив репозитория.")
        source_root = extracted_roots[0]
        shutil.copytree(source_root, target_dir, dirs_exist_ok=True)

    if not (target_dir / BOT_ENTRYPOINT).is_file():
        raise RuntimeError("Репозиторий распакован, но bot.py в корне не найден.")
    return target_dir


def find_llama_server_exe(root: Path) -> Path | None:
    try:
        root = root.resolve()
    except Exception:
        return None

    try:
        direct_candidate = root / "llama-server.exe"
        if direct_candidate.is_file():
            return direct_candidate.resolve()
    except Exception:
        return None

    try:
        for current_dir, dirnames, filenames in os.walk(root, onerror=lambda _exc: None):
            current_path = Path(current_dir)
            try:
                depth = len(current_path.relative_to(root).parts)
            except Exception:
                depth = 0
            if depth >= 5:
                dirnames[:] = []
            if "llama-server.exe" not in filenames:
                continue
            candidate = current_path / "llama-server.exe"
            try:
                if candidate.is_file():
                    return candidate.resolve()
            except Exception:
                continue
    except Exception:
        return None
    return None


def iter_common_llama_roots(project_root: Path) -> list[Path]:
    roots: list[Path] = []

    def add_candidate(candidate: Path) -> None:
        try:
            resolved = candidate.expanduser().resolve()
        except Exception:
            return
        if not resolved.exists() or not resolved.is_dir():
            return
        if resolved not in roots:
            roots.append(resolved)

    launcher_root = resolve_project_root()
    add_candidate(project_root)
    add_candidate(project_root / "llama.cpp")
    add_candidate(project_root.parent / "llama.cpp")
    add_candidate(launcher_root)
    add_candidate(launcher_root / "llama.cpp")
    add_candidate(launcher_root.parent / "llama.cpp")
    add_candidate(Path.home() / "llama.cpp")
    add_candidate(Path.home() / "Tools" / "llama.cpp")
    add_candidate(Path(r"C:\Tools\llama.cpp"))
    add_candidate(Path(r"C:\llama.cpp"))
    for drive in iter_drive_letters():
        add_candidate(Path(f"{drive}:\\Tools\\llama.cpp"))
        add_candidate(Path(f"{drive}:\\llama.cpp"))
    return roots


def find_external_llama_server_exe(project_root: Path) -> Path | None:
    env_server = os.getenv("LLAMA_SERVER_EXE", "").strip()
    if env_server:
        candidate = Path(env_server).expanduser()
        if candidate.is_file():
            return candidate.resolve()

    env_dir = os.getenv("LLAMA_CPP_DIR", "").strip()
    if env_dir:
        candidate = Path(env_dir).expanduser() / "llama-server.exe"
        if candidate.is_file():
            return candidate.resolve()

    for command in (["where", "llama-server.exe"], ["where.exe", "llama-server.exe"]):
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except OSError:
            continue
        if completed.returncode != 0:
            continue
        for raw_line in completed.stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            candidate = Path(line)
            try:
                if candidate.is_file():
                    return candidate.resolve()
            except Exception:
                continue

    for root in iter_common_llama_roots(project_root):
        nested_candidate = find_llama_server_exe(root)
        if nested_candidate is not None:
            return nested_candidate.resolve()
    return None


def iter_common_model_roots(project_root: Path) -> list[Path]:
    roots: list[Path] = []

    def add_candidate(candidate: Path) -> None:
        try:
            resolved = candidate.expanduser().resolve()
        except Exception:
            return
        if not resolved.exists():
            return
        if resolved not in roots:
            roots.append(resolved)

    add_candidate(project_root / "models")
    add_candidate(project_root)
    add_candidate(project_root.parent / "models")
    add_candidate(Path(r"C:\Models"))
    add_candidate(Path.home() / "models")
    add_candidate(Path.home() / ".cache" / "huggingface")
    add_candidate(Path.home() / "Downloads")
    return roots


def score_model_candidate(path: Path) -> tuple[int, int, str]:
    name = path.name.lower()
    score = 0
    if path.name == RECOMMENDED_MODEL_FILE:
        score += 1000
    if "qwen3.5" in name:
        score += 300
    elif "qwen" in name:
        score += 150
    if "35b" in name:
        score += 120
    if "a3b" in name:
        score += 80
    if "uncensored" in name:
        score += 40
    if "q5_k_m" in name:
        score += 90
    elif "q4_k_m" in name:
        score += 70
    elif "bf16" in name:
        score -= 25
    return (score, -len(str(path)), str(path).lower())


def model_identity_key(path: Path) -> str:
    try:
        return str(path.resolve()).lower()
    except Exception:
        return str(path).lower()


def find_external_model_path(project_root: Path) -> Path | None:
    matches = find_external_model_paths(project_root)
    if matches:
        return matches[0]
    return None


def find_external_model_paths(project_root: Path) -> list[Path]:
    env_candidate = resolve_existing_file_path(os.getenv("MODEL_PATH", "").strip(), project_root, suffix=".gguf")
    matches: list[tuple[tuple[int, int, str], Path]] = []
    seen_paths: set[str] = set()

    if env_candidate is not None:
        marker = model_identity_key(env_candidate)
        seen_paths.add(marker)
        matches.append((score_model_candidate(env_candidate), env_candidate))

    for root in iter_common_model_roots(project_root):
        if root.is_file() and root.suffix.lower() == ".gguf":
            marker = model_identity_key(root)
            if marker not in seen_paths:
                seen_paths.add(marker)
                matches.append((score_model_candidate(root), root))
            continue
        if not root.is_dir():
            continue
        for candidate in itertools.islice(root.rglob("*.gguf"), 200):
            marker = model_identity_key(candidate)
            if marker in seen_paths:
                continue
            seen_paths.add(marker)
            matches.append((score_model_candidate(candidate), candidate))

    matches.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in matches]


def format_model_choice(path: Path) -> str:
    try:
        size_gib = path.stat().st_size / (1024 ** 3)
    except OSError:
        size_gib = 0.0
    return f"{path.name} | {size_gib:.1f} GiB | {path}"


def choose_llama_asset(assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [asset for asset in assets if isinstance(asset.get("name"), str)]
    preferred_patterns = [
        ("win", "cpu", "x64", ".zip"),
        ("windows", "cpu", "x64", ".zip"),
        ("win", "x64", ".zip"),
    ]
    for patterns in preferred_patterns:
        for asset in candidates:
            name = asset["name"].lower()
            if all(pattern in name for pattern in patterns):
                return asset
    for asset in candidates:
        name = asset["name"].lower()
        if name.endswith(".zip") and "win" in name:
            return asset
    return None


def ensure_llama_runtime(project_root: Path) -> tuple[Path, Path]:
    existing = find_llama_server_exe(project_root)
    if existing is not None:
        return existing.parent, existing

    external = find_external_llama_server_exe(project_root)
    if external is not None:
        print_block(
            f"""
            Нашел уже установленный llama.cpp.
            Использую вот этот llama-server:
            {external}
            """
        )
        return external.parent, external

    llama_root = project_root / "llama.cpp"
    llama_root.mkdir(parents=True, exist_ok=True)

    request = urllib.request.Request(
        LLAMA_RELEASE_API_URL,
        headers={"User-Agent": "QwenTGLauncher/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)

    asset = choose_llama_asset(release.get("assets") or [])
    if asset is None:
        raise RuntimeError("Не удалось найти Windows-сборку llama.cpp в latest release.")

    asset_name = asset["name"]
    asset_url = asset["browser_download_url"]

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        zip_path = temp_path / asset_name
        download_file(asset_url, zip_path, "Качаю llama.cpp")
        extract_zip(zip_path, llama_root)

    executable = find_llama_server_exe(llama_root)
    if executable is None:
        raise RuntimeError("Скачал llama.cpp, но не нашел llama-server.exe после распаковки.")
    return executable.parent, executable


def huggingface_url(repo_id: str, filename: str) -> str:
    safe_filename = urllib.parse.quote(filename, safe="/")
    return f"https://huggingface.co/{repo_id}/resolve/main/{safe_filename}?download=true"


def download_model(repo_id: str, filename: str, models_dir: Path) -> Path:
    models_dir.mkdir(parents=True, exist_ok=True)
    destination = models_dir / Path(filename).name
    if destination.is_file():
        return destination
    download_file(huggingface_url(repo_id, filename), destination, "Качаю модель")
    return destination


def choose_model_path(project_root: Path) -> Path:
    models_dir = project_root / "models"
    choice = prompt_choice(
        "Теперь нам нужно будет установить модель, надо .gguf конечно. Если впадлу, "
        "мы можем установить модель которую рекомендует разработчик. Правда она весит прилично "
        "и без цензуры, так что осторожно. Или дай путь к уже готовой модели.",
        [
            "Скачать свою модель с Hugging Face",
            "Скачать рекомендуемую модель разработчика",
            "Указать путь к готовой модели",
        ],
    )

    if choice == 1:
        repo_id = prompt_text("Введи repo_id модели на Hugging Face")
        filename = prompt_text("Введи точное имя GGUF-файла")
        return download_model(repo_id, filename, models_dir)

    if choice == 2:
        return download_model(RECOMMENDED_MODEL_REPO, RECOMMENDED_MODEL_FILE, models_dir)

    detected_models = find_external_model_paths(project_root)
    if detected_models:
        print_block(
            f"""
            Я сам прошерстил диски и нашёл готовые .gguf модели.
            Сейчас покажу список, а ты уже выберешь, что ставим.
            """
        )
        options = [format_model_choice(model_path) for model_path in detected_models]
        options.append("Вбить путь вручную")
        detected_choice = prompt_choice("Какую модель ставим?", options)
        if detected_choice <= len(detected_models):
            return detected_models[detected_choice - 1]

    while True:
        raw_path = prompt_text("Введи полный путь к .gguf модели")
        model_path = resolve_existing_file_path(raw_path, project_root, suffix=".gguf")
        if model_path is not None:
            return model_path
        print("Не вижу .gguf по этому пути. Проверь и пришли еще раз.\n", flush=True)


def model_supports_fast_reply(model_path: Path) -> bool:
    name = model_path.name.lower()
    positive_markers = (
        "instruct",
        "chat",
        "assistant",
        "it",
        "coder",
        "qwen",
        "llama",
        "mistral",
        "mixtral",
        "deepseek",
        "gemma",
        "phi",
        "yi",
        "hermes",
        "zephyr",
        "dolphin",
        "nemotron",
    )
    negative_markers = ("base", "pretrain", "embedding", "rerank", "reranker")
    return any(marker in name for marker in positive_markers) or not any(
        marker in name for marker in negative_markers
    )


def model_profile_for_path(model_path: Path) -> dict[str, str]:
    name = model_path.name.lower()

    if "qwen" in name:
        chat_format = "qwen"
    elif any(marker in name for marker in ("mistral", "mixtral", "zephyr", "hermes", "openchat", "chatml")):
        chat_format = "chatml"
    else:
        chat_format = ""

    if any(marker in name for marker in ("coder", "code")):
        max_tokens = "4096"
        temperature = "0.35"
    elif any(marker in name for marker in ("instruct", "chat", "assistant", "it", "qwen", "llama", "mistral", "mixtral", "deepseek", "gemma", "phi")):
        max_tokens = "3072"
        temperature = "0.5"
    else:
        max_tokens = "2048"
        temperature = "0.6"

    if any(marker in name for marker in ("70b", "72b", "32b", "35b", "34b", "30b", "27b")):
        n_ctx = "32768"
    else:
        n_ctx = "16384"

    return {
        "CHAT_FORMAT": chat_format,
        "N_CTX": n_ctx,
        "MAX_TOKENS": max_tokens,
        "BRIEF_MAX_TOKENS": "240",
        "TEMPERATURE": temperature,
        "TOP_P": "0.95",
        "TOP_K": "20",
        "REPEAT_PENALTY": "1.1",
    }


def chat_format_for_model(model_path: Path) -> str:
    return model_profile_for_path(model_path)["CHAT_FORMAT"]


def handle_model_support(project_root: Path, current_model: Path) -> Path:
    if model_supports_fast_reply(current_model):
        print_block(
            """
            Отлично! Все готово для запуска! Перезапусти меня.
            """
        )
        return current_model

    choice = prompt_choice(
        "Братан, извини что потратил время... но я пока не могу над ним работать так, как надо, "
        "потому что модель может полезть в режим раздумия. Я могу оставить ее как есть или "
        "перевести тебя на рекомендуемую модель.",
        [
            "Оставляем текущую модель",
            "Грузим рекомендуемую модель",
        ],
    )
    if choice == 1:
        return current_model
    return download_model(
        RECOMMENDED_MODEL_REPO,
        RECOMMENDED_MODEL_FILE,
        project_root / "models",
    )


def build_default_env(project_root: Path, model_path: Path, llama_dir: Path, llama_server_exe: Path) -> tuple[list[str], dict[str, str]]:
    order, values = load_env_template(project_root)
    profile = model_profile_for_path(model_path)
    values["BOT_TOKEN"] = values.get("BOT_TOKEN", "")
    values["MODEL_PATH"] = str(model_path)
    values["LLAMA_CPP_DIR"] = str(llama_dir)
    values["LLAMA_SERVER_EXE"] = str(llama_server_exe)
    values["SOURCE_URL"] = REPO_PAGE_URL
    for key, value in profile.items():
        values[key] = value
    values.setdefault("MAX_HISTORY_MESSAGES", "10")
    values.setdefault("AI_ENABLED", "true")
    for key in (
        "CHAT_FORMAT",
        "N_CTX",
        "MAX_TOKENS",
        "BRIEF_MAX_TOKENS",
        "TEMPERATURE",
        "TOP_P",
        "TOP_K",
        "REPEAT_PENALTY",
        "AI_ENABLED",
    ):
        if key not in order:
            order.append(key)
    return order, values


def validate_history_limit(raw_value: str) -> str:
    if raw_value == "-1":
        return raw_value
    if raw_value.isdigit():
        return str(int(raw_value))
    raise ValueError("Нужно положительное целое число или -1.")


def validate_existing_env(project_root: Path, state: dict[str, Any]) -> tuple[bool, dict[str, str]]:
    env_path = project_root / ENV_FILE_NAME
    values = parse_env_file(env_path)
    if not values:
        return False, values

    bot_token = values.get("BOT_TOKEN", "").strip()
    if not bot_token:
        return False, values

    model_path_raw = values.get("MODEL_PATH", "").strip()
    if not model_path_raw:
        return False, values
    model_path = resolve_existing_file_path(model_path_raw, project_root, suffix=".gguf")
    if model_path is None:
        return False, values
    values["MODEL_PATH"] = str(model_path)

    history_value = values.get("MAX_HISTORY_MESSAGES", "10").strip()
    try:
        values["MAX_HISTORY_MESSAGES"] = validate_history_limit(history_value)
    except ValueError:
        return False, values

    llama_server_raw = values.get("LLAMA_SERVER_EXE", "").strip()
    llama_server_exe = resolve_existing_file_path(llama_server_raw, project_root, suffix=".exe")
    if llama_server_exe is None and state.get("llama_server_exe"):
        llama_server_exe = resolve_existing_file_path(state["llama_server_exe"], project_root, suffix=".exe")

    if llama_server_exe is None:
        llama_server_exe = find_external_llama_server_exe(project_root)

    if llama_server_exe is None or not llama_server_exe.is_file():
        return False, values

    values["LLAMA_SERVER_EXE"] = str(llama_server_exe)

    llama_cpp_raw = values.get("LLAMA_CPP_DIR", "").strip()
    llama_cpp_dir = resolve_existing_dir_path(llama_cpp_raw, project_root)
    if llama_cpp_dir is None:
        llama_cpp_dir = llama_server_exe.parent
    values["LLAMA_CPP_DIR"] = str(llama_cpp_dir.resolve())
    return True, values


def mark_state_configured_from_env(
    project_root: Path,
    state: dict[str, Any],
    values: dict[str, str],
) -> dict[str, Any]:
    updated_state = dict(state)
    updated_state["installed"] = True
    updated_state["configured"] = True
    updated_state["env_review_required"] = False
    updated_state["install_root"] = str(project_root)
    updated_state["model_path"] = values.get("MODEL_PATH", updated_state.get("model_path", ""))
    updated_state["llama_server_exe"] = values.get(
        "LLAMA_SERVER_EXE",
        updated_state.get("llama_server_exe", ""),
    )
    updated_state["llama_cpp_dir"] = values.get(
        "LLAMA_CPP_DIR",
        updated_state.get("llama_cpp_dir", ""),
    )
    launcher_copy = project_root / LAUNCHER_EXE_NAME
    if launcher_copy.is_file():
        updated_state["launcher_copy"] = str(launcher_copy)
    save_json(project_root / STATE_FILE_NAME, updated_state)
    return updated_state


def env_summary_lines(values: dict[str, str], ordered_keys: list[str]) -> list[str]:
    lines: list[str] = []
    for index, key in enumerate(ordered_keys, start=1):
        display_value = values.get(key, "")
        if key == "BOT_TOKEN" and display_value:
            display_value = display_value[:8] + "..." + display_value[-4:]
        lines.append(f"{index}. {key} = {display_value}")
    return lines


def configure_env(project_root: Path, state: dict[str, Any]) -> None:
    cls()
    print_block(
        """
        Добро пожаловать! Я еще и инсталлер, ахереть правда?
        Чтож, айда заполним с тобой env. Это нужно для работы модели и телеграмм бота в целом.
        """
    )

    current_env_values = parse_env_file(project_root / ENV_FILE_NAME)
    model_path = (
        resolve_existing_file_path(current_env_values.get("MODEL_PATH"), project_root, suffix=".gguf")
        or resolve_existing_file_path(state.get("model_path"), project_root, suffix=".gguf")
        or find_external_model_path(project_root)
    )
    llama_server_exe = (
        resolve_existing_file_path(current_env_values.get("LLAMA_SERVER_EXE"), project_root, suffix=".exe")
        or resolve_existing_file_path(state.get("llama_server_exe"), project_root, suffix=".exe")
        or find_external_llama_server_exe(project_root)
    )
    llama_dir = (
        resolve_existing_dir_path(current_env_values.get("LLAMA_CPP_DIR"), project_root)
        or resolve_existing_dir_path(state.get("llama_cpp_dir"), project_root)
        or (llama_server_exe.parent if llama_server_exe is not None else None)
    )

    if model_path is not None:
        state["model_path"] = str(model_path)
        print_block(
            f"""
            Я сам нашёл модель.
            Использую вот этот файл:
            {model_path}
            """
        )
    else:
        model_path = Path(prompt_text("Введи путь к модели"))

    if llama_server_exe is not None:
        state["llama_server_exe"] = str(llama_server_exe)
        if llama_dir is not None:
            state["llama_cpp_dir"] = str(llama_dir)
        print_block(
            f"""
            И llama.cpp я тоже нашёл сам.
            Использую вот этот llama-server:
            {llama_server_exe}
            """
        )
    else:
        llama_dir = Path(prompt_text("Введи путь к папке llama.cpp"))
        llama_server_exe = Path(
            state.get("llama_server_exe") or prompt_text("Введи путь к llama-server.exe")
        )

    if llama_dir is None:
        llama_dir = llama_server_exe.parent

    order, values = build_default_env(project_root, model_path, llama_dir, llama_server_exe)
    prompted_keys = [
        "BOT_TOKEN",
        "MODEL_PATH",
        "MAX_HISTORY_MESSAGES",
    ]

    explanations = {
        "BOT_TOKEN": "Это токен Telegram-бота. Просто скопируй его из BotFather и вставь.",
        "MODEL_PATH": "Это путь к .gguf модели. Если все окей, просто жми Enter и оставляй как есть.",
        "MAX_HISTORY_MESSAGES": (
            "Этот параметр отвечает за максимальный размер истории сообщений, то есть памяти. "
            "Рекомендуемое значение - 10. Безлимитный режим -1."
        ),
    }

    validators = {
        "BOT_TOKEN": lambda value: value if value else (_ for _ in ()).throw(ValueError("Токен не должен быть пустым.")),
        "MODEL_PATH": lambda value: value
        if Path(value).is_file() and Path(value).suffix.lower() == ".gguf"
        else (_ for _ in ()).throw(ValueError("Нужен путь к существующему .gguf-файлу.")),
        "MAX_HISTORY_MESSAGES": validate_history_limit,
    }

    while True:
        for key in prompted_keys:
            while True:
                print(f"{key} | {explanations[key]}", flush=True)
                try:
                    values[key] = validators[key](
                        prompt_text("Введи значение", default=values.get(key, ""))
                    )
                except ValueError as exc:
                    print(f"{exc}\n", flush=True)
                    continue
                break
            print("", flush=True)

        while True:
            cls()
            print("Такс, проверь ка пожалуйста все параметры, все ли верно.\n", flush=True)
            summary = env_summary_lines(values, prompted_keys)
            print("\n".join(summary), flush=True)
            print("", flush=True)
            choice = prompt_choice(
                "Все норм?",
                [
                    "Да, все верно",
                    "Неа, я проебался, надо подкорректировать",
                ],
            )
            if choice == 1:
                write_env_file(project_root, values, order)
                state["configured"] = True
                state["env_review_required"] = False
                save_json(project_root / STATE_FILE_NAME, state)
                print_block(
                    """
                    Отлично, запускаю все тогда.
                    """
                )
                return

            correction_choice = prompt_choice(
                "Корректируй вариант, давай!",
                summary,
            )
            key = prompted_keys[correction_choice - 1]
            while True:
                try:
                    values[key] = validators[key](
                        prompt_text("Новое значение", default=values.get(key, ""))
                    )
                except ValueError as exc:
                    print(f"{exc}\n", flush=True)
                    continue
                break


def launch_bot(project_root: Path) -> None:
    cls()
    print("Запускаю бота...\n", flush=True)
    subprocess.run([*python_command(), BOT_ENTRYPOINT], cwd=str(project_root), check=False)


def copy_launcher_to_target(project_root: Path, target_root: Path) -> Path | None:
    if not IS_FROZEN:
        return None

    source_path = current_launcher_path()
    destination_path = target_root / LAUNCHER_EXE_NAME
    if source_path != destination_path:
        shutil.copy2(source_path, destination_path)

    if project_root != target_root:
        bootstrap_state = {
            "installed": True,
            "configured": False,
            "env_review_required": True,
            "install_root": str(target_root),
            "launcher_copy": str(destination_path),
        }
        save_json(project_root / STATE_FILE_NAME, bootstrap_state)
    return destination_path


def show_env(project_root: Path) -> None:
    cls()
    env_path = project_root / ENV_FILE_NAME
    if not env_path.is_file():
        print("Файл .env пока не найден.\n", flush=True)
    else:
        print(env_path.read_text(encoding="utf-8", errors="ignore"), flush=True)
    pause()


def edit_env(project_root: Path) -> None:
    state = load_json(project_root / STATE_FILE_NAME)
    configure_env(project_root, state)
    pause()


def model_menu(project_root: Path, state: dict[str, Any]) -> None:
    cls()
    choice = prompt_choice(
        "Дарова! Что делаем с моделью?",
        [
            "Сменить или скачать модель",
            "Удалить текущую модель",
            "Назад",
        ],
    )
    if choice == 3:
        return

    if choice == 2:
        current_model = Path(state.get("model_path") or "")
        if current_model.is_file():
            try:
                current_model.unlink()
                print("Модель удалена.\n", flush=True)
            except Exception as exc:
                print(f"Не вышло удалить модель: {exc}\n", flush=True)
        else:
            print("Текущую модель не вижу, удалять нечего.\n", flush=True)
        pause()
        return

    model_path = choose_model_path(project_root)
    model_path = handle_model_support(project_root, model_path)

    state["model_path"] = str(model_path)
    state["configured"] = False
    state["env_review_required"] = True
    save_json(project_root / STATE_FILE_NAME, state)

    order, values = build_default_env(
        project_root,
        model_path,
        Path(state["llama_cpp_dir"]),
        Path(state["llama_server_exe"]),
    )
    write_env_file(project_root, values, order)
    print("Модель обновил. На следующем шаге можно править env или сразу запускаться.\n", flush=True)
    pause()


def launcher_menu(project_root: Path) -> None:
    state_path = project_root / STATE_FILE_NAME
    state = load_json(state_path)
    while True:
        cls()
        print_block(
            """
            Дарова! Нужно запустить бота? Сменить, скачать или удалить модель?
            Изменить или посмотреть env? Выбирай!
            """
        )
        choice = prompt_choice(
            "Главное меню",
            [
                "Запустить бота",
                "Сменить/Скачать/Удалить модель",
                "Посмотреть env",
                "Изменить env",
                "Выход",
            ],
        )
        if choice == 1:
            launch_bot(project_root)
        elif choice == 2:
            model_menu(project_root, state)
            state = load_json(state_path)
        elif choice == 3:
            show_env(project_root)
        elif choice == 4:
            edit_env(project_root)
            state = load_json(state_path)
        else:
            return


def first_install_flow(project_root: Path) -> None:
    cls()
    print_block(
        """
        Привет!
        Я установщик, простой и удобный! :)
        """
    )

    ensure_python_dependencies(project_root)

    print_block(
        """
        Ну... В принципе все окей у тебя.. Я могу установить этот "порт".
        Я ради прикола посажу его в корень прям. Да не ссы, потом переселишь, я не обижусь.
        """
    )

    install_root = choose_install_root()
    target_root = clone_or_download_repo(install_root)
    ensure_python_dependencies(target_root)
    llama_dir, llama_server_exe = ensure_llama_runtime(target_root)

    cls()
    print_block(
        """
        Та-дааам! Все установлено! Спасибо :3
        """
    )

    model_path = choose_model_path(target_root)
    model_path = handle_model_support(target_root, model_path)

    state = {
        "installed": True,
        "configured": False,
        "env_review_required": True,
        "install_root": str(target_root),
        "model_path": str(model_path),
        "llama_cpp_dir": str(llama_dir),
        "llama_server_exe": str(llama_server_exe),
    }
    save_json(target_root / STATE_FILE_NAME, state)
    order, values = build_default_env(target_root, model_path, llama_dir, llama_server_exe)
    write_env_file(target_root, values, order)
    launcher_copy = copy_launcher_to_target(project_root, target_root)
    restart_hint = launcher_copy if launcher_copy is not None else target_root / "install_and_launch.bat"

    print_block(
        f"""
        Отлично! Все готово для запуска! Перезапусти меня.

        На следующем запуске я уже проведу тебя по env, чтобы ты сам все проверил и подтвердил.

        И да, запускать дальше лучше уже вот отсюда:
        {restart_hint}
        """
    )
    try:
        os.startfile(str(target_root))
    except Exception:
        pass
    pause()


def resolve_runtime_project_root(project_root: Path) -> Path:
    state = normalize_launcher_state(project_root)
    install_root = resolve_state_install_root(state.get("install_root"))
    if install_root is None:
        return project_root
    return install_root


def main() -> int:
    enable_console_copy_paste()
    ensure_utf8_output()
    project_root = resolve_project_root()
    project_root = resolve_runtime_project_root(project_root)
    state = normalize_launcher_state(project_root)

    if not state.get("installed"):
        first_install_flow(project_root)
        return 0

    env_ready, env_values = validate_existing_env(project_root, state)
    if state.get("env_review_required"):
        configure_env(project_root, state)
        launch_bot(project_root)
        return 0

    if env_ready and not state.get("configured"):
        state = mark_state_configured_from_env(project_root, state, env_values)

    if not state.get("configured"):
        configure_env(project_root, state)
        launch_bot(project_root)
        return 0

    launcher_menu(project_root)
    return 0


if __name__ == "__main__":
    launcher_root = resolve_project_root()
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nОстановлено вручную.", flush=True)
    except EOFError:
        print(
            "\nЛаунчер ждёт ввод с клавиатуры. Запусти его в обычном интерактивном окне cmd или PowerShell.",
            flush=True,
        )
    except Exception as exc:
        log_path = write_error_log(launcher_root, exc)
        print(
            "\nЛаунчер словил ошибку. Подробности я сохранил сюда:\n"
            f"{log_path}\n"
            f"Коротко: {exc}",
            flush=True,
        )
        pause()

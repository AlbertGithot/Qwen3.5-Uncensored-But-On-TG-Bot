from __future__ import annotations

import importlib.util
import itertools
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


REPO_PAGE_URL = "https://github.com/AlbertGithot/ai-to-tgbot-port"
STATE_FILE_NAME = ".launcher_state.json"
ENV_FILE_NAME = ".env"
ENV_EXAMPLE_FILE_NAME = ".env.example"
RECOMMENDED_MODEL_REPO = "HauhauCS/Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive"
RECOMMENDED_MODEL_FILE = "Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive-Q5_K_M.gguf"
LLAMA_RELEASE_API_URL = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
BOT_ENTRYPOINT = "bot.py"
UI_STEP_DELAY_SECONDS = 1.0
SYSTEMD_SERVICE_NAME = "heymate-bot.service"


def ensure_utf8_output() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def cls() -> None:
    os.system("clear")


def print_block(text: str) -> None:
    print(textwrap.dedent(text).strip() + "\n", flush=True)
    time.sleep(UI_STEP_DELAY_SECONDS)


def pause(prompt: str = "Нажми Enter, чтобы продолжить...") -> None:
    input(prompt)


def prompt_text(prompt: str, *, default: str | None = None, allow_empty: bool = False) -> str:
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
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def write_env_file(project_root: Path, values: dict[str, str], order: list[str]) -> None:
    output_lines: list[str] = []
    written: set[str] = set()
    for key in order:
        if key in values:
            output_lines.append(f"{key}={values[key]}")
            written.add(key)
    for key in sorted(values):
        if key not in written:
            output_lines.append(f"{key}={values[key]}")
    (project_root / ENV_FILE_NAME).write_text("\n".join(output_lines) + "\n", encoding="utf-8")


def resolve_existing_file_path(raw_value: Any, project_root: Path, *, suffix: str | None = None) -> Path | None:
    if not raw_value:
        return None
    try:
        candidate = Path(str(raw_value)).expanduser()
        candidate = candidate if candidate.is_absolute() else (project_root / candidate).resolve()
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
        candidate = candidate if candidate.is_absolute() else (project_root / candidate).resolve()
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


def project_root() -> Path:
    return Path(__file__).resolve().parent


def python_command() -> list[str]:
    candidates = [[sys.executable], ["python3"], ["python"]]
    for candidate in candidates:
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
    raise RuntimeError("Не удалось найти установленный Python 3.")


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
        if normalize_package_name(module) not in installed_packages and not is_module_installed(module)
    ]
    if not missing:
        return

    print_block(
        """
        Я обнаружил что нету нужных для работы библиотек, сейчас все сделаю.....
        """
    )
    run_command(
        [*python_command(), "-m", "pip", "install", "--disable-pip-version-check", *missing],
        cwd=project_root,
    )


def download_file(url: str, destination: Path, label: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "HeyMateLinux/1.0"})
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
                    print(f"\r{label}: {written // (1024 * 1024)} MB", end="", flush=True)
    print("", flush=True)


def extract_archive(archive_path: Path, target_dir: Path) -> None:
    if archive_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(target_dir)
        return
    if archive_path.suffixes[-2:] == [".tar", ".gz"] or archive_path.suffix.lower() == ".tgz":
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(target_dir)
        return
    raise RuntimeError(f"Не знаю как распаковать архив: {archive_path.name}")


def iter_common_model_roots(project_root: Path) -> list[Path]:
    roots = [
        project_root / "models",
        project_root,
        project_root.parent / "models",
        Path.home() / "models",
        Path.home() / "Downloads",
        Path.home() / ".cache" / "huggingface",
        Path("/opt/models"),
        Path("/srv/models"),
        Path("/var/lib/models"),
        Path("/usr/local/share/models"),
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            resolved = root.expanduser().resolve()
        except Exception:
            continue
        if not resolved.exists():
            continue
        marker = str(resolved).lower()
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(resolved)
    return unique


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


def find_external_model_paths(project_root: Path) -> list[Path]:
    env_candidate = resolve_existing_file_path(os.getenv("MODEL_PATH", "").strip(), project_root, suffix=".gguf")
    matches: list[tuple[tuple[int, int, str], Path]] = []
    seen: set[str] = set()
    if env_candidate is not None:
        seen.add(model_identity_key(env_candidate))
        matches.append((score_model_candidate(env_candidate), env_candidate))

    for root in iter_common_model_roots(project_root):
        if root.is_file() and root.suffix.lower() == ".gguf":
            marker = model_identity_key(root)
            if marker not in seen:
                seen.add(marker)
                matches.append((score_model_candidate(root), root))
            continue
        if not root.is_dir():
            continue
        for candidate in itertools.islice(root.rglob("*.gguf"), 200):
            marker = model_identity_key(candidate)
            if marker in seen:
                continue
            seen.add(marker)
            matches.append((score_model_candidate(candidate), candidate))

    matches.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in matches]


def format_model_choice(path: Path) -> str:
    try:
        size_gib = path.stat().st_size / (1024 ** 3)
    except OSError:
        size_gib = 0.0
    return f"{path.name} | {size_gib:.1f} GiB | {path}"


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
        "Теперь надо поставить .gguf модель. Что делаем?",
        [
            "Скачать свою модель с Hugging Face",
            "Скачать рекомендуемую модель разработчика",
            "Выбрать готовую модель из найденных или вбить путь вручную",
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
            """
            Я сам прошерстил систему и нашёл готовые .gguf модели.
            Выбирай, что ставим.
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
    return any(marker in name for marker in positive_markers) or not any(marker in name for marker in negative_markers)


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

    if any(marker in name for marker in ("70b", "72b", "35b", "34b", "32b", "30b", "27b")):
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


def handle_model_support(project_root: Path, current_model: Path) -> Path:
    if model_supports_fast_reply(current_model):
        print_block(
            """
            Отлично! Эта модель выглядит адекватно для быстрого ответа.
            """
        )
        return current_model

    choice = prompt_choice(
        "Похоже, эта модель может полезть в размышления и сломать быстрый ответ. Что делаем?",
        [
            "Оставляем текущую модель",
            "Качаем рекомендуемую модель",
        ],
    )
    if choice == 1:
        return current_model
    return download_model(RECOMMENDED_MODEL_REPO, RECOMMENDED_MODEL_FILE, project_root / "models")


def find_llama_server_exe(root: Path) -> Path | None:
    try:
        direct_candidate = root.resolve() / "llama-server"
    except Exception:
        return None
    if direct_candidate.is_file():
        return direct_candidate.resolve()
    try:
        for current_dir, dirnames, filenames in os.walk(root, onerror=lambda _exc: None):
            current_path = Path(current_dir)
            try:
                depth = len(current_path.relative_to(root).parts)
            except Exception:
                depth = 0
            if depth >= 5:
                dirnames[:] = []
            if "llama-server" not in filenames:
                continue
            candidate = current_path / "llama-server"
            if candidate.is_file():
                return candidate.resolve()
    except Exception:
        return None
    return None


def iter_common_llama_roots(project_root: Path) -> list[Path]:
    roots = [
        project_root,
        project_root / "llama.cpp",
        project_root.parent / "llama.cpp",
        Path.home() / "llama.cpp",
        Path.home() / "tools" / "llama.cpp",
        Path("/opt/llama.cpp"),
        Path("/opt/llama.cpp/build/bin"),
        Path("/usr/local/bin"),
        Path("/usr/bin"),
        Path("/usr/local/llama.cpp"),
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            resolved = root.expanduser().resolve()
        except Exception:
            continue
        if not resolved.exists():
            continue
        marker = str(resolved).lower()
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(resolved)
    return unique


def find_external_llama_server_exe(project_root: Path) -> Path | None:
    env_server = os.getenv("LLAMA_SERVER_EXE", "").strip()
    if env_server:
        candidate = Path(env_server).expanduser()
        if candidate.is_file():
            return candidate.resolve()

    env_dir = os.getenv("LLAMA_CPP_DIR", "").strip()
    if env_dir:
        candidate = Path(env_dir).expanduser() / "llama-server"
        if candidate.is_file():
            return candidate.resolve()

    command = shutil.which("llama-server")
    if command:
        candidate = Path(command)
        if candidate.is_file():
            return candidate.resolve()

    for root in iter_common_llama_roots(project_root):
        found = find_llama_server_exe(root)
        if found is not None:
            return found
    return None


def choose_llama_asset(assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [asset for asset in assets if isinstance(asset.get("name"), str)]
    preferred_patterns = [
        ("linux", "x64", ".zip"),
        ("linux", "amd64", ".zip"),
        ("linux", "x64", ".tar.gz"),
        ("linux", "amd64", ".tar.gz"),
        ("ubuntu", "x64", ".zip"),
        ("ubuntu", "x64", ".tar.gz"),
    ]
    for patterns in preferred_patterns:
        for asset in candidates:
            name = asset["name"].lower()
            if all(pattern in name for pattern in patterns):
                return asset
    for asset in candidates:
        name = asset["name"].lower()
        if "linux" in name and (name.endswith(".zip") or name.endswith(".tar.gz") or name.endswith(".tgz")):
            return asset
    return None


def ensure_llama_runtime(project_root: Path) -> tuple[Path, Path]:
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
        headers={"User-Agent": "HeyMateLinux/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)

    asset = choose_llama_asset(release.get("assets") or [])
    if asset is None:
        raise RuntimeError("Не удалось найти Linux-сборку llama.cpp в latest release.")

    asset_name = asset["name"]
    asset_url = asset["browser_download_url"]
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        archive_path = temp_path / asset_name
        download_file(asset_url, archive_path, "Качаю llama.cpp")
        extract_archive(archive_path, llama_root)

    executable = find_llama_server_exe(llama_root)
    if executable is None:
        raise RuntimeError("Скачал llama.cpp, но не нашел llama-server после распаковки.")
    return executable.parent, executable


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
    values = parse_env_file(project_root / ENV_FILE_NAME)
    if not values:
        return False, values

    if not values.get("BOT_TOKEN", "").strip():
        return False, values

    model_path = resolve_existing_file_path(values.get("MODEL_PATH", "").strip(), project_root, suffix=".gguf")
    if model_path is None:
        return False, values
    values["MODEL_PATH"] = str(model_path)

    try:
        values["MAX_HISTORY_MESSAGES"] = validate_history_limit(values.get("MAX_HISTORY_MESSAGES", "10").strip())
    except ValueError:
        return False, values

    llama_server_exe = resolve_existing_file_path(values.get("LLAMA_SERVER_EXE", "").strip(), project_root)
    if llama_server_exe is None and state.get("llama_server_exe"):
        llama_server_exe = resolve_existing_file_path(state["llama_server_exe"], project_root)
    if llama_server_exe is None:
        llama_server_exe = find_external_llama_server_exe(project_root)
    if llama_server_exe is None:
        return False, values
    values["LLAMA_SERVER_EXE"] = str(llama_server_exe)

    llama_cpp_dir = resolve_existing_dir_path(values.get("LLAMA_CPP_DIR", "").strip(), project_root)
    if llama_cpp_dir is None:
        llama_cpp_dir = llama_server_exe.parent
    values["LLAMA_CPP_DIR"] = str(llama_cpp_dir)
    return True, values


def mark_state_configured_from_env(project_root: Path, state: dict[str, Any], values: dict[str, str]) -> dict[str, Any]:
    updated_state = dict(state)
    updated_state["configured"] = True
    updated_state["env_review_required"] = False
    updated_state["model_path"] = values.get("MODEL_PATH", updated_state.get("model_path", ""))
    updated_state["llama_server_exe"] = values.get("LLAMA_SERVER_EXE", updated_state.get("llama_server_exe", ""))
    updated_state["llama_cpp_dir"] = values.get("LLAMA_CPP_DIR", updated_state.get("llama_cpp_dir", ""))
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
        Добро пожаловать! На Linux я тоже могу провести тебя по env.
        Это нужно для работы модели и Telegram-бота.
        """
    )

    current_env_values = parse_env_file(project_root / ENV_FILE_NAME)
    model_path = (
        resolve_existing_file_path(current_env_values.get("MODEL_PATH"), project_root, suffix=".gguf")
        or resolve_existing_file_path(state.get("model_path"), project_root, suffix=".gguf")
        or next(iter(find_external_model_paths(project_root)), None)
    )
    llama_server_exe = (
        resolve_existing_file_path(current_env_values.get("LLAMA_SERVER_EXE"), project_root)
        or resolve_existing_file_path(state.get("llama_server_exe"), project_root)
        or find_external_llama_server_exe(project_root)
    )
    llama_dir = (
        resolve_existing_dir_path(current_env_values.get("LLAMA_CPP_DIR"), project_root)
        or resolve_existing_dir_path(state.get("llama_cpp_dir"), project_root)
        or (llama_server_exe.parent if llama_server_exe is not None else None)
    )

    if model_path is None:
        model_path = choose_model_path(project_root)
    state["model_path"] = str(model_path)

    if llama_server_exe is None:
        llama_dir, llama_server_exe = ensure_llama_runtime(project_root)
    if llama_dir is None:
        llama_dir = llama_server_exe.parent

    state["llama_server_exe"] = str(llama_server_exe)
    state["llama_cpp_dir"] = str(llama_dir)
    order, values = build_default_env(project_root, model_path, llama_dir, llama_server_exe)
    prompted_keys = ["BOT_TOKEN", "MODEL_PATH", "MAX_HISTORY_MESSAGES"]

    explanations = {
        "BOT_TOKEN": "Это токен Telegram-бота. Просто скопируй его из BotFather и вставь.",
        "MODEL_PATH": "Это путь к .gguf модели. Если все окей, просто жми Enter и оставляй как есть.",
        "MAX_HISTORY_MESSAGES": "Это размер памяти по сообщениям. Рекомендуемое значение - 10. Безлимитный режим -1.",
    }
    validators = {
        "BOT_TOKEN": lambda value: value if value else (_ for _ in ()).throw(ValueError("Токен не должен быть пустым.")),
        "MODEL_PATH": lambda value: value if Path(value).is_file() and Path(value).suffix.lower() == ".gguf" else (_ for _ in ()).throw(ValueError("Нужен путь к существующему .gguf-файлу.")),
        "MAX_HISTORY_MESSAGES": validate_history_limit,
    }

    while True:
        for key in prompted_keys:
            while True:
                print(f"{key} | {explanations[key]}", flush=True)
                try:
                    values[key] = validators[key](prompt_text("Введи значение", default=values.get(key, "")))
                except ValueError as exc:
                    print(f"{exc}\n", flush=True)
                    continue
                break
            print("", flush=True)

        while True:
            cls()
            print("Проверь параметры, все ли верно.\n", flush=True)
            summary = env_summary_lines(values, prompted_keys)
            print("\n".join(summary), flush=True)
            print("", flush=True)
            choice = prompt_choice("Все норм?", ["Да, все верно", "Нет, надо подкорректировать"])
            if choice == 1:
                write_env_file(project_root, values, order)
                state["configured"] = True
                state["env_review_required"] = False
                save_json(project_root / STATE_FILE_NAME, state)
                print_block("Отлично, запускаю все тогда.")
                return
            correction_choice = prompt_choice("Что правим?", summary)
            key = prompted_keys[correction_choice - 1]
            while True:
                try:
                    values[key] = validators[key](prompt_text("Новое значение", default=values.get(key, "")))
                except ValueError as exc:
                    print(f"{exc}\n", flush=True)
                    continue
                break


def launch_bot(project_root: Path) -> None:
    cls()
    print("Запускаю бота...\n", flush=True)
    subprocess.run([*python_command(), BOT_ENTRYPOINT], cwd=str(project_root), check=False)


def get_systemd_context() -> tuple[list[str], Path, str] | None:
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return None

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return [systemctl], Path("/etc/systemd/system") / SYSTEMD_SERVICE_NAME, "system"

    return (
        [systemctl, "--user"],
        Path.home() / ".config" / "systemd" / "user" / SYSTEMD_SERVICE_NAME,
        "user",
    )


def build_systemd_service_text(project_root: Path, mode: str) -> str:
    python_bin = python_command()[0]
    python_bin = shutil.which(python_bin) or python_bin
    bot_path = project_root / BOT_ENTRYPOINT
    wanted_by = "multi-user.target" if mode == "system" else "default.target"

    return textwrap.dedent(
        f"""
        [Unit]
        Description=HeyMate Telegram bot
        After=network-online.target
        Wants=network-online.target

        [Service]
        Type=simple
        WorkingDirectory={project_root}
        Environment=PYTHONUNBUFFERED=1
        ExecStart="{python_bin}" "{bot_path}"
        Restart=always
        RestartSec=5

        [Install]
        WantedBy={wanted_by}
        """
    ).strip() + "\n"


def install_systemd_service(project_root: Path) -> None:
    cls()
    context = get_systemd_context()
    if context is None:
        print("systemctl не найден. На этой системе некуда ставить service.\n", flush=True)
        pause()
        return

    command_prefix, service_path, mode = context
    service_path.parent.mkdir(parents=True, exist_ok=True)
    service_path.write_text(
        build_systemd_service_text(project_root, mode),
        encoding="utf-8",
    )

    daemon_reload = subprocess.run([*command_prefix, "daemon-reload"], check=False)
    enable_now = subprocess.run(
        [*command_prefix, "enable", "--now", SYSTEMD_SERVICE_NAME],
        check=False,
    )

    if daemon_reload.returncode != 0 or enable_now.returncode != 0:
        print("Не удалось включить systemd service. Проверь вывод выше.\n", flush=True)
        pause()
        return

    print(f"Service установлен: {service_path}", flush=True)
    if mode == "user":
        print(
            "Если это headless Linux-сервер, может понадобиться loginctl enable-linger $USER.\n",
            flush=True,
        )
    pause()


def show_systemd_service_status() -> None:
    cls()
    context = get_systemd_context()
    if context is None:
        print("systemctl не найден.\n", flush=True)
        pause()
        return

    command_prefix, _, _ = context
    subprocess.run(
        [*command_prefix, "status", SYSTEMD_SERVICE_NAME, "--no-pager", "--full"],
        check=False,
    )
    print("", flush=True)
    pause()


def manage_systemd_service(action: str) -> None:
    cls()
    context = get_systemd_context()
    if context is None:
        print("systemctl не найден.\n", flush=True)
        pause()
        return

    command_prefix, _, _ = context
    completed = subprocess.run(
        [*command_prefix, action, SYSTEMD_SERVICE_NAME],
        check=False,
    )
    if completed.returncode == 0:
        print(f"systemd service action completed: {action}\n", flush=True)
    else:
        print(f"Не удалось выполнить action '{action}' для systemd service.\n", flush=True)
    pause()


def show_systemd_service_logs(project_root: Path) -> None:
    cls()
    context = get_systemd_context()
    journalctl = shutil.which("journalctl")

    if context is not None and journalctl:
        command_prefix, _, mode = context
        journal_command = [journalctl]
        if mode == "user":
            journal_command.append("--user")
        journal_command.extend(
            ["-u", SYSTEMD_SERVICE_NAME, "-n", "200", "--no-pager"]
        )
        subprocess.run(journal_command, check=False)
        print("", flush=True)
        pause()
        return

    log_dir = project_root / "bot_logs"
    runtime_log = log_dir / "runtime.log"
    llama_log = log_dir / "llama_server.log"
    printed = False

    if runtime_log.is_file():
        print("=== runtime.log ===", flush=True)
        print(runtime_log.read_text(encoding="utf-8", errors="ignore")[-12000:], flush=True)
        printed = True
    if llama_log.is_file():
        if printed:
            print("", flush=True)
        print("=== llama_server.log ===", flush=True)
        print(llama_log.read_text(encoding="utf-8", errors="ignore")[-12000:], flush=True)
        printed = True
    if not printed:
        print("Логи пока не найдены.\n", flush=True)
    pause()


def remove_systemd_service() -> None:
    cls()
    context = get_systemd_context()
    if context is None:
        print("systemctl не найден.\n", flush=True)
        pause()
        return

    command_prefix, service_path, _ = context
    subprocess.run(
        [*command_prefix, "disable", "--now", SYSTEMD_SERVICE_NAME],
        check=False,
    )
    if service_path.is_file():
        service_path.unlink()
    subprocess.run([*command_prefix, "daemon-reload"], check=False)
    print("systemd service удалён.\n", flush=True)
    pause()


def setup_package(project_root: Path, state: dict[str, Any]) -> dict[str, Any]:
    cls()
    print_block(
        """
        Привет!
        Я Linux-установщик. На серверных Linux тоже можно жить нормально.
        """
    )
    ensure_python_dependencies(project_root)
    llama_dir, llama_server_exe = ensure_llama_runtime(project_root)
    model_path = choose_model_path(project_root)
    model_path = handle_model_support(project_root, model_path)
    state["configured"] = False
    state["env_review_required"] = True
    state["setup_done"] = True
    state["model_path"] = str(model_path)
    state["llama_cpp_dir"] = str(llama_dir)
    state["llama_server_exe"] = str(llama_server_exe)
    save_json(project_root / STATE_FILE_NAME, state)
    order, values = build_default_env(project_root, model_path, llama_dir, llama_server_exe)
    write_env_file(project_root, values, order)
    return state


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
        "Что делаем с моделью?",
        [
            "Сменить или скачать модель",
            "Назад",
        ],
    )
    if choice != 1:
        return
    model_path = choose_model_path(project_root)
    model_path = handle_model_support(project_root, model_path)
    state["model_path"] = str(model_path)
    state["configured"] = False
    state["env_review_required"] = True

    llama_server_exe = resolve_existing_file_path(state.get("llama_server_exe"), project_root)
    llama_cpp_dir = resolve_existing_dir_path(state.get("llama_cpp_dir"), project_root)
    if llama_server_exe is None:
        llama_cpp_dir, llama_server_exe = ensure_llama_runtime(project_root)
        state["llama_server_exe"] = str(llama_server_exe)
    if llama_cpp_dir is None:
        llama_cpp_dir = llama_server_exe.parent
        state["llama_cpp_dir"] = str(llama_cpp_dir)

    save_json(project_root / STATE_FILE_NAME, state)
    order, values = build_default_env(
        project_root,
        model_path,
        llama_cpp_dir,
        llama_server_exe,
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
            Дарова! Linux-пакет на месте.
            Нужно запустить бота, сменить модель или глянуть env?
            """
        )
        choice = prompt_choice(
            "Главное меню",
            [
                "Запустить бота",
                "Сменить или скачать модель",
                "Установить или обновить systemd service",
                "Запустить systemd service",
                "Остановить systemd service",
                "Перезапустить systemd service",
                "Посмотреть статус systemd service",
                "Посмотреть логи systemd/runtime",
                "Удалить systemd service",
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
            install_systemd_service(project_root)
        elif choice == 4:
            manage_systemd_service("start")
        elif choice == 5:
            manage_systemd_service("stop")
        elif choice == 6:
            manage_systemd_service("restart")
        elif choice == 7:
            show_systemd_service_status()
        elif choice == 8:
            show_systemd_service_logs(project_root)
        elif choice == 9:
            remove_systemd_service()
        elif choice == 10:
            show_env(project_root)
        elif choice == 11:
            edit_env(project_root)
            state = load_json(state_path)
        else:
            return


def main() -> int:
    ensure_utf8_output()
    root = project_root()
    state_path = root / STATE_FILE_NAME
    state = load_json(state_path)

    if not state.get("setup_done"):
        state = setup_package(root, state)

    env_ready, env_values = validate_existing_env(root, state)
    if env_ready and not state.get("configured") and not state.get("env_review_required"):
        state = mark_state_configured_from_env(root, state, env_values)

    if state.get("env_review_required") or not state.get("configured"):
        configure_env(root, state)
        launch_bot(root)
        return 0

    launcher_menu(root)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nОстановлено вручную.", flush=True)

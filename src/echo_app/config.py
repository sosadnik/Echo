from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import os
import socket
import sys


APP_NAME = "Echo"
APP_VERSION = "0.1.0.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
RUNTIME_OVERRIDE_KEYS = (
    "whisper_model",
    "whisper_device",
    "diarization_model",
    "diarization_device",
)


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[7:].lstrip()
    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]

    return key, value


def _iter_env_files() -> list[Path]:
    candidates: list[Path] = []
    cwd_env = Path.cwd() / ".env"
    candidates.append(cwd_env)

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / ".env")
    else:
        project_root = Path(__file__).resolve().parents[2]
        candidates.append(project_root / ".env")

    unique_candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_candidates.append(candidate)
    return unique_candidates


def load_dotenv() -> None:
    for env_file in _iter_env_files():
        if not env_file.exists():
            continue
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            parsed = _parse_dotenv_line(raw_line)
            if not parsed:
                continue
            key, value = parsed
            os.environ.setdefault(key, value)


load_dotenv()


def _read_host() -> str:
    return os.getenv("ECHO_HOST", DEFAULT_HOST)


def _read_port() -> int:
    raw = os.getenv("ECHO_PORT", str(DEFAULT_PORT))
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_PORT


def _read_provider() -> str:
    return (os.getenv("ECHO_TRANSCRIPTION_PROVIDER", "local").strip().lower() or "local")


def _read_whisper_model() -> str:
    return os.getenv("ECHO_WHISPER_MODEL", "small").strip() or "small"


def _read_whisper_device() -> str:
    return os.getenv("ECHO_WHISPER_DEVICE", "cpu").strip().lower() or "cpu"


def _read_whisper_compute_type() -> str:
    explicit = os.getenv("ECHO_WHISPER_COMPUTE_TYPE", "").strip().lower()
    if explicit:
        return explicit

    return _default_compute_type(_read_whisper_device())


def _read_diarization_model() -> str:
    return (
        os.getenv("ECHO_DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1").strip()
        or "pyannote/speaker-diarization-community-1"
    )


def _read_diarization_device() -> str:
    explicit = os.getenv("ECHO_DIARIZATION_DEVICE", "").strip().lower()
    if explicit:
        return explicit
    return _read_whisper_device()


def _read_language_hint() -> str | None:
    value = os.getenv("ECHO_LANGUAGE_HINT", "").strip()
    return value or "pl"


def _read_optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _read_hf_token() -> str | None:
    for name in ("ECHO_HF_TOKEN", "HF_TOKEN", "HUGGINGFACE_HUB_TOKEN"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def _default_compute_type(device: str) -> str:
    if device.strip().lower().startswith("cuda"):
        return "float16"
    return "int8"


def _coerce_string(value: object, default: str, *, lowercase: bool = False) -> str:
    if value is None:
        return default
    normalized = str(value).strip()
    if lowercase:
        normalized = normalized.lower()
    return normalized or default


def _coerce_optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _coerce_optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve_data_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"

    if os.name == "nt" and os.getenv("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / APP_NAME

    xdg_data_home = os.getenv("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "echo"

    return Path.home() / ".echo"


def find_free_port(host: str = DEFAULT_HOST, preferred: int = DEFAULT_PORT) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        if sock.connect_ex((host, preferred)) != 0:
            return preferred

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


@dataclass(slots=True)
class AppSettings:
    app_name: str = APP_NAME
    app_version: str = APP_VERSION
    host: str = field(default_factory=_read_host)
    port: int = field(default_factory=_read_port)
    data_root: Path = field(default_factory=resolve_data_root)
    transcription_provider: str = field(default_factory=_read_provider)
    whisper_model: str = field(default_factory=_read_whisper_model)
    whisper_device: str = field(default_factory=_read_whisper_device)
    whisper_compute_type: str = field(default_factory=_read_whisper_compute_type)
    diarization_model: str = field(default_factory=_read_diarization_model)
    diarization_device: str = field(default_factory=_read_diarization_device)
    language_hint: str | None = field(default_factory=_read_language_hint)
    min_speakers: int | None = field(default_factory=lambda: _read_optional_int("ECHO_MIN_SPEAKERS"))
    max_speakers: int | None = field(default_factory=lambda: _read_optional_int("ECHO_MAX_SPEAKERS"))
    huggingface_token: str | None = field(default_factory=_read_hf_token)
    recordings_dir: Path = field(init=False)
    playback_dir: Path = field(init=False)
    exports_dir: Path = field(init=False)
    database_path: Path = field(init=False)
    models_dir: Path = field(init=False)
    whisper_cache_dir: Path = field(init=False)
    hf_home: Path = field(init=False)
    runtime_settings_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.recordings_dir = self.data_root / "recordings"
        self.playback_dir = self.data_root / "playback"
        self.exports_dir = self.data_root / "exports"
        self.database_path = self.data_root / "echo.db"
        self.models_dir = self.data_root / "models"
        self.whisper_cache_dir = self.models_dir / "faster-whisper"
        self.hf_home = self.models_dir / "huggingface"
        self.runtime_settings_path = self.data_root / "settings.json"
        self._normalize_runtime_settings()

    def prepare(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.playback_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.whisper_cache_dir.mkdir(parents=True, exist_ok=True)
        self.hf_home.mkdir(parents=True, exist_ok=True)

        os.environ.setdefault("HF_HOME", str(self.hf_home))
        if self.huggingface_token:
            os.environ.setdefault("HF_TOKEN", self.huggingface_token)

    def load_runtime_overrides(self) -> None:
        if not self.runtime_settings_path.exists():
            return

        try:
            payload = json.loads(self.runtime_settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(payload, dict):
            return

        self.apply_runtime_overrides(payload)

    def apply_runtime_overrides(self, overrides: dict[str, object]) -> None:
        for key in RUNTIME_OVERRIDE_KEYS:
            if key not in overrides:
                continue
            setattr(self, key, overrides[key])
        self._normalize_runtime_settings()

    def runtime_overrides_payload(self) -> dict[str, object]:
        return {
            "whisper_model": self.whisper_model,
            "whisper_device": self.whisper_device,
            "diarization_model": self.diarization_model,
            "diarization_device": self.diarization_device,
        }

    def save_runtime_overrides(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.runtime_overrides_payload(), ensure_ascii=False, indent=2)
        self.runtime_settings_path.write_text(f"{payload}\n", encoding="utf-8")

    def _normalize_runtime_settings(self) -> None:
        self.whisper_model = _coerce_string(self.whisper_model, "small")
        self.whisper_device = _coerce_string(self.whisper_device, "cpu", lowercase=True)
        self.whisper_compute_type = _coerce_string(
            self.whisper_compute_type,
            _default_compute_type(self.whisper_device),
            lowercase=True,
        )
        self.diarization_model = _coerce_string(
            self.diarization_model,
            "pyannote/speaker-diarization-community-1",
        )
        self.diarization_device = _coerce_string(
            self.diarization_device,
            self.whisper_device,
            lowercase=True,
        )
        self.language_hint = _coerce_optional_string(self.language_hint)
        self.min_speakers = _coerce_optional_int(self.min_speakers)
        self.max_speakers = _coerce_optional_int(self.max_speakers)

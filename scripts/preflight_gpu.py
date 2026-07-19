#!/usr/bin/env python3
"""Preflight trwałej instancji GPU Echo; wynik jest maszynowo czytelnym JSON-em."""

from __future__ import annotations

import argparse
from importlib import metadata
import json
from pathlib import Path
import shutil
import sys


PACKAGES = ("faster-whisper", "pyannote.audio", "whisperx", "torch", "ctranslate2")


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            continue
    return versions


def _cuda_info() -> dict[str, object]:
    try:
        import torch
    except ImportError:
        return {"available": False, "reason": "Brak torch."}
    available = bool(torch.cuda.is_available())
    result: dict[str, object] = {"available": available, "cuda": str(torch.version.cuda or "unavailable")}
    if available:
        result["gpu"] = str(torch.cuda.get_device_name(0))
        result["capability"] = ".".join(str(value) for value in torch.cuda.get_device_capability(0))
    return result


def run_preflight(models_dir: Path, *, minimum_free_bytes: int = 5 * 1024**3) -> dict[str, object]:
    models_dir.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage(models_dir)
    cuda = _cuda_info()
    checks: dict[str, dict[str, object]] = {
        "python": {"ok": sys.version_info >= (3, 11), "version": sys.version.split()[0]},
        "ffmpeg": {"ok": shutil.which("ffmpeg") is not None, "path": shutil.which("ffmpeg")},
        "cuda": {"ok": bool(cuda.get("available")), **cuda},
        "disk": {
            "ok": disk.free >= minimum_free_bytes,
            "free_bytes": disk.free,
            "minimum_free_bytes": minimum_free_bytes,
        },
        "models_dir": {
            "ok": models_dir.is_dir() and models_dir.exists(),
            "path": str(models_dir),
        },
        "packages": {"ok": all(package in _package_versions() for package in PACKAGES), "versions": _package_versions()},
    }
    return {
        "status": "ok" if all(bool(check["ok"]) for check in checks.values()) else "failed",
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sprawdza gotowość GPU/ffmpeg/dysku/modeli dla Echo.")
    parser.add_argument("--models-dir", type=Path, default=Path("/data/echo/models"))
    parser.add_argument("--minimum-free-gb", type=float, default=5.0)
    args = parser.parse_args(argv)
    result = run_preflight(args.models_dir, minimum_free_bytes=int(args.minimum_free_gb * 1024**3))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Benchmark porownujacy warianty pipeline'u transkrypcji (`LocalTranscriptionProvider`).

Uruchamia transkrypcje wszystkich nagran ze wskazanego katalogu dla kazdego
podanego wariantu (model Whisper, preset filtrow ffmpeg, alignment on/off),
mierzy czas wykonania i zapisuje wyniki side-by-side do
`data/benchmarks/<timestamp>/`.

Przyklad uzycia:

    python3 scripts/benchmark_transcription.py nagrania/ \\
        --variant model=small,filter=full,align=off \\
        --variant model=large-v3-turbo,filter=light,align=on

Preset filtrow ffmpeg jest przekazywany do providera przez zmienna srodowiskowa
`ECHO_PREPARE_FILTER_PRESET` ustawiana tuz przed zbudowaniem `AppSettings` dla
danego wariantu (nie zakladamy konkretnego API `config.py` - jesli obsluga tej
zmiennej jeszcze nie istnieje, wariant po prostu nie zmieni zachowania presetu,
ale skrypt dziala niezaleznie od tego).
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from echo_app.config import AppSettings  # noqa: E402
from echo_app.transcription import LocalTranscriptionProvider, TranscriptionError  # noqa: E402


AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".ogg")
FILTER_PRESETS = ("full", "light", "none")
ALIGNMENT_VALUES = ("on", "off")

ENV_WHISPER_MODEL = "ECHO_WHISPER_MODEL"
ENV_FILTER_PRESET = "ECHO_PREPARE_FILTER_PRESET"
ENV_ALIGNMENT_ENABLED = "ECHO_ALIGNMENT_ENABLED"


class VariantParseError(ValueError):
    """Nieprawidlowy format stringa wariantu przekazanego przez `--variant`."""


@dataclass(slots=True)
class BenchmarkVariant:
    model: str
    filter_preset: str = "full"
    alignment: bool = False

    @property
    def name(self) -> str:
        align_label = "align-on" if self.alignment else "align-off"
        safe_model = re.sub(r"[^A-Za-z0-9._-]+", "-", self.model)
        return f"{safe_model}__{self.filter_preset}__{align_label}"

    def as_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "filter_preset": self.filter_preset,
            "alignment": self.alignment,
        }


def _parse_bool_flag(raw_value: str, *, field_name: str) -> bool:
    normalized = raw_value.strip().lower()
    if normalized in ("on", "true", "1", "yes"):
        return True
    if normalized in ("off", "false", "0", "no"):
        return False
    raise VariantParseError(
        f"Nieprawidlowa wartosc `{field_name}={raw_value}`. Oczekiwano on/off."
    )


def parse_variant_spec(spec: str) -> BenchmarkVariant:
    """Parsuje string `model=...,filter=...,align=...` na `BenchmarkVariant`.

    Kolejnosc pol jest dowolna; `filter` i `align` sa opcjonalne (defaulty:
    `full` i `off`). Pole `model` jest wymagane.
    """

    stripped = str(spec or "").strip()
    if not stripped:
        raise VariantParseError("Pusty opis wariantu.")

    fields: dict[str, str] = {}
    for chunk in stripped.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise VariantParseError(
                f"Nieprawidlowy fragment wariantu `{chunk}` - oczekiwano `klucz=wartosc`."
            )
        key, value = chunk.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if not key or not value:
            raise VariantParseError(
                f"Nieprawidlowy fragment wariantu `{chunk}` - klucz i wartosc nie moga byc puste."
            )
        fields[key] = value

    if "model" not in fields:
        raise VariantParseError(f"Wariant `{spec}` nie zawiera wymaganego pola `model`.")

    model = fields["model"]

    filter_preset = fields.get("filter", "full").strip().lower()
    if filter_preset not in FILTER_PRESETS:
        raise VariantParseError(
            f"Nieprawidlowy preset filtrow `{filter_preset}`. Dozwolone: {', '.join(FILTER_PRESETS)}."
        )

    align_raw = fields.get("align", "off")
    alignment = _parse_bool_flag(align_raw, field_name="align")

    known_keys = {"model", "filter", "align"}
    unknown_keys = set(fields) - known_keys
    if unknown_keys:
        raise VariantParseError(
            f"Nieznane pola wariantu: {', '.join(sorted(unknown_keys))}."
        )

    return BenchmarkVariant(model=model, filter_preset=filter_preset, alignment=alignment)


def build_variants(specs: list[str]) -> list[BenchmarkVariant]:
    """Zamienia liste stringow `--variant` na liste `BenchmarkVariant` (bez duplikatow nazw)."""

    variants: list[BenchmarkVariant] = []
    seen_names: set[str] = set()
    for spec in specs:
        variant = parse_variant_spec(spec)
        if variant.name in seen_names:
            raise VariantParseError(
                f"Zduplikowany wariant `{variant.name}` (spec: `{spec}`)."
            )
        seen_names.add(variant.name)
        variants.append(variant)
    return variants


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark_transcription.py",
        description=(
            "Porownuje warianty pipeline'u transkrypcji (model Whisper, preset filtrow "
            "ffmpeg, alignment) na nagraniach ze wskazanego katalogu."
        ),
    )
    parser.add_argument(
        "recordings_dir",
        type=Path,
        help="Katalog z nagraniami (.wav/.mp3/.m4a/.ogg) do benchmarku.",
    )
    parser.add_argument(
        "--variant",
        dest="variants",
        action="append",
        default=None,
        metavar="model=...,filter=...,align=...",
        help=(
            "Wariant do przetestowania, np. `model=small,filter=full,align=off`. "
            "Mozna podac wielokrotnie. Pole `model` jest wymagane, `filter` "
            f"({'/'.join(FILTER_PRESETS)}) i `align` (on/off) sa opcjonalne."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Katalog bazowy na wyniki benchmarku (domyslnie `data/benchmarks`).",
    )
    return parser


@dataclass(slots=True)
class BenchmarkArgs:
    recordings_dir: Path
    variants: list[BenchmarkVariant]
    output_dir: Path | None = None


def parse_args(argv: list[str] | None = None) -> BenchmarkArgs:
    parser = build_arg_parser()
    namespace = parser.parse_args(argv)

    raw_variants = namespace.variants or []
    if not raw_variants:
        parser.error("Podaj co najmniej jeden wariant przez --variant.")

    try:
        variants = build_variants(raw_variants)
    except VariantParseError as exc:
        parser.error(str(exc))
        raise  # nieosiagalne - parser.error konczy proces, ale mypy/testy lubia jawnosc

    return BenchmarkArgs(
        recordings_dir=namespace.recordings_dir,
        variants=variants,
        output_dir=namespace.output_dir,
    )


def iter_audio_files(recordings_dir: Path) -> list[Path]:
    if not recordings_dir.exists() or not recordings_dir.is_dir():
        return []
    files = [
        entry
        for entry in sorted(recordings_dir.iterdir())
        if entry.is_file() and entry.suffix.lower() in AUDIO_EXTENSIONS
    ]
    return files


def find_reference_path(audio_path: Path) -> Path | None:
    ref_path = audio_path.with_suffix("").with_suffix(".ref.txt")
    if ref_path.exists():
        return ref_path
    return None


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"\w+", text.lower(), flags=re.UNICODE) if token]


def compute_wer(reference: str, hypothesis: str) -> float | None:
    """Prosty word error rate liczony przez odleglosc edycyjna na poziomie slow.

    Zwraca None gdy referencja jest pusta (WER nieokreslony).
    """

    ref_tokens = _tokenize(reference)
    hyp_tokens = _tokenize(hypothesis)

    if not ref_tokens:
        return None

    rows = len(ref_tokens) + 1
    cols = len(hyp_tokens) + 1
    distance = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        distance[i][0] = i
    for j in range(cols):
        distance[0][j] = j

    for i in range(1, rows):
        for j in range(1, cols):
            if ref_tokens[i - 1] == hyp_tokens[j - 1]:
                distance[i][j] = distance[i - 1][j - 1]
            else:
                distance[i][j] = 1 + min(
                    distance[i - 1][j],     # usuniecie
                    distance[i][j - 1],     # wstawienie
                    distance[i - 1][j - 1],  # podstawienie
                )

    edits = distance[rows - 1][cols - 1]
    return edits / len(ref_tokens)


@dataclass(slots=True)
class VariantRunResult:
    variant: BenchmarkVariant
    audio_file: str
    duration_seconds: float
    success: bool
    error: str | None = None
    text: str = ""
    segments: list[dict[str, object]] = field(default_factory=list)
    wer: float | None = None


def _build_settings_for_variant(variant: BenchmarkVariant) -> AppSettings:
    import os

    os.environ[ENV_WHISPER_MODEL] = variant.model
    os.environ[ENV_FILTER_PRESET] = variant.filter_preset
    os.environ[ENV_ALIGNMENT_ENABLED] = "1" if variant.alignment else "0"
    return AppSettings()


async def _run_variant_on_file(
    variant: BenchmarkVariant,
    audio_path: Path,
) -> VariantRunResult:
    settings = _build_settings_for_variant(variant)
    provider = LocalTranscriptionProvider(settings)

    start = time.perf_counter()
    try:
        result = await provider.transcribe(audio_path)
    except TranscriptionError as exc:
        duration = time.perf_counter() - start
        return VariantRunResult(
            variant=variant,
            audio_file=audio_path.name,
            duration_seconds=duration,
            success=False,
            error=str(exc),
        )

    duration = time.perf_counter() - start

    wer_value: float | None = None
    ref_path = find_reference_path(audio_path)
    if ref_path is not None:
        reference_text = ref_path.read_text(encoding="utf-8")
        wer_value = compute_wer(reference_text, result.text)

    return VariantRunResult(
        variant=variant,
        audio_file=audio_path.name,
        duration_seconds=duration,
        success=True,
        text=result.text,
        segments=[segment.model_dump() for segment in result.segments],
        wer=wer_value,
    )


def _write_variant_outputs(output_dir: Path, run_result: VariantRunResult) -> None:
    audio_stem = Path(run_result.audio_file).stem
    variant_dir = output_dir / audio_stem
    variant_dir.mkdir(parents=True, exist_ok=True)

    json_path = variant_dir / f"{run_result.variant.name}.json"
    json_path.write_text(
        json.dumps(
            {
                "variant": run_result.variant.as_dict(),
                "audio_file": run_result.audio_file,
                "duration_seconds": run_result.duration_seconds,
                "success": run_result.success,
                "error": run_result.error,
                "text": run_result.text,
                "segments": run_result.segments,
                "wer": run_result.wer,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    md_lines = [
        f"# {run_result.audio_file} — wariant `{run_result.variant.name}`",
        "",
        f"- model: `{run_result.variant.model}`",
        f"- filter: `{run_result.variant.filter_preset}`",
        f"- alignment: `{'on' if run_result.variant.alignment else 'off'}`",
        f"- czas: `{run_result.duration_seconds:.2f}s`",
        f"- status: `{'OK' if run_result.success else 'BLAD'}`",
    ]
    if run_result.wer is not None:
        md_lines.append(f"- WER: `{run_result.wer:.4f}`")
    if run_result.error:
        md_lines.extend(["", "## Blad", "", run_result.error])
    else:
        md_lines.extend(["", "## Transkrypt", "", run_result.text or "_(pusty)_"])
        if run_result.segments:
            md_lines.extend(["", "## Segmenty", ""])
            for segment in run_result.segments:
                md_lines.append(
                    f"- `[{segment['start']:.2f}-{segment['end']:.2f}]` "
                    f"**{segment['speaker']}**: {segment['text']}"
                )

    md_path = variant_dir / f"{run_result.variant.name}.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")


def _write_summary(output_dir: Path, results: list[VariantRunResult]) -> None:
    summary_payload = {
        "results": [
            {
                "audio_file": r.audio_file,
                "variant": r.variant.as_dict(),
                "variant_name": r.variant.name,
                "duration_seconds": r.duration_seconds,
                "success": r.success,
                "error": r.error,
                "wer": r.wer,
            }
            for r in results
        ],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md_lines = ["# Podsumowanie benchmarku transkrypcji", "", "| Plik | Wariant | Czas [s] | Status | WER |",
                "|---|---|---|---|---|"]
    for r in results:
        status = "OK" if r.success else f"BLAD: {r.error}"
        wer_display = f"{r.wer:.4f}" if r.wer is not None else "-"
        md_lines.append(
            f"| {r.audio_file} | {r.variant.name} | {r.duration_seconds:.2f} | {status} | {wer_display} |"
        )
    (output_dir / "summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")


async def run_benchmark(args: BenchmarkArgs) -> Path:
    audio_files = iter_audio_files(args.recordings_dir)
    if not audio_files:
        raise SystemExit(f"Brak plikow audio ({', '.join(AUDIO_EXTENSIONS)}) w `{args.recordings_dir}`.")

    output_root = args.output_dir or (Path(__file__).resolve().parents[1] / "data" / "benchmarks")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[VariantRunResult] = []
    for audio_path in audio_files:
        for variant in args.variants:
            run_result = await _run_variant_on_file(variant, audio_path)
            _write_variant_outputs(output_dir, run_result)
            results.append(run_result)

    _write_summary(output_dir, results)
    return output_dir


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = asyncio.run(run_benchmark(args))
    print(f"Wyniki benchmarku zapisane w: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

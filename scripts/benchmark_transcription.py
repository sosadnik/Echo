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
from datetime import UTC, datetime
from itertools import permutations
import json
import math
from pathlib import Path
import re
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from echo_app.config import AppSettings  # noqa: E402
from echo_app.transcription import LocalTranscriptionProvider, TranscriptionError  # noqa: E402


AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".ogg")
FILTER_PRESETS = ("full", "light", "none")
ALIGNMENT_VALUES = ("on", "off")

class VariantParseError(ValueError):
    """Nieprawidlowy format stringa wariantu przekazanego przez `--variant`."""


@dataclass(slots=True)
class BenchmarkVariant:
    model: str
    filter_preset: str = "full"
    alignment: bool = False
    repeats: int = 1
    vad_threshold: float | None = None

    @property
    def name(self) -> str:
        align_label = "align-on" if self.alignment else "align-off"
        safe_model = re.sub(r"[^A-Za-z0-9._-]+", "-", self.model)
        vad_label = f"__vad-{self.vad_threshold:g}" if self.vad_threshold is not None else ""
        return f"{safe_model}__{self.filter_preset}__{align_label}{vad_label}"

    def as_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "filter_preset": self.filter_preset,
            "alignment": self.alignment,
            "repeats": self.repeats,
            "vad_threshold": self.vad_threshold,
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

    try:
        repeats = int(fields.get("repeats", "1"))
    except ValueError as exc:
        raise VariantParseError("`repeats` musi być dodatnią liczbą całkowitą.") from exc
    if repeats < 1:
        raise VariantParseError("`repeats` musi być dodatnią liczbą całkowitą.")

    vad_threshold: float | None = None
    if "vad_threshold" in fields:
        try:
            vad_threshold = float(fields["vad_threshold"])
        except ValueError as exc:
            raise VariantParseError("`vad_threshold` musi być liczbą od 0 do 1.") from exc
        if not 0 <= vad_threshold <= 1:
            raise VariantParseError("`vad_threshold` musi być liczbą od 0 do 1.")

    known_keys = {"model", "filter", "align", "repeats", "vad_threshold"}
    unknown_keys = set(fields) - known_keys
    if unknown_keys:
        raise VariantParseError(
            f"Nieznane pola wariantu: {', '.join(sorted(unknown_keys))}."
        )

    return BenchmarkVariant(
        model=model,
        filter_preset=filter_preset,
        alignment=alignment,
        repeats=repeats,
        vad_threshold=vad_threshold,
    )


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
    parser.add_argument(
        "--dataset-manifest",
        type=Path,
        default=None,
        help="JSON z `samples`: audio, scenario, reference_text oraz opcjonalne dane speakerów.",
    )
    parser.add_argument("--run-id", default=None, help="Bezpieczna nazwa runu; wymagana do wznowienia.")
    parser.add_argument("--resume", action="store_true", help="Wznów run i pomiń kompletne artefakty.")
    parser.add_argument("--warmup-runs", type=int, default=1, help="Liczba niescorowanych warm-upów per wariant.")
    return parser


@dataclass(slots=True)
class BenchmarkArgs:
    recordings_dir: Path
    variants: list[BenchmarkVariant]
    output_dir: Path | None = None
    dataset_manifest: Path | None = None
    run_id: str | None = None
    resume: bool = False
    warmup_runs: int = 1


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

    if namespace.warmup_runs < 0:
        parser.error("`--warmup-runs` nie może być ujemne.")
    if namespace.resume and not namespace.run_id:
        parser.error("`--resume` wymaga `--run-id`.")
    if namespace.run_id and re.fullmatch(r"[A-Za-z0-9._-]+", namespace.run_id) is None:
        parser.error("`--run-id` może zawierać tylko litery, cyfry, kropkę, `_` i `-`.")

    return BenchmarkArgs(
        recordings_dir=namespace.recordings_dir,
        variants=variants,
        output_dir=namespace.output_dir,
        dataset_manifest=namespace.dataset_manifest,
        run_id=namespace.run_id,
        resume=namespace.resume,
        warmup_runs=namespace.warmup_runs,
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


@dataclass(slots=True)
class DatasetSample:
    sample_id: str
    audio_path: Path
    scenario: str = "unspecified"
    reference_text: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


def _safe_name(value: str, fallback: str = "sample") -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip(".-_")
    return normalized or fallback


def load_dataset_manifest(path: Path, recordings_dir: Path) -> list[DatasetSample]:
    """Wczytuje metadane datasetu, nie kopiując prywatnego audio ani gold labels."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VariantParseError(f"Nie można odczytać manifestu datasetu `{path}`.") from exc
    samples = payload.get("samples") if isinstance(payload, dict) else None
    if not isinstance(samples, list) or not samples:
        raise VariantParseError("Manifest datasetu musi zawierać niepustą listę `samples`.")
    root = recordings_dir.resolve()
    loaded: list[DatasetSample] = []
    seen_ids: set[str] = set()
    for index, sample in enumerate(samples, start=1):
        if not isinstance(sample, dict) or not isinstance(sample.get("audio"), str):
            raise VariantParseError("Każdy sample wymaga pola tekstowego `audio`.")
        audio_path = (root / sample["audio"]).resolve()
        if root not in audio_path.parents or not audio_path.is_file():
            raise VariantParseError(f"Nieprawidłowa lub niedostępna ścieżka audio `{sample['audio']}`.")
        sample_id = _safe_name(str(sample.get("id") or audio_path.stem or f"sample-{index}"))
        if sample_id in seen_ids:
            raise VariantParseError(f"Zduplikowane ID sample `{sample_id}`.")
        seen_ids.add(sample_id)
        scenario = _safe_name(str(sample.get("scenario") or "unspecified"), "unspecified")
        reference_text = sample.get("reference_text")
        if reference_text is not None and not isinstance(reference_text, str):
            raise VariantParseError(f"`reference_text` dla `{sample_id}` musi być tekstem.")
        metadata = {key: value for key, value in sample.items() if key not in {"id", "audio", "scenario", "reference_text"}}
        loaded.append(DatasetSample(sample_id, audio_path, scenario, reference_text, metadata))
    return loaded


def build_dataset_samples(recordings_dir: Path, manifest_path: Path | None) -> list[DatasetSample]:
    if manifest_path is not None:
        return load_dataset_manifest(manifest_path, recordings_dir)
    samples: list[DatasetSample] = []
    for audio_path in iter_audio_files(recordings_dir):
        reference_path = find_reference_path(audio_path)
        reference_text = reference_path.read_text(encoding="utf-8") if reference_path else None
        samples.append(DatasetSample(_safe_name(audio_path.stem), audio_path, reference_text=reference_text))
    return samples


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


def compute_error_breakdown(reference: list[str], hypothesis: list[str]) -> dict[str, int]:
    """Minimalny backtrace Levenshteina: substitutions/deletions/insertions."""
    rows, cols = len(reference) + 1, len(hypothesis) + 1
    matrix = [[(0, 0, 0, 0) for _ in range(cols)] for _ in range(rows)]
    for index in range(1, rows):
        matrix[index][0] = (index, 0, index, 0)
    for index in range(1, cols):
        matrix[0][index] = (index, 0, 0, index)
    for row in range(1, rows):
        for column in range(1, cols):
            if reference[row - 1] == hypothesis[column - 1]:
                matrix[row][column] = matrix[row - 1][column - 1]
                continue
            candidates = [
                (matrix[row - 1][column][0] + 1, matrix[row - 1][column][1], matrix[row - 1][column][2] + 1, matrix[row - 1][column][3]),
                (matrix[row][column - 1][0] + 1, matrix[row][column - 1][1], matrix[row][column - 1][2], matrix[row][column - 1][3] + 1),
                (matrix[row - 1][column - 1][0] + 1, matrix[row - 1][column - 1][1] + 1, matrix[row - 1][column - 1][2], matrix[row - 1][column - 1][3]),
            ]
            matrix[row][column] = min(candidates, key=lambda item: item[0])
    _, substitutions, deletions, insertions = matrix[-1][-1]
    return {"substitutions": substitutions, "deletions": deletions, "insertions": insertions}


def compute_cer(reference: str, hypothesis: str) -> float | None:
    ref_chars = [character for character in reference.lower() if not character.isspace()]
    hyp_chars = [character for character in hypothesis.lower() if not character.isspace()]
    if not ref_chars:
        return None
    breakdown = compute_error_breakdown(ref_chars, hyp_chars)
    return sum(breakdown.values()) / len(ref_chars)


def _metric_na(reason: str) -> dict[str, object]:
    return {"value": None, "reason": reason}


def _speaker_texts(segments: list[dict[str, object]]) -> dict[str, str]:
    grouped: dict[str, list[str]] = {}
    for segment in segments:
        speaker = str(segment.get("speaker") or "UNKNOWN")
        grouped.setdefault(speaker, []).append(str(segment.get("text") or ""))
    return {speaker: " ".join(parts).strip() for speaker, parts in grouped.items()}


def _best_speaker_mapping(
    reference_segments: list[dict[str, object]],
    hypothesis_segments: list[dict[str, object]],
) -> tuple[dict[str, str], float | None]:
    reference_by_speaker = _speaker_texts(reference_segments)
    hypothesis_by_speaker = _speaker_texts(hypothesis_segments)
    if not reference_by_speaker or not hypothesis_by_speaker:
        return {}, None
    ref_speakers = sorted(reference_by_speaker)
    hyp_speakers = sorted(hypothesis_by_speaker)
    total_reference_words = sum(len(_tokenize(text)) for text in reference_by_speaker.values())
    if total_reference_words == 0:
        return {}, None
    padded_hypotheses = hyp_speakers + [f"__missing_{index}" for index in range(max(0, len(ref_speakers) - len(hyp_speakers)))]
    best_mapping: dict[str, str] = {}
    best_errors: int | None = None
    for assignment in permutations(padded_hypotheses, len(ref_speakers)):
        mapping = dict(zip(ref_speakers, assignment, strict=True))
        errors = 0
        for ref_speaker, hyp_speaker in mapping.items():
            breakdown = compute_error_breakdown(
                _tokenize(reference_by_speaker[ref_speaker]),
                _tokenize(hypothesis_by_speaker.get(hyp_speaker, "")),
            )
            errors += sum(breakdown.values())
        if best_errors is None or errors < best_errors:
            best_errors = errors
            best_mapping = mapping
    return best_mapping, (best_errors / total_reference_words if best_errors is not None else None)


def _active_speaker(segments: list[dict[str, object]], moment: float) -> str | None:
    for segment in segments:
        if float(segment.get("start") or 0.0) <= moment < float(segment.get("end") or 0.0):
            return str(segment.get("speaker") or "UNKNOWN")
    return None


def _speaker_time_metrics(
    reference_segments: list[dict[str, object]],
    hypothesis_segments: list[dict[str, object]],
    mapping: dict[str, str],
) -> tuple[float | None, float | None, float | None]:
    boundaries = sorted({
        float(segment.get(key) or 0.0)
        for segment in reference_segments + hypothesis_segments
        for key in ("start", "end")
    })
    total = errors = 0.0
    intersections = {speaker: 0.0 for speaker in mapping}
    unions = {speaker: 0.0 for speaker in mapping}
    for start, end in zip(boundaries, boundaries[1:]):
        duration = max(0.0, end - start)
        if duration == 0:
            continue
        moment = (start + end) / 2
        ref_speaker = _active_speaker(reference_segments, moment)
        hyp_speaker = _active_speaker(hypothesis_segments, moment)
        if ref_speaker is not None:
            total += duration
            if mapping.get(ref_speaker) != hyp_speaker:
                errors += duration
        for speaker, mapped in mapping.items():
            ref_active = ref_speaker == speaker
            hyp_active = hyp_speaker == mapped
            if ref_active and hyp_active:
                intersections[speaker] += duration
            if ref_active or hyp_active:
                unions[speaker] += duration
    der = errors / total if total > 0 else None
    jer_values = [1 - intersections[speaker] / union for speaker, union in unions.items() if union > 0]
    jer = sum(jer_values) / len(jer_values) if jer_values else None

    timestamp_errors: list[float] = []
    for ref_speaker, hyp_speaker in mapping.items():
        ref_items = [item for item in reference_segments if str(item.get("speaker")) == ref_speaker]
        hyp_items = [item for item in hypothesis_segments if str(item.get("speaker")) == hyp_speaker]
        for reference_item, hypothesis_item in zip(ref_items, hyp_items):
            timestamp_errors.extend([
                abs(float(reference_item.get("start") or 0) - float(hypothesis_item.get("start") or 0)),
                abs(float(reference_item.get("end") or 0) - float(hypothesis_item.get("end") or 0)),
            ])
    timestamp_mae = statistics.mean(timestamp_errors) if timestamp_errors else None
    return der, jer, timestamp_mae


def compute_metrics(
    *,
    reference: str | None,
    hypothesis: str,
    metadata: dict[str, object],
    hypothesis_segments: list[dict[str, object]],
) -> dict[str, object]:
    reference_text = reference or ""
    normalized_reference = " ".join(_tokenize(reference_text))
    normalized_hypothesis = " ".join(_tokenize(hypothesis))
    normalized_tokens = _tokenize(normalized_reference)
    errors = compute_error_breakdown(normalized_tokens, _tokenize(normalized_hypothesis))
    raw_reference = reference_text.split()
    raw_hypothesis = hypothesis.split()
    raw_errors = compute_error_breakdown(raw_reference, raw_hypothesis)

    required_phrases = metadata.get("required_phrases")
    recall: float | None = None
    if isinstance(required_phrases, list) and required_phrases:
        matches = sum(
            1 for phrase in required_phrases
            if " ".join(_tokenize(str(phrase))) in normalized_hypothesis
        )
        recall = matches / len(required_phrases)

    expected_silence = bool(metadata.get("expected_silence"))
    hypothesis_word_count = len(_tokenize(hypothesis))
    false_speech: dict[str, object] = {
        "applicable": expected_silence,
        "detected": expected_silence and hypothesis_word_count > 0,
        "word_count": hypothesis_word_count if expected_silence else 0,
    }

    raw_reference_segments = metadata.get("reference_segments")
    if isinstance(raw_reference_segments, list) and all(isinstance(item, dict) for item in raw_reference_segments):
        reference_segments = list(raw_reference_segments)
        mapping, cpwer = _best_speaker_mapping(reference_segments, hypothesis_segments)
        der, jer, timestamp_mae = _speaker_time_metrics(reference_segments, hypothesis_segments, mapping)
        speaker_metrics = {
            "cpwer": {"value": cpwer, "reason": None if cpwer is not None else "Brak tekstu speakerów."},
            "der": {"value": der, "reason": None if der is not None else "Brak odcinków czasowych."},
            "jer": {"value": jer, "reason": None if jer is not None else "Brak odcinków czasowych."},
            "timestamp_mae_seconds": {
                "value": timestamp_mae,
                "reason": None if timestamp_mae is not None else "Brak sparowanych segmentów.",
            },
        }
    else:
        reason = "Brak gold segmentów speakerów w manifeście datasetu."
        speaker_metrics = {name: _metric_na(reason) for name in ("cpwer", "der", "jer", "timestamp_mae_seconds")}

    return {
        "normalized_wer": (sum(errors.values()) / len(normalized_tokens)) if normalized_tokens else None,
        "raw_wer": (sum(raw_errors.values()) / len(raw_reference)) if raw_reference else None,
        "cer": compute_cer(reference_text, hypothesis),
        "errors": errors,
        "false_speech": false_speech,
        "required_phrase_recall": recall,
        "speaker": speaker_metrics,
    }


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
    cer: float | None = None
    errors: dict[str, int] | None = None
    repeat: int = 1
    phase: str = "warmed_inference"
    manifest: dict[str, object] | None = None
    sample_id: str = "sample"
    scenario: str = "unspecified"
    metrics: dict[str, object] = field(default_factory=dict)
    warnings: list[dict[str, object]] = field(default_factory=list)


def _build_settings_for_variant(variant: BenchmarkVariant) -> AppSettings:
    # Benchmark nie może mutować globalnego środowiska: każdy wariant ma własny,
    # jawny i serializowalny zestaw parametrów.
    return AppSettings(
        whisper_model=variant.model,
        asr_filter_preset=variant.filter_preset,
        alignment_enabled=variant.alignment,
    )


def _build_provider_for_variant(variant: BenchmarkVariant) -> LocalTranscriptionProvider:
    provider = LocalTranscriptionProvider(_build_settings_for_variant(variant))
    if variant.vad_threshold is not None:
        provider.vad_parameters["threshold"] = variant.vad_threshold
    return provider


async def _run_variant_on_file(
    variant: BenchmarkVariant,
    audio_path: Path,
    provider: LocalTranscriptionProvider | None = None,
    repeat: int = 1,
) -> VariantRunResult:
    reference_path = find_reference_path(audio_path)
    sample = DatasetSample(
        sample_id=_safe_name(audio_path.stem),
        audio_path=audio_path,
        reference_text=reference_path.read_text(encoding="utf-8") if reference_path else None,
    )
    return await _run_variant_on_sample(variant, sample, provider=provider, repeat=repeat)


async def _run_variant_on_sample(
    variant: BenchmarkVariant,
    sample: DatasetSample,
    provider: LocalTranscriptionProvider | None = None,
    repeat: int = 1,
    phase: str = "warmed_inference",
) -> VariantRunResult:
    provider = provider or _build_provider_for_variant(variant)

    start = time.perf_counter()
    try:
        result = await provider.transcribe(sample.audio_path)
    except Exception as exc:
        duration = time.perf_counter() - start
        return VariantRunResult(
            variant=variant,
            audio_file=sample.audio_path.name,
            duration_seconds=duration,
            success=False,
            error=f"{type(exc).__name__}: {exc}",
            repeat=repeat,
            phase=phase,
            sample_id=sample.sample_id,
            scenario=sample.scenario,
        )

    duration = time.perf_counter() - start

    result_segments = [segment.model_dump() for segment in result.segments]
    metrics = compute_metrics(
        reference=sample.reference_text,
        hypothesis=result.text,
        metadata=sample.metadata,
        hypothesis_segments=result_segments,
    )

    return VariantRunResult(
        variant=variant,
        audio_file=sample.audio_path.name,
        duration_seconds=duration,
        success=True,
        text=result.text,
        segments=result_segments,
        wer=metrics["normalized_wer"],
        cer=metrics["cer"],
        errors=metrics["errors"],
        repeat=repeat,
        phase=phase,
        manifest=result.manifest.model_dump() if result.manifest else None,
        sample_id=sample.sample_id,
        scenario=sample.scenario,
        metrics=metrics,
        warnings=[warning.model_dump() for warning in (result.manifest.warnings if result.manifest else [])],
    )


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
        temp_path = Path(file.name)
    temp_path.replace(path)


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
        file.write(value)
        temp_path = Path(file.name)
    temp_path.replace(path)


def _result_path(output_dir: Path, sample_id: str, variant_name: str, repeat: int, phase: str) -> Path:
    return output_dir / "results" / _safe_name(sample_id) / f"{_safe_name(variant_name)}__{_safe_name(phase)}-{repeat}.json"


def _write_variant_outputs(output_dir: Path, run_result: VariantRunResult) -> None:
    variant_dir = output_dir / "results" / _safe_name(run_result.sample_id)
    variant_dir.mkdir(parents=True, exist_ok=True)

    json_path = _result_path(
        output_dir, run_result.sample_id, run_result.variant.name, run_result.repeat, run_result.phase
    )
    _atomic_write_json(
        json_path,
        {
            "variant": run_result.variant.as_dict(),
            "audio_file": run_result.audio_file,
            "duration_seconds": run_result.duration_seconds,
            "success": run_result.success,
            "error": run_result.error,
            "text": run_result.text,
            "segments": run_result.segments,
            "wer": run_result.wer,
            "cer": run_result.cer,
            "errors": run_result.errors,
            "repeat": run_result.repeat,
            "phase": run_result.phase,
            "manifest": run_result.manifest,
            "sample_id": run_result.sample_id,
            "scenario": run_result.scenario,
            "metrics": run_result.metrics,
            "warnings": run_result.warnings,
        },
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

    md_path = json_path.with_suffix(".md")
    _atomic_write_text(md_path, "\n".join(md_lines) + "\n")


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def _aggregate_group(results: list[VariantRunResult]) -> dict[str, object]:
    successful = [result for result in results if result.success and result.phase == "warmed_inference"]
    durations = [result.duration_seconds for result in successful]
    wers = [float(result.metrics["normalized_wer"]) for result in successful if result.metrics.get("normalized_wer") is not None]
    cers = [float(result.metrics["cer"]) for result in successful if result.metrics.get("cer") is not None]
    return {
        "count": len(results),
        "success_count": len(successful),
        "failure_count": sum(not result.success for result in results),
        "duration_seconds": {
            "median": statistics.median(durations) if durations else None,
            "p95": _percentile(durations, 0.95),
        },
        "normalized_wer": {"median": statistics.median(wers) if wers else None},
        "cer": {"median": statistics.median(cers) if cers else None},
    }


def aggregate_results(results: list[VariantRunResult]) -> dict[str, object]:
    scenarios = sorted({result.scenario for result in results})
    variants = sorted({result.variant.name for result in results})
    return {
        "global": _aggregate_group(results),
        "scenarios": {
            scenario: _aggregate_group([result for result in results if result.scenario == scenario])
            for scenario in scenarios
        },
        "variants": {
            variant: _aggregate_group([result for result in results if result.variant.name == variant])
            for variant in variants
        },
    }


def _write_summary(output_dir: Path, results: list[VariantRunResult]) -> None:
    summary_payload = {
        "artifact_version": "benchmark-artifact/v1",
        "aggregates": aggregate_results(results),
        "results": [
            {
                "audio_file": r.audio_file,
                "variant": r.variant.as_dict(),
                "variant_name": r.variant.name,
                "duration_seconds": r.duration_seconds,
                "success": r.success,
                "error": r.error,
                "wer": r.wer,
                "cer": r.cer,
                "repeat": r.repeat,
                "phase": r.phase,
                "scenario": r.scenario,
                "metrics": r.metrics,
            }
            for r in results
        ],
    }
    _atomic_write_json(output_dir / "summary.json", summary_payload)

    md_lines = ["# Podsumowanie benchmarku transkrypcji", "", "| Plik | Wariant | Czas [s] | Status | WER |",
                "|---|---|---|---|---|"]
    for r in results:
        status = "OK" if r.success else f"BLAD: {r.error}"
        wer_display = f"{r.wer:.4f}" if r.wer is not None else "-"
        md_lines.append(
            f"| {r.audio_file} | {r.variant.name} | {r.duration_seconds:.2f} | {status} | {wer_display} |"
        )
    _atomic_write_text(output_dir / "summary.md", "\n".join(md_lines) + "\n")


def _result_from_payload(payload: dict[str, object], variant: BenchmarkVariant) -> VariantRunResult:
    return VariantRunResult(
        variant=variant,
        audio_file=str(payload.get("audio_file") or ""),
        duration_seconds=float(payload.get("duration_seconds") or 0),
        success=bool(payload.get("success")),
        error=str(payload["error"]) if payload.get("error") else None,
        text=str(payload.get("text") or ""),
        segments=list(payload.get("segments") or []),
        wer=payload.get("wer"),
        cer=payload.get("cer"),
        errors=payload.get("errors"),
        repeat=int(payload.get("repeat") or 1),
        phase=str(payload.get("phase") or "warmed_inference"),
        manifest=payload.get("manifest"),
        sample_id=str(payload.get("sample_id") or "sample"),
        scenario=str(payload.get("scenario") or "unspecified"),
        metrics=dict(payload.get("metrics") or {}),
        warnings=list(payload.get("warnings") or []),
    )


def _load_complete_result(path: Path, variant: BenchmarkVariant) -> VariantRunResult | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not payload.get("success"):
        return None
    return _result_from_payload(payload, variant)


async def run_benchmark(args: BenchmarkArgs) -> Path:
    samples = build_dataset_samples(args.recordings_dir, args.dataset_manifest)
    if not samples:
        raise SystemExit(f"Brak plikow audio ({', '.join(AUDIO_EXTENSIONS)}) w `{args.recordings_dir}`.")

    output_root = args.output_dir or (Path(__file__).resolve().parents[1] / "data" / "benchmarks")
    run_id = args.run_id or time.strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / _safe_name(run_id, "run")
    if output_dir.exists() and any(output_dir.iterdir()) and not args.resume:
        raise SystemExit(f"Run `{run_id}` już istnieje; użyj `--resume` albo innego `--run-id`.")
    output_dir.mkdir(parents=True, exist_ok=True)

    created_at = datetime.now(UTC).isoformat()
    existing_manifest_path = output_dir / "run-manifest.json"
    if args.resume and existing_manifest_path.exists():
        try:
            existing_manifest = json.loads(existing_manifest_path.read_text(encoding="utf-8"))
            created_at = str(existing_manifest.get("created_at") or created_at)
        except (OSError, json.JSONDecodeError):
            pass

    manifest_base: dict[str, object] = {
        "artifact_version": "benchmark-artifact/v1",
        "run_id": run_id,
        "created_at": created_at,
        "updated_at": datetime.now(UTC).isoformat(),
        "variants": [variant.as_dict() for variant in args.variants],
        "samples": [
            {"id": sample.sample_id, "audio": sample.audio_path.name, "scenario": sample.scenario}
            for sample in samples
        ],
        "warmup_runs": args.warmup_runs,
    }
    _atomic_write_json(
        existing_manifest_path,
        {**manifest_base, "status": "running"},
    )
    results: list[VariantRunResult] = []
    providers = {
        variant.name: _build_provider_for_variant(variant)
        for variant in args.variants
    }
    try:
        for variant in args.variants:
            provider = providers[variant.name]
            for warmup_index in range(1, args.warmup_runs + 1):
                warmup_path = _result_path(output_dir, "_warmup", variant.name, warmup_index, "warmup")
                warmup_result = _load_complete_result(warmup_path, variant) if args.resume else None
                if warmup_result is None:
                    warmup_sample = DatasetSample("_warmup", samples[0].audio_path, "warmup")
                    warmup_result = await _run_variant_on_sample(
                        variant, warmup_sample, provider=provider, repeat=warmup_index, phase="warmup"
                    )
                    _write_variant_outputs(output_dir, warmup_result)

            for sample in samples:
                for repeat in range(1, variant.repeats + 1):
                    result_path = _result_path(output_dir, sample.sample_id, variant.name, repeat, "warmed_inference")
                    run_result = _load_complete_result(result_path, variant) if args.resume else None
                    if run_result is None:
                        run_result = await _run_variant_on_sample(
                            variant,
                            sample,
                            provider=provider,
                            repeat=repeat,
                            phase="warmed_inference",
                        )
                        _write_variant_outputs(output_dir, run_result)
                    results.append(run_result)
                    _atomic_write_json(
                        existing_manifest_path,
                        {**manifest_base, "status": "running", "completed_result_count": len(results)},
                    )
    except BaseException:
        _write_summary(output_dir, results)
        _atomic_write_json(
            existing_manifest_path,
            {**manifest_base, "status": "interrupted", "completed_result_count": len(results)},
        )
        raise

    _write_summary(output_dir, results)
    failed_count = sum(not result.success for result in results)
    _atomic_write_json(
        existing_manifest_path,
        {
            **manifest_base,
            "status": "completed",
            "result_count": len(results),
            "failed_result_count": failed_count,
            "summary": "summary.json",
        },
    )
    return output_dir


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = asyncio.run(run_benchmark(args))
    print(f"Wyniki benchmarku zapisane w: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

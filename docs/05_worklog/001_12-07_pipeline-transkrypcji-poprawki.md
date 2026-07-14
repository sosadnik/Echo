# 001 — Poprawki pipeline'u transkrypcji: bug fix, model, forced alignment (12-07)

## TL;DR
Zrealizowany plan `docs/02_plans/active/01_poprawki_pipeline_transkrypcji.md` w całości poza
krokiem 5 (benchmark na realnym sprzęcie). Naprawiono crashujący bug `vad_filter=false`, zmieniono
domyślny model na `large-v3-turbo`, dodano forced alignment (`whisperx`, moduł `alignment.py`)
z fallbackiem, preset filtrów ffmpeg (`ECHO_PREPARE_FILTER_PRESET`) i skrypt benchmarku
(`scripts/benchmark_transcription.py`). 58 testów zielonych. Następny krok: przenieść plan do
`completed/` po kroku 5, albo najpierw odpalić benchmark na Pop!_OS z realnymi nagraniami.

## Co zrobione
- Krok 1: `LocalTranscriptionProvider._build_transcribe_kwargs()` — naprawiono `vad_filter=false`
  (literał `false` zamiast `False` powodował `NameError`) → `True`, dodano
  `condition_on_previous_text=False`. Test regresyjny w `tests/test_transcription_prepare.py`.
- Krok 2: domyślny `ECHO_WHISPER_MODEL=large-v3-turbo` w `config.py`, `float16`/`int8` per device
  bez zmian logiki. Pin `faster-whisper>=1.2,<2.0` w `pyproject.toml`. README/`.env.example`
  zaktualizowane. Testy w `tests/test_config_defaults.py`.
- Krok 3+4: nowy moduł `src/echo_app/alignment.py` (`ForcedAligner`, oparty o `whisperx.align()`)
  — wyrównuje słowa Whispera przez wav2vec2 (PL). Fallback do surowych timestampów przy
  wyjątku/braku zależności (log + brak crasha). Zintegrowany w `_transcribe_sync` między Whisperem
  a diarizacją, z etapem progresu `alignment` (zakresy procentów przeskalowane: whisper 14-64,
  alignment 66-74, diarization 76-96). Testy w `tests/test_alignment.py` (happy path, exception
  fallback, missing-dependency fallback, integracja z providerem).
- Strumień A (równolegle): `scripts/benchmark_transcription.py` — CLI z powtarzalnym
  `--variant model=...,filter=...,align=...`, uruchamia pipeline per plik×wariant, zapisuje
  transkrypty/czasy/WER do `data/benchmarks/<timestamp>/`. Testy tylko na parsing (bez modeli ML)
  w `tests/test_benchmark_transcription.py`.
- Strumień B (równolegle): `ECHO_PREPARE_FILTER_PRESET` (`full`/`light`/`none`) w `config.py` +
  `_resolve_prepare_audio_filter` w `transcription.py`. Domyślnie `full`. Testy rozszerzone w
  `tests/test_transcription_prepare.py`.
- Krok 6: README zaktualizowany (nowe defaulty, `ECHO_PREPARE_FILTER_PRESET`, uwaga
  Blackwell/`compute_type=float16`, sekcja o pracy przez tunel SSH z Pop!_OS), `.env.example` też.
- Dodano `whisperx>=3.1,<4.0` do extra `[local]` w `pyproject.toml`.
- Utworzono `.venv/` lokalnie (nie w gicie) z `pip install -e .`, żeby móc uruchamiać testy —
  system Python na Macu ma PEP 668 (externally-managed-environment).

## Gdzie skończyłem / kontekst
- Gałąź: `master` (bezpośrednio, bez feature branch).
- Wszystkie zmiany w working tree, **nic nie jest jeszcze zacommitowane** (patrz `git status`
  wyżej: zmienione `README.md`, `.env.example`, `pyproject.toml`, `config.py`, `transcription.py`,
  `test_transcription_prepare.py`; nowe: `alignment.py`, `benchmark_transcription.py`,
  `test_alignment.py`, `test_benchmark_transcription.py`, `test_config_defaults.py`).
- Krok 5 planu (benchmark na realnych nagraniach z dyktafonu na Pop!_OS + RTX 5070 Ti, CUDA) i
  ewentualny ADR o zmianie domyślnego presetu filtrów — **nie zrobione**, wymaga fizycznego
  dostępu do maszyny z GPU i realnych nagrań; poza zasięgiem tej sesji (Mac, bez GPU).
- Plan `docs/02_plans/active/01_poprawki_pipeline_transkrypcji.md` ma odhaczone `[x]` punkty
  1-4, 6, A, B — nieodhaczony tylko punkt 5.

## Następny krok
- [ ] Odpalić `python3 scripts/benchmark_transcription.py <katalog_nagran> --variant ...` na
      Pop!_OS (CUDA) z realnymi nagraniami z dyktafonu, porównać warianty modelu/presetu
      filtrów/alignmentu, na tej podstawie ustalić domyślny preset filtrów (ewentualny ADR w
      `docs/06_decisions/`) i odhaczyć krok 5.
- [ ] Po odhaczeniu kroku 5 przenieść plan do `docs/02_plans/completed/` (skill `docs-organizer`).
- [ ] Rozważyć `git add`/commit zmian z tej sesji (obecnie tylko w working tree).

# 01 — Poprawki pipeline'u transkrypcji (jakość + forced alignment)

> **Status: zastąpiony 2026-07-18 przez plan 03.** Checkpointy 1–4, 6 i strumienie
> A/B są historycznie wykonane, ale plan nie przeszedł końcowej weryfikacji. Jego
> otwarty checkpoint 5 (benchmark na realnych danych) przejmują checkpointy 9 i 11
> planu 03, a wszystkie otwarte kryteria końcowe przejmuje jego sekcja
> „Weryfikacja końcowa”. Ten plan jest zachowany wyłącznie jako kontekst historii.

## Kontekst

Transkrypcje nagrań z dyktafonu (polski) gubiły kwestie i myliły speakerów. Analiza
(`docs/03_reports/2026-07-11_pipeline_transkrypcji_analiza.md`) wykazała: twardy bug
`NameError` blokujący provider `local`, zbyt słaby domyślny model (`small`), wyłączony VAD,
potencjalnie szkodliwy denoise w preprocessingu oraz niedokładne word timestamps
faster-whisper psujące przypisywanie słów do speakerów. Środowisko docelowe etapu 1:
Pop!_OS + RTX 5070 Ti (Blackwell) przez tunel SSH; Mac korzysta z UI przez przeglądarkę.
Etap 2 (zdalny provider dla Maca, providerzy API) — poza zakresem tego planu.

## Cel końcowy / Definicja ukończenia

- Provider `local` wykonuje transkrypcję bez crasha (bug `false` naprawiony, pokryty testem).
- Domyślna konfiguracja: `large-v3-turbo`, `vad_filter=True`,
  `condition_on_previous_text=False`; na CUDA `float16` (Blackwell), na CPU `int8`.
- Chain filtrów ffmpeg jest konfigurowalny presetem (`full` / `light` / `none`), z decyzją
  o domyślnym presecie podjętą na podstawie benchmarku na realnych nagraniach.
- Word timestamps przechodzą przez forced alignment (wav2vec2, model PL) z fallbackiem do
  surowych timestampów przy błędzie alignmentu.
- Istnieje skrypt benchmarku porównujący warianty pipeline'u na wskazanym katalogu nagrań.
- `python3 -m unittest discover -s tests -v` — wszystkie testy zielone.

## Referencje

- Analiza: `docs/03_reports/2026-07-11_pipeline_transkrypcji_analiza.md`
- Kod: `src/echo_app/transcription.py` (pipeline), `src/echo_app/config.py` (ustawienia),
  `tests/test_transcription_prepare.py` (istniejące testy prepare)
- Zewnętrzne:
  - faster-whisper: https://github.com/SYSTRAN/faster-whisper
  - WhisperX (forced alignment): https://github.com/m-bain/whisperX
  - Model alignmentu PL (domyślny w WhisperX): `jonatasgrosman/wav2vec2-large-xlsr-53-polish`
  - Blackwell/CTranslate2 (int8 crash → float16): https://github.com/SubtitleEdit/subtitleedit/issues/10180
  - pyannote community-1: https://huggingface.co/pyannote/speaker-diarization-community-1

## Implementacja (sekwencyjna)

- [x] 1. Fix bug `NameError`: wydzielić `_build_transcribe_kwargs()` w
      `LocalTranscriptionProvider`, poprawić `false` → poprawne wartości; docelowe kwargs:
      `beam_size=5`, `vad_filter=True`, `word_timestamps=True`,
      `condition_on_previous_text=False`, `language` z `language_hint`. Test jednostkowy
      buduje kwargs i weryfikuje wartości (łapie regresję typu `false`).
- [x] 2. Zmiana domyślnego modelu na `large-v3-turbo` w `config.py`
      (`_read_whisper_model`, `_normalize_runtime_settings`); aktualizacja `README.md`
      i `.env.example`. Podbić pin `faster-whisper>=1.2` w `pyproject.toml` (CTranslate2 ≥ 4.5
      wymagane dla Blackwell). Test: domyślne `AppSettings` zwracają `large-v3-turbo`,
      `float16` dla `cuda`, `int8` dla `cpu`.
- [x] 3. Forced alignment: nowy moduł `src/echo_app/alignment.py` — po `_run_whisper`
      wyrównuje słowa przez wav2vec2 (WhisperX `align()` jako zależność w extra `[local]`
      albo bezpośrednio torchaudio forced align; decyzja przy implementacji, preferencja:
      WhisperX). Wejście: segmenty/słowa Whispera + ścieżka WAV; wyjście: `list[WordToken]`
      z poprawionymi timestampami. Przy wyjątku lub braku zależności — log + fallback do
      surowych słów (pipeline nie może się wywalić przez alignment). Testy z mockiem
      alignera: ścieżka szczęśliwa + fallback.
- [x] 4. Integracja alignmentu w `_transcribe_sync` (między Whisperem a merge) + etap
      postępu „alignment" w pasku progresu (przeskalować zakresy procentów).
- [ ] 5. Uruchomić benchmark (skrypt ze strumienia A) na realnych nagraniach z dyktafonu na
      PC (Pop!_OS, CUDA): warianty `small` vs `large-v3-turbo`, preset filtrów
      `full`/`light`/`none`, alignment on/off. Na tej podstawie ustalić domyślny preset
      filtrów i zapisać decyzję (ADR w `docs/06_decisions/`, jeśli zmieniamy default).
- [x] 6. Aktualizacja `README.md` (nowe defaulty, preset filtrów, uwaga Blackwell/float16,
      krótka sekcja o pracy przez tunel SSH) + wpis worklog.

## Strumienie niezależne (równolegle ⇄)

- [x] ⇄ A. Skrypt benchmarku `scripts/benchmark_transcription.py`: przyjmuje katalog nagrań
      i listę wariantów (model, preset filtrów, alignment on/off), uruchamia pipeline dla
      każdego wariantu, zapisuje do `data/benchmarks/` transkrypty + czasy + parametry
      (JSON/markdown, side-by-side do ręcznego A/B; opcjonalnie WER, gdy obok nagrania leży
      plik referencyjny `.ref.txt`). Bez testów integracyjnych z modelami — test tylko na
      parsowanie argumentów i składanie wariantów.
- [x] ⇄ B. Preset filtrów ffmpeg: `ECHO_PREPARE_FILTER_PRESET` (`full` = obecny chain,
      `light` = tylko `highpass=f=90,lowpass=f=7600`, `none` = bez `-af`) w `config.py` +
      użycie w `_build_prepare_audio_command`. Domyślnie `full` (do czasu benchmarku — krok 5).
      Testy: komenda ffmpeg dla każdego presetu.

Zależności: A i B są niezależne od siebie i od kroków 1–4; krok 5 wymaga A + B + 1–4.

## Strategia testów

Uruchamianie: `python3 -m unittest discover -s tests -v` (bez zależności `[local]` —
wszystko na mockach, jak dotychczas w `test_transcription_prepare.py`).

- Krok 1: test wartości kwargs (w tym `vad_filter is True`,
  `condition_on_previous_text is False`) — regresja na literały.
- Krok 2: testy defaultów `AppSettings` + compute type per device.
- Kroki 3–4: mock alignera — (a) poprawione timestampy trafiają do merge,
  (b) wyjątek alignera nie przerywa transkrypcji (fallback), (c) brak zależności
  alignmentu nie przerywa transkrypcji.
- Strumień B: `_build_prepare_audio_command` dla presetów `full`/`light`/`none`
  (obecne testy prepare rozszerzyć, nie duplikować).
- Strumień A: test składania listy wariantów benchmarku (bez odpalania modeli).
- Przypadki brzegowe: puste nagranie (words=[]), brak turn diarizacji, alignment zwraca
  mniej słów niż wejście (merge musi działać na tym, co jest).

## Weryfikacja końcowa
- [ ] Testy zakresowe dla zmiany
- [ ] Pełny zestaw testów / build / lint / typecheck właściwy dla projektu
- [ ] Kryteria akceptacji i istotne przypadki brzegowe
- [ ] Dokumentacja jest zgodna z wdrożeniem
- [ ] Brak znanych regresji i nierozwiązanych blockerów

## Wynik weryfikacji
Nie przeprowadzono.

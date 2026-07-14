# 2026-07-11 — Analiza pipeline'u transkrypcji (jakość, błędy, stan rynku)

Migawka analizy wykonanej w sesji Claude Code. Kontekst: transkrypcje nagrań z dyktafonu
(polski, długie i zaszumione pliki) często gubiły kwestie mimo preprocessingu.

## Stan implementacji

Pipeline w `src/echo_app/transcription.py` (provider `local`):

1. ffmpeg: konwersja do mono 16 kHz WAV + chain filtrów
   (`highpass=90, lowpass=7600, afftdn, speechnorm, alimiter`).
2. faster-whisper: transkrypcja z `word_timestamps=True`, domyślny model `small`.
3. pyannote `speaker-diarization-community-1`: diarizacja (aktualny model, OK).
4. Ręczne scalanie: przypisanie słów do speakerów po midpoincie słowa vs tury diarizacji,
   merge segmentów tego samego speakera z progiem 1.2 s.

## Znalezione problemy (od najcięższego)

| # | Problem | Miejsce | Skutek |
|---|---------|---------|--------|
| 1 | `"vad_filter": false` — małe `false` to `NameError` | `transcription.py:345` | Provider `local` crashuje przy każdej transkrypcji w obecnym HEAD |
| 2 | Domyślny model `small` | `config.py` | Wysoki WER na polskim; główna przyczyna gubionych kwestii |
| 3 | VAD wyłączony (intencja `False`) | `transcription.py` | Halucynacje/pomijanie mowy na cichych fragmentach dyktafonu |
| 4 | Agresywny denoise (`afftdn`, `speechnorm`) | `PREPARE_AUDIO_FILTER` | Whisper trenowany na surowym audio — denoise potrafi pogarszać WER; filtrowane audio idzie też do pyannote (embeddingi speakerów) |
| 5 | Word timestamps faster-whisper = interpolacja (±setki ms) | `_run_whisper` → `_pick_speaker_for_word` | Błędne przypisanie słów do speakerów przy szybkich wymianach; krótkie wtrącenia sklejane z cudzą wypowiedzią |
| 6 | Brak `condition_on_previous_text=False` | `_run_whisper` | Halucynacja raz zaczęta propaguje się na kolejne segmenty |
| 7 | Nakładająca się mowa ginie (natura Whispera, 1 strumień) | architektura | Część „nieuwzględnionych kwestii"; ogranicza to każde rozwiązanie single-stream |

## Stan rynku (lipiec 2026) — istotne dla projektu

- **Whisper large-v3 / large-v3-turbo** — standard jakości dla polskiego w faster-whisper;
  turbo ≈ jakość v3 przy ~4× szybszym dekodowaniu.
- **WhisperX** — forced alignment wav2vec2 po Whisperze: ±50 ms na słowie zamiast ±500 ms;
  rozwiązuje problem #5. https://github.com/m-bain/whisperX
- **NVIDIA Parakeet-TDT 0.6B v3 / Canary-1B v2** — 25 języków EU (w tym polski), word
  timestamps, bardzo szybkie; NeMo = Linux-first. Kandydat na alternatywny backend.
- **pyannote community-1** — już używany, aktualny stan open source. Lepszy tylko komercyjny
  pyannoteAI Precision-2 (API).
- **API zewnętrzne** — ElevenLabs Scribe v2 (~5% WER PL, diarizacja + timestampy w jednym
  wywołaniu, ~$0.2–0.4/h), AssemblyAI, Deepgram, Speechmatics. Dobre jako referencja
  jakości i opcjonalny provider (architektura `TranscriptionProvider` na to gotowa).

## Sprzęt użytkownika i wnioski

- **PC: RTX 5070 Ti 16 GB (Blackwell), Pop!_OS headless po SSH** — pełny stack lokalny:
  large-v3/turbo float16 + pyannote na CUDA jednocześnie; godzina audio w ~2–4 min.
  **Uwaga Blackwell:** wymagane CUDA 12.8+ i CTranslate2 ≥ 4.5; int8 na CUDA crashuje
  (`CUBLAS_STATUS_NOT_SUPPORTED`) → na GPU trzymać `float16` (config już to robi domyślnie).
- **MacBook M5 16 GB** — faster-whisper na Macu działa tylko na CPU (CTranslate2 bez Metal);
  turbo int8 użyteczne, ale pełną moc M5 (~14–18× realtime) dają backendy whisper.cpp/MLX —
  temat na osobny etap.

## Rekomendacja (przyjęta przez użytkownika)

Etapowo: **Etap 1** — fixy jakości + forced alignment + benchmark, praca na PC (Pop!_OS,
tunel SSH `ssh -L 8765:127.0.0.1:8765`). **Etap 2** (poza zakresem planu 01) — zdalny
provider transkrypcji dla Maca i/lub providerzy zewnętrzni.

Plan wdrożeniowy: `docs/02_plans/active/01_poprawki_pipeline_transkrypcji.md`.

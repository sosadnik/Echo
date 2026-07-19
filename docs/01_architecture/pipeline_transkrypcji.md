# Architektura pipeline'u transkrypcji

## Stan aktualny

Żądanie `POST /api/jobs/transcribe/{recording_id}` tworzy wpis w SQLite przez
`EchoRepository`, a `JobRunner` uruchamia zadanie `asyncio`. Provider lokalny
normalizuje wejście przez ffmpeg do mono PCM 16 kHz, wykonuje faster-whisper,
wywołuje WhisperX alignment i pyannote, a następnie scala słowa do segmentów.
Wynik jest przechowywany w `jobs.transcript_text` i `jobs.result_json`.

```text
API -> JobRunner -> EchoRepository (SQLite)
                 -> LocalTranscriptionProvider
                    -> ffmpeg -> ASR -> alignment -> diaryzacja -> merge
```

Aktualna wersja `JobRunner` tworzy zadanie na każde zgłoszenie; trwały worker,
deduplikacja i recovery zostaną dodane w checkpointach 2–4 planu 03.

## Stan docelowy

Warstwa submit zapisuje `queued`, a pojedynczy worker atomowo pobiera najstarszy
job. Przy inicjalizacji repozytorium wszystkie osierocone joby `running` są
oznaczane jako `interrupted`. Provider przekazuje wynik wraz z wersjonowanym
`PipelineManifest`; API wystawia manifest i warningi bez sekretów.

Audio neutralne (mono PCM 16 kHz) jest wspólną bazą. ASR może dostać osobny
wariant filtra, a alignment i diaryzacja domyślnie korzystają z neutralnego
wariantu. Alignment pracuje na segmentach lub ograniczonych chunkach ASR, więc
jego częściowa awaria nie usuwa tekstu całego nagrania.

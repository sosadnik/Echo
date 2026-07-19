# Specyfikacja pipeline'u transkrypcji

## Cel

Pipeline przetwarza jedno nagranie na transkrypt z segmentami i provenance wyniku.
Jest odporny na restart procesu, zewnętrzne błędy ML oraz częściowe degradacje
alignmentu i diaryzacji. Pojedyncza instancja wykonuje co najwyżej jeden ciężki
job GPU naraz.

## Stany joba

Dozwolony cykl życia to:

```text
queued -> running -> completed
                  -> failed
                  -> interrupted
```

- `queued` — job został przyjęty i czeka na workera.
- `running` — worker rozpoczął wykonanie.
- `completed` — wynik i manifest zostały atomowo zapisane.
- `failed` — nieodwracalny błąd wykonania; użytkownik może zgłosić nowy job.
- `interrupted` — proces zakończył się lub worker został bezpiecznie zatrzymany;
  wynik nie jest uznawany za kompletny i retry tworzy nowy job.

Aktywny job (`queued` lub `running`) jest unikalny dla `recording_id`. Ponowne
zgłoszenie tego samego nagrania zwraca istniejący aktywny job, nie uruchamia
drugiej inferencji.

## Kontrakty danych

### `benchmark-artifact/v1`

Każdy ukończony job i każdy wynik benchmarku może zawierać `PipelineManifest` z
`artifact_version="benchmark-artifact/v1"`. Wymagane pola: `backend`, `model`,
`effective_settings`, `device`, `compute_type`, `library_versions`. Opcjonalne,
ale zalecane pola obserwowalności to `stage_timings`, `warnings`, `word_counts`,
`audio_duration_seconds`, `realtime_factor` i `hardware`.

`StageTiming` zapisuje czas etapu w sekundach oraz flagę `cold_start`.
`PipelineWarning` ma stabilny `code`, komunikat dla człowieka i opcjonalny etap.
Manifest nie może zawierać tokenów ani innych sekretów.

### ASR

`AsrSegment` zachowuje tekst, zakres czasu i listę `AsrWord`. `AsrWord` zachowuje
tekst oraz timestampy ASR/alignmentu; `aligned=false` znaczy, że pozostawiono
timestamp ASR po częściowym fallbacku. Segmenty i słowa są źródłem prawdy dla
tekstu końcowego; interpunkcja nie może znikać wyłącznie z powodu alignmentu.

### Zgodność wsteczna

Dotychczasowy `result_json` w postaci `{ "segments": [...] }` pozostaje
odczytywalny. Brak manifestu oznacza nieznane provenance (`null`), a nie
domyślne lub wymyślone wartości.

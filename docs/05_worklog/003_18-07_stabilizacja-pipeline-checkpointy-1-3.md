# 003 — Stabilizacja pipeline'u: checkpointy 1–3 (18-07)

## TL;DR

Plan 03 pozostaje w `implementation`; checkpointy 1–3 są odhaczone i przetestowane.
Dodano kontrakt `benchmark-artifact/v1`, migrację SQLite oraz ustawienia runtime dla
alignmentu, modelu i osobnych filtrów audio. Następny krok to checkpoint 4:
trwały pojedynczy worker GPU z deduplikacją i recovery po restarcie.

## Co zrobione

- Dodano specyfikację, architekturę pipeline'u oraz ADR-0001 dla formatu artefaktów i stanów joba.
- Rozszerzono modele API i SQLite o manifest, warningi oraz dane recovery; migracja zachowuje stare `result_json`.
- Zarchiwizowano zastąpiony plan 01, wskazując mapowanie jego otwartego benchmarku na plan 03.
- Wprowadzono `alignment_enabled`, canonical `large-v3-turbo`, `compute_type=auto` z wartością efektywną oraz oddzielne presety ASR/diaryzacji w API i UI.
- Pełny zestaw: 68 testów zaliczonych, 1 pominięty (brak ffmpeg).

## Gdzie skończyłem / kontekst

Gałąź `master`, niezacommitowane zmiany w `src/echo_app/{app,config,repository,schemas,transcription}.py`, UI, testach i dokumentacji. Pierwszy otwarty punkt to 4 w `docs/02_plans/implementation/03_stabilizacja_pipeline_i_benchmarku.md`. Nie zmieniono plików przygotowanych wcześniej przez użytkownika: planu 04 ani raportów analitycznych.

## Następny krok

- [ ] Zaimplementować i przetestować pojedynczego trwałego workera GPU: FIFO, deduplikację aktywnego joba, recovery `running -> interrupted`, cancel/timeout i bezpieczny shutdown.

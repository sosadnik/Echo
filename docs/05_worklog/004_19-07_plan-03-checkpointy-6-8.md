# 004 — Plan 03: checkpointy 6–8 (19-07)

## TL;DR

Plan 03 pozostaje w `implementation`, z ukończonymi checkpointami 1–8. Dodano trwałą strukturę ASR, przypisanie speakerów przez największy overlap z `UNKNOWN` dla luk oraz manifest `benchmark-artifact/v1` zapisywany przy jobie. Następny krok to checkpoint 9: przebudowa harnessu benchmarkowego.

## Co zrobione

- ASR zachowuje tekst i segmenty jako źródło prawdy; alignment tylko aktualizuje timestampy.
- Dlarizacja degraduje się jawnie do jednego speakera z warningiem (lub kończy błąd w trybie strict); overlap i luki są konfigurowalne.
- Job zapisuje manifest, czasy etapów, RTF i warningi bez tokenów; dodano testy kontraktów, speakerów i persistence.
- Pełny zestaw: 82 testy zaliczone, 1 pominięty (brak `ffmpeg`); workflow-check i `git diff --check` zaliczone.

## Gdzie skończyłem / kontekst

Gałąź `master`, zmiany całego planu 03 są niezacommitowane. Plan: `docs/02_plans/implementation/03_stabilizacja_pipeline_i_benchmarku.md`; punkty 9–11 i strumień A pozostają otwarte. Nie wykonano benchmarku GPU ani testu kontenera, ponieważ lokalne środowisko nie ma `ffmpeg`, GPU Pop!_OS ani prywatnego datasetu.

## Następny krok

- [ ] Przebudować `scripts/benchmark_transcription.py` na artefakty `benchmark-artifact/v1`, z powtórzeniami, warm-upem, wznowieniem i metrykami WER/CER/S/D/I.

# 005 — Harness benchmarku i runtime GPU (19-07)

## TL;DR

Plan 03 pozostaje w `implementation`. Rozszerzono harness o powtórzenia, reużycie providera, atomowe artefakty, manifest datasetu i metryki WER/CER/S/D/I; runtime Docker jest localhost-only, bez reloadu w trybie stałym. Następny krok wymaga pełnego domknięcia artefaktów/metadanych harnessu, a następnie świadomego deployu i benchmarku na Pop!_OS.

## Co zrobione

- Dodano `repeats`, wielokrotne artefakty per wariant, run manifest i ustawienia wariantu bez mutowania środowiska.
- Dodano parser manifestu datasetu oraz WER, CER i rozbicie substitutions/deletions/insertions.
- Dodano `compose.dev.yaml`; produkcyjny Compose wiąże port do `127.0.0.1`, nie używa `--reload`, a `.env` jest opcjonalny dla walidacji/preflight.
- Pop!_OS osiągalny: RTX 5070 Ti, sterownik 580.173.02, Compose 2.40.3.
- Pełny zestaw: 86 testów zaliczonych, 1 pominięty (brak ffmpeg); walidator workflow i `git diff --check` zaliczone.

## Gdzie skończyłem / kontekst

Zmiany są niezacommitowane na `master`. Plan 03 nadal ma otwarte checkpointy 9–11 i strumień A, ponieważ checklisty wymagają jeszcze m.in. pełnej obsługi wznowienia oraz benchmarku na prywatnym gold secie. Nie wdrożono zmian na serwer GPU i nie uruchomiono kosztownej inferencji.

## Następny krok

- [ ] Domknąć checkpoint 9/10 (wznowienie runu, agregacja p50/p95 i metryki zależne od gold speakerów), potem przygotować commit/deploy do Pop!_OS na polecenie użytkownika.

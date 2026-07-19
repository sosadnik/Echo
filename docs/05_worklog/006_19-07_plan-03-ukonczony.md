# 006 — Plan 03 ukończony (19-07)

## TL;DR

Plan 03 został w całości zaimplementowany, zweryfikowany i przeniesiony do `completed`.
Pipeline ma trwałą kolejkę GPU i recovery, wersjonowany manifest, poprawiony alignment oraz
diaryzację, wiarygodny harness i utwardzony runtime Pop!_OS. Kontrolny benchmark GPU zakończył
144/144 wyników sukcesem; kolejnym krokiem może być plan 04 — porównywarka benchmarków i adaptery ASR.

## Co zrobione

- Domknięto checkpointy 9–11: wznowienia, powtórzenia, cold/warm timings, pełne provenance,
  metryki tekstowe i speakerowe oraz agregacje per wariant/scenariusz.
- Utwardzono obraz GPU i Compose: przypięte wersje CUDA/ML, preflight, healthcheck,
  localhost-only w trybie stałym i jawny override `compose.dev.yaml`.
- Przygotowano w prywatnym volume sześć scenariuszy i uruchomiono macierz dwóch modeli,
  dwóch filtrów i alignment on/off po trzy powtórzenia; run
  `plan03-control-20260719-r2` ma 144/144 sukcesów i 8 warm-upów.
- Weryfikacja wykryła brak commita aplikacji w manifestach kontenera bez binarki Git.
  Dodano test odtwarzający oraz fallback odczytujący `.git/HEAD`; wszystkie 152 artefakty
  drugiego przebiegu zawierają `echo_commit=f00095662acf`.
- Testy: lokalnie 97 OK i 1 pominięty bez ffmpeg; w kontenerze GPU 97 OK bez pominięć.
  Preflight GPU, E2E kolejki/deduplikacji, restart recovery, tunel SSH, blokada portu LAN,
  `git diff --check` i walidator workflow przeszły.
- Zaktualizowano README i przewodniki; plan wraz z kompletnym wynikiem weryfikacji znajduje się
  w `docs/02_plans/completed/03_stabilizacja_pipeline_i_benchmarku.md`.

## Gdzie skończyłem / kontekst

Gałąź `master`; runtime na Pop!_OS działa jako zdrowa usługa na `127.0.0.1:8765`, dostępna
przez tunel SSH. Prywatny dataset i oba runy benchmarku pozostają wyłącznie w named volume
`echo_echo-data`. Pseudo-labeli nie traktowano jako podstawy do zmiany domyślnego VAD/filtrów.

## Następny krok

- [ ] Rozpocząć plan 04: `docs/02_plans/implementation/04_porownywarka_benchmarkow_i_adaptery_asr.md`,
  wykorzystując artefakty `plan03-control-20260719-r2` jako wejście techniczne.

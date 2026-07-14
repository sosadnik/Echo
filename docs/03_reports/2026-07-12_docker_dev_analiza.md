# Analiza: Docker do pracy developerskiej (2026-07-12)

## Problem / Cel

Development Echo toczy się na dwóch maszynach: Mac (bez NVIDIA GPU, głównie UI/API na providerze
`mock`) oraz Pop!_OS z RTX 5070 Ti (Blackwell), gdzie działa ciężki pipeline
`faster-whisper + pyannote + whisperx`. Środowisko CUDA na Blackwell jest kruche (wymaga
CUDA ≥ 12.8, cuDNN 9, ctranslate2 ≥ 4.5, torch ≥ 2.7.1/cu128) i trudne do odtworzenia ręcznie.
Analiza ma rozstrzygnąć: **jaki wariant konteneryzacji ma sens dla dev workflow** — przy założeniu,
że dystrybucja końcowa to portable exe (pyinstaller), więc Docker służy *wyłącznie* wygodzie
developmentu.

## Ustalenia

Fakty z kodu istotne dla konteneryzacji:

- **Bind host**: domyślnie `127.0.0.1`, ale jest env `ECHO_HOST` (`config.py:81`) — w kontenerze
  wystarczy `ECHO_HOST=0.0.0.0`, bez zmian w kodzie.
- **Jeden katalog danych = jeden volume**: `resolve_data_root()` (`config.py:191`) na Linuksie daje
  `$XDG_DATA_HOME/echo` lub `~/.echo`; wewnątrz siedzi wszystko — nagrania, SQLite, exporty oraz
  `HF_HOME` z cache modeli (`config.py:243-263`). Named volume na ten katalog daje persystencję
  modeli między rebuildami. Dodatkowo `XDG_DATA_HOME` pozwala jawnie wskazać punkt montowania.
- **`.env` ładowany z cwd i project root** (`config.py:44-63`) — przy bind-mouncie repo działa bez
  zmian; compose może też robić `env_file: .env`.
- **Granica lekki/ciężki już istnieje**: `pyproject.toml` — baza (fastapi, uvicorn) jest lekka,
  ciężar (torch, faster-whisper, pyannote, whisperx) w extras `[local]`; przełącznik
  `ECHO_TRANSCRIPTION_PROVIDER=mock|local`. Docker powinien tę granicę odwzorować, nie dublować.
- **ffmpeg** wymagany systemowo — musi być w obrazie (`apt-get install ffmpeg`).

Ustalenia z badania wzorców zewnętrznych (solution-researcher):

- Branża stosuje oba wzorce: jeden Dockerfile + `ARG BASE_IMAGE` (speaches) albo osobne
  `Dockerfile`/`Dockerfile.gpu` (whisper-asr-webservice, tagi `latest`/`latest-gpu`).
- Baza dla Blackwell: **`nvidia/cuda:12.8.x-cudnn-runtime-ubuntu24.04`** + torch z indeksu cu128
  (nie `pytorch/pytorch` — większy i nic nie wnosi); whisperx potwierdził sm_120 na
  torch 2.7.1/cu128 + ctranslate2 ≥ 4.5.
- Dev workflow standard: bind-mount `src/` + `uvicorn --reload`, named volume na cache HF,
  `env_file: .env`; GPU w compose przez `deploy.resources.reservations.devices`
  (`driver: nvidia, capabilities: [gpu]`) lub skrót `gpus: all`.
- **Nie budować obrazu GPU na Macu**: cross-build amd64 przez QEMU na Apple Silicon jest
  wielokrotnie wolniejszy, a obraz i tak działa tylko na Pop!_OS — budować natywnie tam;
  z Maca można sterować przez `docker context create ssh://popos`.

## Rozważane podejścia

### A. Jeden Dockerfile + build-arg `BASE_IMAGE` + override/profile compose (wzorzec speaches)
- Na czym polega: `ARG BASE_IMAGE` przełącza `python:3.11-slim` (CPU/mock) vs
  `nvidia/cuda:12.8-cudnn-runtime` (GPU + extras `[local]`); wspólny `compose.yaml`,
  GPU w `compose.override.yaml` per maszyna.
- Zalety: jeden plik; mapuje się 1:1 na extras z pyproject.
- Wady / koszt: warunkowa logika w Dockerfile (indeks torch CPU vs cu128) krucha; łatwo zbudować
  zły wariant bez jawnego arga; cache warstw i tak rozjeżdża się między wariantami.

### B. Dwa osobne Dockerfile (CPU i GPU) + dwa compose (wzorzec whisper-asr-webservice)
- Na czym polega: `Dockerfile` (CPU) i `Dockerfile.gpu` utrzymywane osobno.
- Zalety: zero warunkowej magii, każdy plik prosty; wariant GPU ewoluuje niezależnie.
- Wady / koszt: duplikacja przy każdej zmianie zależności/entrypointu; dwa artefakty do pilnowania
  w jednoosobowym projekcie.

### C. Docker tylko dla wariantu GPU na Pop!_OS; Mac zostaje natywny (venv + mock)
- Na czym polega: jeden `Dockerfile` GPU (baza `nvidia/cuda:12.8-cudnn-runtime-ubuntu24.04`,
  instalacja `.[local]` z indeksem cu128, ffmpeg) + `compose.yaml` z bind-mountem kodu,
  `uvicorn --reload`, named volume na dane/cache modeli i sekcją GPU. Budowany i uruchamiany
  natywnie na Pop!_OS; Mac dalej `pip install -e .` + `ECHO_TRANSCRIPTION_PROVIDER=mock`.
- Zalety: najmniej plików i pojęć; zero problemu cross-arch; kontener rozwiązuje *jedyny realny*
  problem (reprodukowalne CUDA/cudnn na Blackwell); środowisko Mac i tak musi istnieć natywnie
  (pyinstaller buduje się na platformie docelowej).
- Wady / koszt: brak „jednego polecenia" stawiającego całość na dowolnej maszynie; nowy deweloper
  na Linuksie bez GPU nie dostaje gotowego wariantu CPU.

### D. (ortogonalne) `docker compose watch` zamiast czystego bind-mountu
- Na czym polega: `develop.watch` z `action: sync` dla `src/echo_app/` i `action: rebuild` dla
  `pyproject.toml`.
- Zalety: jawny podział kod=sync / zależności=rebuild.
- Wady / koszt: dodatkowy nawyk (`up --watch`); bind-mount + `--reload` prostszy i wystarczający
  dla jednoosobowego projektu.

## Rekomendacja

**Podejście C z elementami A**: jeden `Dockerfile` GPU (baza
`nvidia/cuda:12.8-cudnn-runtime-ubuntu24.04`, ffmpeg, instalacja `.[local]` z indeksem cu128)
+ `compose.yaml` z bind-mountem kodu, `uvicorn --reload`, named volume na katalog danych
(`XDG_DATA_HOME` → cache modeli przeżywa rebuild), `env_file: .env`, sekcja GPU
(`deploy.resources.reservations.devices`). Budowa i uruchamianie natywnie na Pop!_OS
(opcjonalnie sterowanie z Maca przez `docker context ssh://`). Mac pozostaje przy natywnym venv
z providerem `mock` — dublowanie lekkiego środowiska w kontenerze to koszt bez korzyści.

Decyzja jest łatwo odwracalna (czysto dodatkowe pliki dev, zero zmian w kodzie aplikacji) —
ADR niewymagany.

## Referencje

- Kod: `src/echo_app/config.py` (host/port, data_root, HF_HOME, dotenv), `pyproject.toml`
  (extras `[local]`), `README.md` (sekcja Blackwell i tunel SSH)
- Zewnętrzne:
  - speaches — Dockerfile (BASE_IMAGE, uv, cache HF): https://github.com/speaches-ai/speaches/blob/master/Dockerfile
  - whisper-asr-webservice (Dockerfile + Dockerfile.gpu): https://github.com/ahmetoner/whisper-asr-webservice
  - Blackwell wymagania (CUDA 12.8, torch 2.7.1, ctranslate2 ≥ 4.5): https://github.com/pluja/whishper/issues/172
  - GPU w Compose: https://docs.docker.com/compose/how-tos/gpu-support/
  - buildx na Apple Silicon (powolny cross-build): https://github.com/docker/buildx/issues/1539

## Otwarte pytania

- [ ] Czy dodać też lekki wariant CPU/mock (Dockerfile z `python:3.11-slim`) dla symetrii
      środowisk na Macu / dla ewentualnych kolejnych deweloperów? (Rekomendacja: nie teraz —
      dodać, gdy pojawi się realna potrzeba.)
- [ ] `uv` vs `pip` w obrazie — `uv` przyspiesza build, ale wprowadza nowe narzędzie do projektu,
      który dziś używa `pip`. (Rekomendacja: zostać przy `pip` z cache mount.)

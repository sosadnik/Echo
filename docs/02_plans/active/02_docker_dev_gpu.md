# 02 — Docker dev (GPU) dla pipeline'u Echo na serwerze popos

## Kontekst

Ciężki pipeline (`faster-whisper` + `pyannote` + `whisperx`) wymaga na RTX 5070 Ti (Blackwell)
kruchego zestawu CUDA ≥ 12.8 / cuDNN 9 / ctranslate2 ≥ 4.5 / torch cu128 — kontener czyni to
środowisko reprodukowalnym. Zgodnie z rekomendacją analizy
(`docs/03_reports/2026-07-12_docker_dev_analiza.md`, podejście C z elementami A):
**Docker tylko dla wariantu GPU na serwerze popos**; Mac pozostaje przy natywnym venv
z providerem `mock`. Infrastruktura serwera jest gotowa i opisana w
`docs/04_guides/serwer_gpu_popos.md` (Docker 29 + Compose v2 + nvidia-container-toolkit
zweryfikowane smoke-testem `--gpus all nvidia-smi`).

Docker służy wyłącznie wygodzie developmentu — dystrybucja końcowa pozostaje pyinstaller
(bez zmian w `scripts/build_windows.bat`).

## Cel końcowy / Definicja ukończenia

Na serwerze popos `docker compose up` buduje i uruchamia Echo tak, że:

1. Web UI/API odpowiada na `:8765` (z Maca przez tunel SSH),
2. transkrypcja realnego pliku audio przechodzi end-to-end na `device=cuda`
   (whisper + diarizacja + forced alignment),
3. edycja pliku w `src/echo_app/` na serwerze → auto-reload bez rebuildu,
4. pobrane modele przeżywają `docker compose down` i rebuild obrazu (named volume),
5. testy jednostkowe przechodzą w kontenerze
   (`docker compose run --rm echo python3 -m unittest discover -s tests -v`),
6. workflow dev (sync kodu Mac→popos, uruchamianie, logi) jest udokumentowany.

## Referencje

- Analiza: `docs/03_reports/2026-07-12_docker_dev_analiza.md` (rekomendacja + wzorce)
- Infrastruktura: `docs/04_guides/serwer_gpu_popos.md` (dostęp, GPU-in-Docker zweryfikowane)
- Kod: `src/echo_app/config.py` — `ECHO_HOST` (bind `0.0.0.0` w kontenerze),
  `resolve_data_root()` → `XDG_DATA_HOME` (punkt montowania named volume; wewnątrz siedzi
  wszystko: nagrania, SQLite, `HF_HOME` z cache modeli), dotenv z project root
- Kod: `pyproject.toml` — extras `[local]` (granica lekki/ciężki), `src/echo_app/main.py`
  i `app.py:create_app` (entrypoint uvicorn)
- Zewnętrzne: speaches Dockerfile (https://github.com/speaches-ai/speaches/blob/master/Dockerfile),
  GPU w Compose (https://docs.docker.com/compose/how-tos/gpu-support/),
  wymagania Blackwell (https://github.com/pluja/whishper/issues/172)

## Checklista (sekwencyjna)

- [x] 1. **`Dockerfile` + `.dockerignore`** — baza `nvidia/cuda:12.8.*-cudnn-runtime-ubuntu24.04`;
      apt: `python3`, `python3-pip`, `python3-venv`, `ffmpeg`; instalacja `-e .[local]`
      z indeksem torch cu128 (`--extra-index-url https://download.pytorch.org/whl/cu128`),
      z cache mountem pip; `ENV ECHO_HOST=0.0.0.0`, `XDG_DATA_HOME=/data`;
      `.dockerignore` wyklucza `.git`, `.venv`, `__pycache__`, `dist`, `docs`, dane audio.
      Weryfikacja: obraz buduje się na popos (`docker build`).
- [x] 2. **`compose.yaml`** — serwis `echo`: build z kroku 1, port `8765:8765`,
      bind-mount repo → `/app` (reload kodu), named volume `echo-data:/data`
      (modele/nagrania/DB przeżywają rebuild), `env_file: .env` (HF_TOKEN),
      `ECHO_WHISPER_DEVICE=cuda`, GPU przez `deploy.resources.reservations.devices`
      (`driver: nvidia`, `capabilities: [gpu]`), command:
      `uvicorn echo_app.app:create_app --factory --reload --host 0.0.0.0 --port 8765`.
      Weryfikacja: `docker compose config` przechodzi; kontener startuje i widzi GPU
      (`docker compose exec echo nvidia-smi`).
- [ ] 3. **Uruchomienie na popos** — repo już sklonowane w `~/Documents/Git/Echo`
      (origin: github.com/sosadnik/Echo.git; wymaga `git pull` po wypchnięciu plików
      z kroków 1–2); `.env` z `HF_TOKEN` **już istnieje** na serwerze;
      `docker compose up -d`; API odpowiada
      (`curl 127.0.0.1:8765` na popos i przez tunel z Maca); testy jednostkowe
      w kontenerze zielone; edycja pliku w `src/` → widoczny auto-reload w logach.
- [ ] 4. **Smoke test GPU end-to-end** — nagranie testowe:
      `~/Documents/Git/Echo/V20260314-170105.WAV` na popos (kopia na Macu:
      `samples/V20260314-170105.WAV`, katalog w `.gitignore`); upload przez API/UI,
      job transkrypcji kończy się sukcesem na `cuda` (float16), wynik zawiera segmenty
      z diarizacją; w logach brak fallbacków na CPU; po `docker compose down && up`
      modele nie pobierają się ponownie (volume działa).
- [ ] 5. ⇄ **Dokumentacja** — README: sekcja „Development w Dockerze (serwer GPU)"
      (build, up, logi, testy, tunel); `docs/04_guides/serwer_gpu_popos.md`: workflow
      iteracji (Mac: `git push` → popos: `git pull`, compose restart nie jest potrzebny
      przy zmianach w `src/` dzięki `--reload`).

## Strumienie niezależne (równolegle ⇄)

- [ ] ⇄ A. Krok 5 (dokumentacja) może iść równolegle z krokiem 4 (smoke test GPU) —
      po ukończeniu kroków 1–3, gdy kształt plików jest już ustalony.

## Strategia testów

- **Jednostkowe (regresja)**: istniejący zestaw `python3 -m unittest discover -s tests -v`
  musi przechodzić (a) natywnie na Macu — pilnuje, że zmiany nie psują wariantu mock/exe,
  (b) w kontenerze na popos — pilnuje kompletności obrazu (ffmpeg, zależności).
  Nowe pliki (`Dockerfile`, `compose.yaml`) nie wymagają testów unittest — ich „testem"
  są weryfikacje w checkpointach (build, config, start, GPU widoczne).
- **Integracyjne (checkpoint 3)**: start kontenera + `curl` health + auto-reload.
- **End-to-end (checkpoint 4)**: realna transkrypcja na GPU — kryteria: job `done`,
  segmenty z ≥ 1 speakerem, brak logów fallbacku CPU/alignment-failure, czas znacząco
  krótszy niż CPU (sanity, bez formalnego progu — benchmark to krok 5 planu `01`).
- **Przypadki brzegowe**: brak `HF_TOKEN` w `.env` (czytelny błąd joba diarizacji, nie crash
  backendu); restart kontenera w trakcie joba (job w stanie failed/pending po powrocie,
  backend wstaje czysto).

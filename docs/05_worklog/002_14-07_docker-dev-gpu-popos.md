# 002 — Docker dev (GPU) na popos (14-07)

## TL;DR

Plan `02_docker_dev_gpu` w 100% zrealizowany i przeniesiony do `completed/`. Na serwerze `popos`
(RTX 5070 Ti) działa `docker compose` z pełnym pipeline'em (`faster-whisper` + `pyannote.audio` +
`whisperx`) na `cuda`/`float16` — potwierdzone realną transkrypcją 60-minutowego nagrania z
diarizacją w ~3 min. Serwer `popos` jest teraz **wyłączony** (na prośbę użytkownika, `sudo poweroff`
po zakończeniu sesji). Następny krok: włączyć `popos` i kontynuować pracę na kolejnym planie/temacie
wg potrzeby — środowisko Docker jest gotowe do użycia (`git pull` + `docker compose up -d`).

## Co zrobione

- `Dockerfile` + `.dockerignore` — obraz `nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04`,
  instalacja `-e .[local]` z indeksu `cu128` w venv.
- `compose.yaml` — bind-mount repo → `/app`, named volume `echo-data:/data`, GPU reservation,
  `uvicorn --reload`.
- Odkryto i naprawiono: `origin/master` nie miał jeszcze niezacommitowanych zmian z planu 01
  (whisperx w `pyproject.toml`, `alignment.py`, `config.py`, `transcription.py` + testy) — za
  zgodą użytkownika zacommitowane i wypchnięte osobnym commitem (`d5f7e14`).
- Odkryto i naprawiono: `torchcodec` (zależność `pyannote.audio`) nie ładował się bez systemowej
  `libpython3.12t64` na Ubuntu 24.04 — dodane do `Dockerfile` (`7f2f633`).
- Udokumentowana pułapka: klient `hf-xet` (transfer modeli z HF) potrafi się zawiesić po błędzie
  500 z `cas-server.xethub.hf.co` tuż przed ukończeniem pliku (proces `S`, 0% CPU/GPU) — fix:
  `docker compose restart echo` + ponów joba.
- Zweryfikowane end-to-end: build, GPU widoczne (`torch.cuda.is_available()`), health `:8765`
  (lokalnie i przez tunel SSH z Maca), 58/58 testów jednostkowych w kontenerze, auto-reload,
  smoke test transkrypcji (60 min audio, diarizacja, brak fallbacku CPU), persystencja modeli
  po `docker compose down && up`.
- Dokumentacja: sekcja „Development w Dockerze (serwer GPU)” w `README.md` +
  `docs/04_guides/serwer_gpu_popos.md` (workflow iteracji, napotkane pułapki).
- Plan przeniesiony: `docs/02_plans/active/02_docker_dev_gpu.md` → `docs/02_plans/completed/`.
- Na koniec sesji: `popos` wyłączony przez `sudo -n poweroff` na wyraźną prośbę użytkownika.

## Gdzie skończyłem / kontekst

Gałąź `master`, wszystko zacommitowane i wypchnięte do `origin/master` (ostatni commit `398317b`).
Repo na `popos` (`~/Documents/Git/Echo`) jest zsynchronizowane z `origin/master` (ten sam commit).
Katalog danych na `popos`: `/data/echo` (named volume `echo-data`), cache modeli ~5.3 GB.

Niezacommitowane w repo pozostają: cały scaffold `docs/` (00, 01, 03, 05, 06, 99 + `README.md`
per-kategoria) oraz `.claude/` i `CLAUDE.md` z `init-app-workflow` — to świadomie pominięte,
poza zakresem planu 02 (nie moje do commitowania bez wyraźnej prośby).

Plan 01 (`docs/02_plans/active/01_poprawki_pipeline_transkrypcji.md`) ma jeden otwarty punkt:
krok 5 — benchmark na realnych nagraniach z dyktafonu (mógłby teraz iść na `popos` przez
`scripts/benchmark_transcription.py`, skoro Docker GPU już działa).

## Następny krok

- [ ] Włączyć `popos` (fizycznie albo przez smart plug/WOL, gdy będzie skonfigurowany) i po
      starcie: `ssh popos 'cd ~/Documents/Git/Echo && docker compose up -d'`.
- [ ] Rozważyć dokończenie planu 01 — krok 5 (benchmark na realnych nagraniach), teraz że
      środowisko GPU w Dockerze jest gotowe i zweryfikowane.

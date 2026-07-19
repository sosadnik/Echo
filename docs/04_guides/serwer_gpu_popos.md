# Przewodnik: headless serwer GPU (Pop!_OS) dla Echo

Maszyna z RTX 5070 Ti (Blackwell) pod ciężki pipeline transkrypcji (`faster-whisper`,
`pyannote`, `whisperx`) uruchamiany w Dockerze. Mac łączy się przez SSH; Web UI Echo
przez tunel SSH (`ssh -L 8765:127.0.0.1:8765 popos`).

Stan skonfigurowany: 2026-07-13.

## Dostęp

- Host: `popos` (alias w `~/.ssh/config` na Macu) → `192.168.1.140` (rezerwacja DHCP
  na routerze Play Box Net: MAC WiFi `50:BB:B5:A5:35:24` → `.140`).
- Auth: wyłącznie klucz (hasłem wyłączone w `sshd_config`). mDNS: `pop-os.local`.
- Zdalne komendy administracyjne **bez hasła** (`/etc/sudoers.d/remote-mgmt`):
  `reboot`, `poweroff`, `efibootmgr` — tylko te; reszta sudo wymaga hasła interaktywnie.
- Claude CLI zainstalowany i zalogowany — nieinteraktywnie:
  `ssh popos 'claude -p "..."'` (dłuższe sesje: `ssh popos` + `tmux` + `claude`).

```bash
ssh popos 'sudo -n reboot'      # zdalny restart
ssh popos 'sudo -n poweroff'    # zdalne wyłączenie
```

## Boot / dual-boot z Windows

- Bootloader: systemd-boot; **domyślny wpis: Pop!_OS**, timeout menu ustawiony —
  zdalny/zimny start zawsze ląduje w Pop!_OS, przy biurku można wybrać Windows z menu.
- Jednorazowy boot do Windows zdalnie:

```bash
ssh popos 'sudo -n efibootmgr'                    # lista wpisów (Windows = Boot0000)
ssh popos 'sudo -n efibootmgr --bootnext 0000 && sudo -n reboot'
```

- Powrót: restart/shutdown Windowsa → następny start = Pop!_OS (domyślny).
- W UEFI są wpisy-duchy po starych instalacjach (`Kubuntu`, drugi `Windows Boot Manager`)
  — nieużywane.

## Zasilanie

- BIOS: **Restore on AC Power Loss = Power On** — powrót zasilania uruchamia maszynę.
- Docelowo smart plug **Shelly Plug S MTR Gen3** (lokalny HTTP API, bez chmury):
  gniazdko stale ON; zdalny start = cykl zasilania; przycisk na obudowie działa normalnie.

```bash
# zdalny "przycisk power" (po instalacji Shelly; ustawić rezerwację DHCP dla wtyczki):
curl -s "http://<ip-shelly>/rpc/Switch.Set?id=0&on=false&toggle_after=5"
# czy PC działa? (pobór mocy)
curl -s "http://<ip-shelly>/rpc/Switch.GetStatus?id=0"
```

- Usypianie systemu zablokowane: `sleep/suspend/hibernate/hybrid-sleep.target` = masked.

## Sieć (WiFi) — zebrane pułapki

Karta: **MediaTek MT7921** (`mt7921e`), sieć 5 GHz `Bulbulator-5G`, kanał **48 na sztywno**
(nie-DFS; "auto" na routerze wybierał kanał DFS niewidoczny bez domeny regulacyjnej).

1. Profil WiFi musi być **systemowy** (hasło w pliku, nie w keyringu GNOME) — inaczej
   sieć nie wstaje bez zalogowania w GUI. Tworzyć jako root:
   `sudo nmcli device wifi connect '<SSID>' password '<hasło>'` (hasło w apostrofach!).
2. Domena regulacyjna ustawiona na stałe: `/etc/modprobe.d/cfg80211.conf`
   (`options cfg80211 ieee80211_regdom=PL`) — bez tego kanały DFS 5 GHz są niewidoczne.
3. **Dual-boot pułapka**: Windows z włączonym Fast Startup zostawia MT7921
   w stanie, w którym Linux widzi pustą listę sieci. Fix doraźny: pełny power-off
   z odcięciem zasilania ~30 s; fix trwały: **Fast Startup w Windows wyłączony** —
   nie włączać ponownie.
4. Po zmianie kanału/restarcie AP maszyna łączy się sama (autoconnect), do ~2 min.
5. Pusta lista `nmcli device wifi list` przy aktywnym połączeniu bywa normalna
   (cache skanu); rozstrzyga `nmcli connection show --active`.

## Docker + GPU

- Docker 29.x + Compose v2 (apt), użytkownik w grupie `docker`.
- `nvidia-container-toolkit` zainstalowany i skonfigurowany (`nvidia-ctk runtime configure`).
- Sterownik NVIDIA 580.x, CUDA 13.0. Uwaga Blackwell: w kontenerach pipeline'u wymagane
  CUDA ≥ 12.8 / cuDNN 9 / ctranslate2 ≥ 4.5 / torch cu128 (szczegóły:
  `docs/03_reports/2026-07-12_docker_dev_analiza.md`).

```bash
# smoke-test GPU w kontenerze:
ssh popos 'docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi'
```

- Sterowanie demonem Dockera z Maca (opcjonalnie):
  `docker context create popos --docker "host=ssh://sebastian@192.168.1.140"`.

## Echo w Dockerze — workflow iteracji (repo `~/Documents/Git/Echo`)

Kod synchronizuje się przez git, nie przez bind-mount z Maca: `git push` na Macu →
`ssh popos 'cd ~/Documents/Git/Echo && git pull'`. Zwykły `compose.yaml` wiąże port wyłącznie
z `127.0.0.1` hosta i uruchamia stabilny serwer bez `--reload`; UI pozostaje dostępne przez
tunel SSH. Do krótkiego developmentu użyj jawnie `docker compose -f compose.yaml -f compose.dev.yaml up`.
Po zmianie `Dockerfile`/`pyproject.toml` wykonaj `docker compose up -d --build`.

Przydatne komendy (z katalogu repo na popos):

```bash
docker compose up -d --build      # (re)build + start
docker compose logs echo -f       # logi na żywo
docker compose down               # stop (named volume echo-data przeżywa)
docker compose run --rm echo python3 -m unittest discover -s tests -v
docker compose --profile tools run --rm gpu-preflight
```

Zweryfikowane (2026-07-13): build, GPU (`torch.cuda.is_available()` → RTX 5070 Ti), health
`:8765`, testy w kontenerze, auto-reload i pełny smoke test transkrypcji (60 min nagrania,
`cuda`/`float16`, diarizacja, ~3 min) — patrz `docs/02_plans/completed/02_docker_dev_gpu.md`.

Wersje stosu zweryfikowane ponownie 2026-07-19 są przypięte w `constraints-gpu.txt`.
Preflight sprawdza CUDA, ffmpeg, co najmniej 5 GiB wolnego miejsca, katalog modeli i
obecność wszystkich wymaganych bibliotek. Stały serwer wiąże port wyłącznie do
`127.0.0.1`; `--reload` występuje tylko w jawnym `compose.dev.yaml`.

Napotkane pułapki:

- **`torchcodec is not available`** przy diarizacji — brak systemowej `libpython3.12.so.1.0`
  (pakiet `libpython3.12t64`), do której dynamicznie linkuje się `torchcodec`. Naprawione
  w `Dockerfile` (`apt-get install libpython3.12t64`).
- **Pobieranie modeli z HF potrafi się zawiesić** — klient `hf-xet` czasem dostaje `500`
  z `cas-server.xethub.hf.co` i wisi bez końca tuż przed ukończeniem pliku zamiast zgłosić
  błąd (proces w stanie `S`, 0% CPU/GPU — widać w `docker compose exec echo ls -la /proc/<pid>/fd`
  po plikach `.incomplete`/`.lock` w `/data/echo/models/huggingface/hub/`). Fix:
  `docker compose restart echo` i ponowić joba.
- `buildx`/BuildKit nie jest zainstalowany — `Dockerfile` nie używa `--mount=type=cache`
  (świadomie, żeby nie wymagać dodatkowego pakietu na serwerze).

## Diagnostyka po restarcie — szybka checklista

```bash
ssh popos true && echo OK                # 1. maszyna w sieci?
ssh popos 'nvidia-smi | head -4'         # 2. GPU żyje? ("Driver/library mismatch" → reboot)
ssh popos 'docker ps'                    # 3. Docker działa?
```

Gdy maszyna nie wraca do sieci: monitor + konsola, patrz sekcja „Sieć" pkt 1–3.

# Echo

Prosty szkielet aplikacji do przeglądu nagrań z dyktafonu:

- lokalny backend `FastAPI`
- proste `Web UI` serwowane przez backend
- launcher pod desktopowy `exe`
- lokalny pipeline `faster-whisper + pyannote.audio`

## Dlaczego taki wariant

Na start celem jest prostota i niezawodność:

- backend i logika audio w Pythonie, bo tam jest najwięcej sensownych narzędzi do transkrypcji
- UI jako zwykła aplikacja webowa, ale uruchamiana lokalnie
- docelowo pakowanie do `portable exe` bez środowiska deweloperskiego po stronie użytkownika

Aktualny kierunek:

- `faster-whisper` robi transkrypcję i timestampy słów
- `pyannote.audio` robi diarizację speakerów
- backend scala oba wyniki do segmentów pod UI
- modele i cache są odkładane lokalnie przez aplikację

Provider domyślny to `local`. Tryb `mock` nadal istnieje do szybkiego testu UI:

```bash
ECHO_TRANSCRIPTION_PROVIDER=mock python3 -m echo_app.launcher
```

## Struktura

```text
src/echo_app/
  app.py
  config.py
  jobs.py
  launcher.py
  main.py
  repository.py
  schemas.py
  transcription.py
  static/
scripts/
  build_windows.bat
```

## Instalacja

Minimalny backend/UI:

```bash
python3 -m pip install -e .
```

Wymaganie systemowe dla lokalnego pipeline:

```bash
ffmpeg
```

Lokalne modele (`faster-whisper`, `pyannote.audio`, `whisperx` do forced alignment):

```bash
python3 -m pip install -e .[local]
```

## Uruchomienie lokalne

```bash
python3 -m echo_app.main
```

Albo launcher, który otworzy przeglądarkę:

```bash
python3 -m echo_app.launcher
```

## Konfiguracja modeli

Najważniejsze zmienne środowiskowe:

```bash
ECHO_WHISPER_MODEL=large-v3-turbo
ECHO_WHISPER_DEVICE=cpu
ECHO_WHISPER_COMPUTE_TYPE=int8
ECHO_DIARIZATION_MODEL=pyannote/speaker-diarization-community-1
ECHO_PREPARE_FILTER_PRESET=full
HF_TOKEN=...
```

Opcjonalne ograniczenia diarizacji:

```bash
ECHO_MIN_SPEAKERS=1
ECHO_MAX_SPEAKERS=4
ECHO_LANGUAGE_HINT=pl
```

Domyslnie aplikacja ustawia `ECHO_LANGUAGE_HINT=pl`. W `.env` warto to wpisac tylko wtedy, gdy chcesz nadpisac jezyk.

Uwagi praktyczne:

- z poziomu UI można teraz zmieniać tylko model i device dla `Whisper` oraz diarizacji; zapisują się do `settings.json` w katalogu danych aplikacji
- z poziomu biblioteki można importować kilka plików audio naraz; upload leci sekwencyjnie, żeby łatwiej utrzymać stabilny lokalny backend
- nazwę nagrania można edytować bezpośrednio w karcie biblioteki; zmiana dotyczy wpisu w aplikacji, nie nazwy pliku na dysku
- z poziomu UI można pobrać eksport `txt` z segmentami diarizacji; plik zawiera timestampy oraz nazwy speakerów ustawione lokalnie w UI
- `.env` nadal jest dobrym miejscem na wartości startowe i `HF_TOKEN`
- wejściowe audio jest przed obróbką czyszczone przez `ffmpeg`, chain sterowany presetem `ECHO_PREPARE_FILTER_PRESET`: `full` (domyślny, `high-pass` + `low-pass` + `denoise` + `speechnorm` + `limiter`), `light` (tylko `high-pass`/`low-pass`) albo `none` (bez czyszczenia, tylko konwersja do mono `wav` `16 kHz`); domyślny preset pozostaje `full` do czasu benchmarku na realnych nagraniach (krok 5 planu `01`)
- word timestampy z `faster-whisper` przechodzą przez forced alignment (`whisperx`, model wav2vec2 dla polskiego); jeśli `whisperx` nie jest zainstalowany albo alignment się nie powiedzie, pipeline loguje ostrzeżenie i używa surowych timestampów z Whispera — transkrypcja nigdy nie pada przez błąd alignmentu
- `faster-whisper` może pobrać model automatycznie przy pierwszym uruchomieniu.
- `pyannote` może wymagać `HF_TOKEN`, jeśli model diarizacji jest pobierany z Hugging Face.
- w spakowanym `exe` dane aplikacji i cache modeli trafiają do katalogu `data/` obok programu
- docelowo można zamiast repo/model id wskazać lokalne katalogi modeli

### Uwaga: Blackwell (RTX 50xx) i `compute_type`

Na GPU z architekturą Blackwell (np. RTX 5070 Ti) `compute_type=int8` w CTranslate2 może się wywalać (crash) — bezpieczny domyślny wybór dla `ECHO_WHISPER_DEVICE=cuda` to `float16` (patrz `_default_compute_type` w `config.py`, ustawiane automatycznie gdy `ECHO_WHISPER_COMPUTE_TYPE` nie jest ustawione ręcznie). Wymaga `faster-whisper>=1.2` i CTranslate2 ≥ 4.5 (patrz [SubtitleEdit#10180](https://github.com/SubtitleEdit/subtitleedit/issues/10180)).

### Praca przez tunel SSH (Pop!_OS + GPU, Mac jako klient)

Etap 1 zakłada, że ciężki pipeline (`faster-whisper`, `pyannote`, `whisperx`) działa na maszynie z GPU (np. Pop!_OS + RTX 5070 Ti), a Mac korzysta z `Web UI` przez przeglądarkę po przekierowaniu portu:

```bash
ssh -L 8765:127.0.0.1:8765 user@pop-os-host
```

Backend uruchamiasz normalnie na maszynie z GPU (`python3 -m echo_app.main`), a na Macu otwierasz `http://127.0.0.1:8765` w przeglądarce. Zdalny provider dla Maca bez tunelu i providerzy oparci o API to zakres kolejnego etapu.

## Budowa `portable exe` na Windows

Najprostszy i praktyczniejszy wariant to `one-folder`, nie `one-file`. Dla aplikacji desktopowej z assetami i późniejszym FFmpeg/modelami jest to zwykle mniej problematyczne.

Windows:

```bat
scripts\build_windows.bat
```

Wynik:

```text
dist\Echo\Echo.exe
```

## Kolejne kroki

1. Dodać weryfikację zależności i test model/device z UI przed startem joba.
2. Dodać import folderu z nagraniami i batch processing.
3. Dodać odtwarzacz audio zsynchronizowany z segmentami speakerów.
4. Dodać eksport do `json`, `docx`.

# Analiza: pipeline transkrypcji, alignmentu i diaryzacji (2026-07-18)

## Problem / Cel

Celem jest krytyczna ocena lokalnego pipeline'u Echo na rzeczywistym środowisku
Pop!_OS + RTX 5070 Ti 16 GB, wskazanie poprawek jakościowych i operacyjnych oraz
przygotowanie krótkiej listy modeli ASR do porównania z aktualnym
`faster-whisper large-v3`. Analiza obejmuje kod, testy, narzędzie benchmarkowe i
diagnostykę działającej instancji po SSH. Nie obejmuje wdrożenia zmian ani
uruchamiania nowych, kosztownych benchmarków modeli.

## Ocena ogólna

Pipeline ma **dobry fundament i bardzo dobrą wydajność**, ale nie jest jeszcze
gotowy do rzetelnego wyboru modelu na podstawie obecnego benchmarku.

- Mocne strony: lokalność danych, sensowna granica `TranscriptionProvider`, GPU,
  WhisperX z bezpiecznym fallbackiem, aktualny `pyannote community-1`, jawny VAD,
  postęp etapów i testy jednostkowe.
- Największe ryzyko jakościowe: benchmark nie przełącza naprawdę alignmentu,
  filtracja nie została rozstrzygnięta na danych referencyjnych, a metryka WER nie
  mierzy diaryzacji ani stabilności.
- Największe ryzyko operacyjne: API może uruchomić wiele ciężkich jobów równolegle
  na współdzielonym providerze/GPU, a job przerwany restartem zostaje na zawsze w
  stanie `running`.
- Wniosek: najpierw naprawić harness i kontrolę wykonania, następnie wykonać mały,
  dobrze opisany benchmark. Sama zamiana modelu bez tych zmian nie pozwoli
  odróżnić poprawy ASR od wpływu VAD, filtrów, alignmentu i diaryzacji.

## Stan faktyczny

### Przepływ danych

1. `ffmpeg` konwertuje wejście do mono PCM 16 kHz i opcjonalnie stosuje preset
   `full`, `light` albo `none` (`src/echo_app/transcription.py:259-353`).
2. `faster-whisper` wykonuje ASR z `beam_size=5`, VAD, timestampami słów,
   `condition_on_previous_text=False` i wymuszonym `pl`
   (`src/echo_app/transcription.py:362-426`).
3. WhisperX/wav2vec2 poprawia timestampy; awaria powoduje powrót do timestampów
   Whispera (`src/echo_app/alignment.py:29-90`).
4. `pyannote/speaker-diarization-community-1` wykonuje diaryzację, preferowany
   jest wynik `exclusive_speaker_diarization`
   (`src/echo_app/transcription.py:452-496`).
5. Każde słowo dostaje speakera według środka timestampu; sąsiednie słowa tego
   samego speakera są scalane przy przerwie do 1,2 s
   (`src/echo_app/transcription.py:573-644`).

### Działająca instancja Pop!_OS

Diagnostyka read-only po SSH potwierdziła:

- repo i kontener na commitcie `9a89f1d`, usługa działa na porcie 8765;
- GPU: RTX 5070 Ti, 16 303 MiB, sterownik 580.173.02;
- aktywne ustawienia: `large-v3`, CUDA/FP16, język `pl`, pyannote community-1,
  1-4 speakerów;
- pakiety: faster-whisper 1.2.1, CTranslate2 4.8.1, pyannote.audio 4.0.7,
  WhisperX 3.8.6, Torch 2.8.0+cu128;
- proces po załadowaniu modeli zajmuje około 11,5 GB VRAM także w bezczynności;
- cztery ukończone przebiegi tego samego pliku 3612,5 s trwały 162-182 s, czyli
  około 20-22x realtime;
- w bazie pozostał jeden stary job `running/diarization` po przerwaniu procesu;
- po zmianie VAD dwa powtórzenia dały po 182 słowa/20 segmentów/3 speakerów i
  były identyczne; wcześniejsze dwa dawały tylko 18 słów/2 segmenty/1 speakera.
  Potwierdza to wpływ VAD, ale bez transkryptu referencyjnego nie dowodzi poprawy
  WER ani poprawności speakerów.

Testy lokalne: 59 uruchomionych, 58 zaliczonych i 1 pominięty (ffmpeg). Są szybkie
i użyteczne dla helperów, lecz nie obejmują pełnego job runnera, restart recovery,
współbieżności, rzeczywistego przełączania wariantów benchmarku ani metryk
diaryzacji.

## Ustalenia i ryzyka

### P0 - naprawić przed benchmarkiem modeli

1. **`align=on/off` nie działa.** Skrypt ustawia `ECHO_ALIGNMENT_ENABLED`
   (`scripts/benchmark_transcription.py:43-45,283-289`), ale konfiguracja i
   provider nigdy jej nie odczytują. Oba warianty zawsze uruchamiają alignment.

2. **UI może po cichu zmienić model na `small`.** Backendowy default to
   `large-v3-turbo`, lecz allow-lista UI zawiera `turbo`, a nie
   `large-v3-turbo`; nieznana wartość jest mapowana na `small`
   (`src/echo_app/static/app.js:110,201-207,879`). Zapis formularza może więc
   zdegradować model bez ostrzeżenia.

3. **Zmiana CPU/CUDA nie przelicza `compute_type`.** Runtime override i API
   pozwalają zmienić urządzenie, ale nie `whisper_compute_type`
   (`src/echo_app/config.py:281-306`, `src/echo_app/schemas.py:81-85`). Przejście
   CPU -> CUDA może zachować `int8`, które na tym Blackwellu wcześniej zawodziło.

4. **Brak prawdziwej kolejki GPU.** Każde żądanie tworzy osobny `asyncio.Task`,
   a wszystkie korzystają ze wspólnego providera i modeli
   (`src/echo_app/jobs.py:54-68`). Równoległe wywołania API mogą dać OOM,
   wyścigi w lazy-loadzie albo nieprzewidywalne czasy. Nazwa statusu `queued` nie
   oznacza serializacji wykonania.

5. **Brak recovery po restarcie.** Job przerwany restartem nie jest oznaczany
   jako failed/interrupted. Potwierdza to stary wpis `running` na działającej
   instancji.

6. **Czas benchmarku miesza cold start z inferencją.** Provider jest tworzony od
   nowa dla każdej pary plik-wariant (`scripts/benchmark_transcription.py:292-301,
   423-427`). Wyniki nie rozdzielają pobrania/ładowania modelu, warm-upu i samego
   przetwarzania audio.

### P1 - największa szansa na poprawę jakości

1. **Rozdzielić audio dla ASR i diaryzacji.** Dziś zarówno Whisper, alignment,
   jak i embeddingi speakerów dostają ten sam przefiltrowany plik. `afftdn` i
   `speechnorm` mogą pomóc ASR, ale zmienić cechy głosu. ASR powinien dostać
   wariant benchmarkowany (`none/light/full`), a pyannote przynajmniej wariant
   `none` lub `light`.

2. **Nie spłaszczać godziny do jednego segmentu alignmentu.** `ForcedAligner`
   buduje jeden segment od pierwszego do ostatniego słowa
   (`src/echo_app/alignment.py:47-68`). Dla długiego nagrania lepiej zachować
   segmenty ASR lub dzielić po pauzach/VAD. Zmniejszy to pamięć, ograniczy
   rozjazdy i umożliwi lokalny fallback tylko dla wadliwego fragmentu.

3. **Ujednolicić tekst i timestampy.** `TranscriptResult.text` pochodzi z
   niealignowanego tekstu Whispera, a segmenty są odtwarzane z listy słów po
   alignmencie. Aligner może pominąć słowa, a parser usuwa tokeny interpunkcyjne,
   więc eksport segmentów i pełny tekst mogą się różnić.

4. **Ulepszyć przypisanie speakera.** Midpoint + najbliższa tura jest prosty,
   lecz przypisuje słowo do speakera nawet w luce i nie reprezentuje nakładającej
   się mowy. Lepszy jest największy overlap słowa z turą, jawny próg pewności,
   `UNKNOWN` dla luk i opcjonalne zachowanie informacji o overlapie. Dla krótkich
   wtrąceń należy benchmarkować także próg merge 1,2 s.

5. **Dodać kontekst dziedzinowy.** Nazwy własne i słownictwo użytkownika warto
   podawać jako hotwords/prompt tam, gdzie backend to wspiera. To często daje
   większy praktyczny zysk niż przejście między modelami o zbliżonym WER.

6. **Ocenić VAD na pełnym zbiorze, nie jednym pliku.** Próg 0,2 odzyskał dużo
   mowy i ustabilizował powtórzenia, ale może też zwiększyć false positives w
   szumie. Potrzebne są nagrania: ciche, normalne, zaszumione, z ciszą oraz z
   nakładającą się mową.

7. **Zachować transkrypcję przy awarii diaryzacji.** Alignment ma fallback, lecz
   wyjątek pyannote kończy cały job (`src/echo_app/transcription.py:473-476`).
   Tryb degradacji do jednego speakera jest praktyczniejszy, o ile wynik jawnie
   zapisze warning i status jakości.

### P2 - operacyjność, prywatność i obserwowalność

- Dodać pojedynczego workera/semafor GPU, cancel/timeout i jawny stan
  `interrupted` przy starcie aplikacji.
- Zapisywać czasy etapów, RTF, szczyt VRAM, liczbę słów/segmentów, fallback
  alignmentu i wersje modeli do wyniku joba/benchmarku.
- Logować wyjątki ze stack trace i `job_id` po stronie serwera, a do UI zwracać
  krótszy, bezpieczny komunikat; obecnie zostaje głównie `str(exc)` w bazie.
- Nie trzymać `uvicorn --reload` na stale działającej instancji przetwarzającej
  joby.
- Port 8765 jest publikowany na `0.0.0.0` bez uwierzytelniania, mimo że przewodnik
  zakłada tunel SSH. Nagrania i transkrypty należy wystawić tylko na localhost,
  ograniczyć firewallem/VPN albo dodać uwierzytelnienie.
- Zablokować wersje środowiska/obrazu; szerokie zakresy zależności utrudniają
  reprodukcję (instancja używa już pyannote.audio 4.0.7).

## Modele do przetestowania

Kolejność poniżej jest celowa: najpierw kandydaci o najlepszym stosunku szansy na
poprawę do kosztu integracji. Parametry nie są bezpośrednią miarą VRAM ani
prędkości.

| Priorytet | Model | Po co testować | Integracja / ograniczenia |
|---|---|---|---|
| 1 | `large-v3-turbo` / alias `turbo` | Najtańszy eksperyment; 809M zamiast ok. 1,55B, zwykle mały spadek jakości względem large-v3 | Bez zmian backendu, faster-whisper/CTranslate2; najpierw FP16, `int8_float16` tylko jako osobny test zgodności z Blackwell |
| 2 | `nvidia/parakeet-tdt-0.6b-v3` | 600M, polski, wysoki throughput, natywne word/segment timestamps | Nowy provider NeMo/Transformers, nie CTranslate2; CC BY 4.0; dla godziny użyć local attention albo chunkingu |
| 3 | `Qwen/Qwen3-ASR-1.7B-hf` | Bardzo mocny współczesny ASR, oficjalne wsparcie polskiego; quality-first challenger dla large-v3 | Nowy provider Transformers/Qwen; brak CTranslate2; osobny alignment dla PL, bo Qwen ForcedAligner nie wymienia polskiego |
| 4 | `nvidia/canary-1b-v2` | 978M, polski, dokładne timestampy, interpunkcja; alternatywny profil błędów do Parakeeta | Nowy provider NeMo, CC BY 4.0; zwykle wolniejszy od Parakeeta, ale potencjalnie dokładniejszy |
| 5 | `Qwen/Qwen3-ASR-0.6B-hf` | Mały i bardzo szybki wariant; dobry kandydat na codzienny model, jeśli jakość cichej mowy wystarczy | Nowy provider; PL wspierany, lecz oficjalne benchmarki zbiorcze wskazują wyraźnie słabszą jakość niż 1.7B |
| 6 | `CohereLabs/cohere-transcribe-03-2026` | 2B, polski, Apache 2.0, model nastawiony na jakość; dobry challenger dla large-v3 | Większy, nie mniejszy; model gated, nowy provider/vLLM lub Transformers; brak timestampów i skłonność do halucynacji na ciszy wymagają VAD + alignmentu |
| 7 | `openai/whisper-small` | 244M, drop-in speed/VRAM lower bound; pokaże koszt jakościowy mocnego odchudzenia | Bez zmian backendu; spodziewany duży spadek jakości na trudnej polskiej rozmowie |
| 8 | `bardsai/whisper-medium-pl` | 769M fine-tune polski; sprawdza, czy specjalizacja językowa przebije nowsze modele ogólne | Stary fine-tune Common Voice/VoxPopuli; wymaga konwersji do CTranslate2; wyniki self-reported nie obejmują mamrotanej mowy |

Opcjonalnie, poza pierwszą rundą: polski wav2vec2 XLSR-53 jako diagnostyczny dolny
punkt odniesienia; `facebook/mms-1b-all` wyłącznie badawczo (CC BY-NC 4.0 i słabsze
wyniki PL); `nvidia/nemotron-3.5-asr-streaming-0.6b` tylko jeśli pojawi się wymóg
realtime; oraz `microsoft/VibeVoice-ASR` jako eksperyment all-in-one
ASR+diaryzacja+timestampy. VibeVoice ma 9B parametrów i w BF16 nie mieści się
komfortowo wraz z narzutem na 16 GB VRAM, więc wymagałby kwantyzacji i nie spełnia
celu „mniejszy model”.

Nie rekomenduję `distil-large-v3` ani `distil-large-v3.5` dla Echo: mimo wsparcia
przez faster-whisper, oficjalne karty opisują je jako rodzinę angielską i przykłady
ustawiają `language="en"`. Nie są wiarygodnym kandydatem do polskich nagrań.

## Proponowany benchmark

### Zbiór

Minimum 6-10 krótkich, reprezentatywnych wycinków (łącznie 30-60 min), ręcznie
przepisanych i oznaczonych speakerami:

- cicha/mamrotana mowa;
- normalna rozmowa;
- szum i ruch;
- długa cisza + krótkie wypowiedzi;
- szybka zmiana mówców i krótkie wtrącenia;
- overlap dwóch osób;
- nazwy własne/słownictwo użytkownika.

Pełny godzinny plik należy zostawić na drugi etap, po odrzuceniu słabych modeli.

### Metryki

- ASR: znormalizowany WER i CER oraz osobno deletions/insertions/substitutions;
- kompletność: recall ręcznie zaznaczonych wypowiedzi i false speech w ciszy;
- diaryzacja: DER oraz speaker-attributed WER (`cpWER` lub `tcpWER`);
- timestampy: średni/p95 błąd początku i końca słowa/segmentu;
- stabilność: 3 powtórzenia trudnych klipów i odległość między wynikami;
- koszt: czas każdego etapu, RTF, szczyt VRAM, czas cold/warm start;
- praktyka: ślepa ocena A/B użytkownika dla czytelności i poprawności nazw.

### Kolejność eksperymentów

1. Naprawić przełączniki benchmarku i dodać stage timings/DER/cpWER.
2. Na `large-v3` ustalić VAD oraz osobne presety audio ASR/diaryzacja.
3. Runda drop-in: `large-v3` vs `turbo` vs `small`; opcjonalnie polski
   `bardsai/whisper-medium-pl` po konwersji.
4. Runda nowych providerów: Qwen3 1.7B/0.6B, Parakeet, Canary, Cohere.
5. Dwa najlepsze warianty sprawdzić na pełnych nagraniach i powtórzeniach.

Model należy zmienić tylko wtedy, gdy wygrywa nie samym WER, lecz łącznie:
kompletnością cichej mowy, cpWER/DER, stabilnością, czasem i użyciem VRAM.

## Rozważane podejścia

### A. Tylko zmiana rozmiaru Whispera

- Zalety: minimalny koszt, istniejący kod i alignment zostają.
- Wady: ten sam profil błędów; mniejszy model może mocniej gubić trudny polski.
- Ocena: obowiązkowa szybka baza (`turbo`, `small`), ale nie koniec oceny.

### B. Modułowy provider ASR + osobne alignment/diaryzacja

- Zalety: pasuje do obecnego `Protocol`, umożliwia uczciwe Qwen/NeMo/Cohere i
  zachowuje pyannote.
- Wady: trzeba ujednolicić format słów, interpunkcję, timestampy i błędy.
- Ocena: rekomendowane podejście docelowe.

### C. Model all-in-one ASR + diaryzacja

- Zalety: jedna inferencja, globalny kontekst speakera, mniej ręcznego merge.
- Wady: VibeVoice jest za duży dla komfortowego BF16 na 16 GB, trudniej wymieniać
  części i ocenić przyczynę błędu.
- Ocena: eksperyment porównawczy, nie pierwszy kierunek wdrożenia.

## Rekomendacja

Najpierw wykonać mały plan naprawy benchmarku i wykonania jobów, a dopiero potem
benchmark modeli. Pierwsza realna runda powinna objąć:

1. `large-v3` jako kontrolę;
2. `large-v3-turbo` jako prawie bezkosztowy kandydat produkcyjny;
3. `Parakeet-TDT-0.6B-v3` jako kandydat speed/quality;
4. `Qwen3-ASR-1.7B` jako kandydat quality-first;
5. `Qwen3-ASR-0.6B` jako kandydat lekki;
6. `Canary-1B-v2` albo Cohere Transcribe, zależnie od czasu integracji.

Nie podejmować decyzji na jednym pliku ani na ręcznym „brzmi lepiej”. Dla Echo
najważniejsza jest kompletność cichej mowy i przypisanie jej do właściwej osoby;
zwykły WER nie obejmuje obu tych problemów.

## Referencje

- Kod: `src/echo_app/transcription.py`, `src/echo_app/alignment.py`,
  `src/echo_app/jobs.py`, `scripts/benchmark_transcription.py`.
- Poprzednie raporty: `docs/03_reports/2026-07-11_pipeline_transkrypcji_analiza.md`,
  `docs/03_reports/2026-07-18_alternatywy_asr_analiza.md`.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [Whisper large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo)
- [Qwen3-ASR 1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf)
- [Parakeet-TDT-0.6B-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)
- [Canary-1B-v2](https://huggingface.co/nvidia/canary-1b-v2)
- [Cohere Transcribe 03-2026](https://huggingface.co/CohereLabs/cohere-transcribe-03-2026)
- [VibeVoice-ASR](https://huggingface.co/microsoft/VibeVoice-ASR)
- [Polish ASR Leaderboard / BIGOS](https://huggingface.co/blog/michaljunczyk/introducing-polish-asr-leaderboard)
- [wav2vec2 XLSR-53 Polish](https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-polish)
- [bardsai Whisper medium PL](https://huggingface.co/bardsai/whisper-medium-pl)

## Otwarte pytania

- [ ] Czy priorytetem jest maksymalna jakość, czy zwolnienie VRAM dla innych
      zadań na GPU?
- [ ] Czy użycie będzie komercyjne (istotne dla modeli CC BY-NC)?
- [ ] Czy istnieją ręczne transkrypty i oznaczenia speakerów dla co najmniej
      30 minut reprezentatywnych nagrań?
- [ ] Czy port aplikacji ma być dostępny w LAN, czy wyłącznie przez tunel SSH?

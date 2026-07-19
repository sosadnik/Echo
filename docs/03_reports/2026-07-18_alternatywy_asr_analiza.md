# Analiza: alternatywy dla Whisper jako silnika ASR (2026-07-18)

## Problem / Cel

Obecny pipeline transkrypcji Echo (`faster-whisper` model `large-v3`, CTranslate2, GPU) po
naprawie progu VAD (`docs/03_reports` — zob. commit `9a89f1d`) wciąż daje niedoskonałe wyniki na
cichych, mamrotanych nagraniach z dyktafonu po polsku. Użytkownik chce wiedzieć, jakie są
sprawdzone **alternatywy dla całej rodziny Whisper** jako silnika ASR (nie inne rozmiary tego
samego modelu — to już sprawdzone) i czy warto je przetestować lokalnie na tym samym nagraniu
testowym (`samples/V20260314-170105.WAV`), żeby porównać jakość transkrypcji.

## Ustalenia

- Architektura Echo jest już przygotowana pod wymianę silnika: `TranscriptionProvider` to
  `Protocol` z jedną metodą `transcribe()` (`src/echo_app/transcription.py:21`);
  `LocalTranscriptionProvider._run_whisper()` produkuje listę `WordToken(start, end, text)`, którą
  dalej konsumuje `_run_alignment()` (obecnie WhisperX/wav2vec2) i `_merge_words_into_segments()`
  (merge z diarizacją pyannote). Podmiana silnika ASR = nowa implementacja zwracająca tę samą
  strukturę `WordToken` — reszta pipeline'u (alignment, diarizacja, merge) zostaje bez zmian, o ile
  nowy silnik nie daje już natywnie precyzyjnych word-timestampów (wtedy krok alignment można
  nawet pominąć).
- Jedyny publiczny, systematyczny benchmark WER dla polskiego (600 ewaluacji, 25 kombinacji
  system-model, w tym Whisper, NVIDIA NeMo, MMS, wav2vec2): **Polish ASR Leaderboard (PAL) /
  BIGOS V2** — [huggingface.co/spaces/amu-cai/pl-asr-leaderboard](https://huggingface.co/spaces/amu-cai/pl-asr-leaderboard),
  paper: [BIGOS V2 (NeurIPS D&B 2024)](https://papers.nips.cc/paper_files/paper/2024/file/69bddcea866e8210cf483769841282dd-Paper-Datasets_and_Benchmarks_Track.pdf).
  Wynik ogólny: **Whisper Large (v2/v3) najlepszy wśród darmowych/lokalnych opcji**, tuż za nim
  **NVIDIA NeMo multilang**, potem MMS i wav2vec2. Mediana WER na BIGOS ~14,5%, na mowie
  spontanicznej (PELCRA) ~32,4% — nawet najlepsze silniki mają duży WER na trudnym, spontanicznym
  polskim, zgodnie z charakterem nagrań dyktafonowych Echo.

## Rozważane podejścia

### A. NVIDIA NeMo — Parakeet-TDT-0.6B-v3 (+ Canary-1B-v2 jako wariant)
- Na czym polega: model transducer (TDT), 600M parametrów, natywnie wielojęzyczny (25 języków
  europejskich w tym polski), auto-detekcja języka, bardzo wysoki throughput. Canary-1B-v2 (AED)
  ta sama rodzina, wolniejszy, porównywalny jakościowo do modeli 3× większych.
- Zalety: natywne wsparcie polskiego (karta modelu, nie fine-tune społecznościowy); **natywne
  word-level timestamps** bez osobnego kroku forced-alignment — potencjalnie eliminuje cały krok
  WhisperX z pipeline'u; licencja **CC-BY-4.0** (Canary-1B-v2, bez ograniczeń komercyjnych);
  lżejszy niż Whisper large-v3 (mniej VRAM, szybsza inferencja na RTX 5070 Ti); konkurencyjny z
  Whisper Large na BIGOS wśród darmowych opcji.
- Wady / koszt: NeMo Linux-first, cięższa instalacja niż `faster-whisper` (ale GPU-host to już
  Docker/Pop!_OS, więc mniejszy problem); brak potwierdzonej kompatybilności z Blackwell (sm_120)
  w oficjalnej dokumentacji — wymaga weryfikacji praktycznej; brak twardych liczb WER PL dla
  cichej/mamrotanej mowy specyficznie — trzeba zweryfikować na własnym materiale; brak wbudowanej
  diarizacji (trzeba skleić z pyannote, ale wzorzec integracji już istnieje w Echo).

### B. Meta MMS (wav2vec2, >1400 języków)
- Na czym polega: self-supervised wav2vec2 trenowany na ~500 tys. godzin mowy, CTC-based (word
  timestamps naturalnie z alignmentu ramkowego).
- Zalety: bardzo szeroki zasięg językowy, dobre wyniki dla języków niskozasobowych.
- Wady / koszt: **licencja CC-BY-NC-4.0 — wyklucza użycie komercyjne** bez osobnej zgody Mety; na
  BIGOS dla polskiego wypada **gorzej niż Whisper Large i NeMo multilang** (przewaga MMS
  materializuje się głównie dla języków niskozasobowych, nie dla polskiego); mniej aktywny rozwój
  niż NeMo/Whisper.

### C. Polskie fine-tuny wav2vec2 (community: jonatasgrosman i inne)
- Na czym polega: wav2vec2-large-XLSR/XLS-R fine-tunowane pod polski, głównie na Common Voice PL.
- Zalety: małe, szybkie, łatwa integracja (`transformers`), CTC → naturalny alignment.
- Wady / koszt: trenowane na **czystych, czytanych** danych (Common Voice) — odwrotny profil
  akustyczny niż ciche, mamrotane nagrania Echo; projekty społecznościowe nieaktywne od lat; w
  BIGOS wyraźnie za Whisper Large i NeMo multilang.

### Odrzucone bez pełnej analizy
- **SenseVoice** (Alibaba) — `SenseVoiceSmall` nie obsługuje polskiego (tylko zh/yue/en/ja/ko).
- **SeamlessM4T v2** — obsługuje polski, ale ta sama licencja CC-BY-NC-4.0 co MMS + brak jasnej
  dokumentacji word-level timestamps dla ASR.
- **Cloud API** (Azure Speech, Google STT, ElevenLabs Scribe v2 ~5% WER PL) — dobry punkt
  odniesienia jakości ("sufit" osiągalnej dokładności), ale sprzeczny z priorytetem
  offline/prywatności nagrań dyktafonowych. Ewentualny jednorazowy test na niewrażliwym pliku,
  nie jako kierunek produkcyjny.

## Rekomendacja

**Przetestować lokalnie na GPU na tym samym pliku testowym: NVIDIA NeMo Parakeet-TDT-0.6B-v3**
jako główny kandydat (i Canary-1B-v2 jako wariant wolniejszy/potencjalnie dokładniejszy, jeśli
czas pozwoli), porównując WER/jakość transkrypcji z obecnym faster-whisper large-v3. Uzasadnienie:
jedyna alternatywa z (a) potwierdzonym natywnym wsparciem polskiego, (b) natywnymi word-level
timestampami pasującymi 1:1 do istniejącej struktury `WordToken` (możliwość uproszczenia
pipeline'u przez pominięcie kroku WhisperX), (c) licencją CC-BY-4.0 bez ograniczeń komercyjnych,
(d) lżejszym footprintem GPU niż obecny large-v3, (e) wynikami na BIGOS konkurencyjnymi z Whisper
Large wśród darmowych modeli. MMS i community wav2vec2-PL odpadają jako pierwszy krok — licencja
NC (MMS) i niedopasowany profil danych treningowych (wav2vec2-PL) czynią je mało obiecującymi w
świetle własnego benchmarku BIGOS dla polskiego.

Do samego testu porównawczego rozważyć wykorzystanie istniejącego narzędzia
[pl-asr-bigos-tools](https://github.com/goodmike31/pl-asr-bigos-tools) (już 29 kombinacji
system-model dla polskiego) zamiast pisania własnego harnessu od zera.

Decyzja o ewentualnej wymianie silnika ASR w produkcji (nie tylko test porównawczy) jest **trudna
do odwrócenia** (wybór technologii, zmiana kształtu części pipeline'u) — jeśli test pokaże wyraźną
przewagę Parakeet/Canary, przed wdrożeniem warto zapisać ADR w `docs/06_decisions/`.

## Referencje

- Kod: `src/echo_app/transcription.py` (`TranscriptionProvider`, `WordToken`,
  `LocalTranscriptionProvider._run_whisper`/`_run_alignment`/`_merge_words_into_segments`)
- Wcześniejsza analiza: `docs/03_reports/2026-07-11_pipeline_transkrypcji_analiza.md` (już
  wskazywała Parakeet-TDT/Canary jako kandydata oraz ElevenLabs Scribe v2 jako referencję jakości)
- Naprawa VAD: commit `9a89f1d` (`fix: obniż próg VAD...`)
- Zewnętrzne:
  - [Polish ASR Leaderboard (PAL) — Hugging Face Space](https://huggingface.co/spaces/amu-cai/pl-asr-leaderboard)
  - [Introducing the Polish ASR Leaderboard (PAL) and BIGOS Corpora](https://huggingface.co/blog/michaljunczyk/introducing-polish-asr-leaderboard)
  - [pl-asr-bigos-tools (GitHub)](https://github.com/goodmike31/pl-asr-bigos-tools)
  - [BIGOS V2 paper (NeurIPS D&B 2024)](https://papers.nips.cc/paper_files/paper/2024/file/69bddcea866e8210cf483769841282dd-Paper-Datasets_and_Benchmarks_Track.pdf)
  - [nvidia/parakeet-tdt-0.6b-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)
  - [nvidia/canary-1b-v2](https://huggingface.co/nvidia/canary-1b-v2)
  - [Canary-1B-v2 & Parakeet-TDT-0.6B-v3 (arXiv 2509.14128)](https://arxiv.org/pdf/2509.14128)
  - [NVIDIA blog: multilingual speech AI dataset/models](https://blogs.nvidia.com/blog/speech-ai-dataset-models/)
  - [Scaling Speech Technology to 1000+ Languages (MMS, JMLR)](https://jmlr.org/papers/volume25/23-1318/23-1318.pdf)
  - [MMS licencja CC-BY-NC 4.0 — dyskusja](https://news.ycombinator.com/item?id=36035444)
  - [jonatasgrosman/wav2vec2-large-xlsr-53-polish](https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-polish)
  - [SenseVoice (GitHub)](https://github.com/FunAudioLLM/SenseVoice)
  - [facebook/seamless-m4t-v2-large](https://huggingface.co/facebook/seamless-m4t-v2-large)

## Otwarte pytania

- [ ] Czy NeMo (Parakeet/Canary) działa poprawnie na Blackwell (sm_120)/CUDA 12.8 w Dockerze
      Echo — brak potwierdzenia w dokumentacji, wymaga weryfikacji praktycznej przy teście.
- [ ] Czy pominięcie kroku WhisperX (natywne word-timestamps z NeMo) faktycznie poprawia jakość
      alignmentu, czy tylko upraszcza pipeline — do oceny po teście na materiale referencyjnym.
- [ ] Czy projekt Echo ma (lub będzie miał) komercyjne przeznaczenie — wpływa na wagę kryterium
      licencji (dyskwalifikuje MMS/SeamlessM4T jeśli tak).

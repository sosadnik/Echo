# 03 — Stabilizacja pipeline'u transkrypcji i wiarygodnego benchmarku

## Kontekst

Audyt `docs/03_reports/2026-07-18_audyt_pipeline_transkrypcji_i_diaryzacji.md`
potwierdził, że pipeline jest szybki na Pop!_OS + RTX 5070 Ti, ale obecny harness
nie pozwala wiarygodnie wybierać modelu. Przełącznik `align=on/off` nie zmienia
wykonania, UI może po cichu zdegradować model do `small`, nie ma prawdziwej kolejki
GPU ani recovery po restarcie, a wspólny filtrowany tor audio i godzinny alignment
w jednym segmencie utrudniają ocenę jakości. Plan obejmuje poprawę fundamentu;
adaptery nowych rodzin modeli i przeglądarka wyników są osobnym planem 04.

Plan rozszerza i zastępuje niezrealizowany checkpoint benchmarkowy z
`docs/99_archive/01_poprawki_pipeline_transkrypcji.md`. Podczas
wdrożenia plan 01 należy oznaczyć jako zastąpiony i przenieść do archiwum, bez
fałszywego uznawania jego niewykonanej weryfikacji za ukończoną.

## Cel końcowy / Definicja ukończenia

- Pipeline wykonuje najwyżej jeden ciężki job GPU naraz, a kolejne joby faktycznie
  czekają; duplikat dla tego samego nagrania jest odrzucany lub zwracany jako
  istniejący aktywny job.
- Po restarcie osierocone joby nie pozostają jako `running`: dostają jawny status
  `interrupted`, nagrania wracają do spójnego stanu, a job można ponowić.
- Ustawienia mają kanoniczne ID modelu, `compute_type=auto` przeliczane z device i
  działający przełącznik alignmentu; UI nie wykonuje cichego fallbacku.
- Neutralny plik mono 16 kHz jest wspólną bazą, ale ASR i diaryzacja mogą dostać
  osobne presety; domyślnie pyannote nie dostaje agresywnego `full`.
- Alignment zachowuje segmenty ASR, działa fragmentami i nigdy nie usuwa słów z
  wyniku tylko dlatego, że część fragmentu nie została wyrównana.
- Przypisanie speakera korzysta z największego overlapu, obsługuje luki jako
  `UNKNOWN` i nie maskuje awarii diaryzacji jako sukcesu bez ostrzeżenia.
- Każdy job i wynik benchmarku zapisuje wersjonowany manifest: backend/model,
  parametry VAD/filtrów/alignmentu, device/compute type, wersje bibliotek, warningi,
  liczby słów przed/po etapach, czasy etapów, RTF i dane o pamięci, jeśli dostępne.
- Harness rozdziela cold start/warm-up/inferencję, naprawdę przełącza warianty,
  obsługuje powtórzenia i liczy co najmniej WER, CER oraz S/D/I; po dostarczeniu
  oznaczeń speakerów także DER/JER i cpWER/tcpWER.
- Serwer GPU domyślnie wystawia port tylko na localhost hosta, nie używa
  `--reload` w trybie stałej pracy, a zweryfikowany stos GPU jest reprodukowalny.

## Status operacyjny

normalny

## Referencje

- Analiza: `docs/03_reports/2026-07-18_audyt_pipeline_transkrypcji_i_diaryzacji.md`
- Poprzedni plan: `docs/99_archive/01_poprawki_pipeline_transkrypcji.md`
- Spec do utworzenia: `docs/00_specification/pipeline_transkrypcji.md`
- Architektura do utworzenia: `docs/01_architecture/pipeline_transkrypcji.md`
- Kod: `src/echo_app/transcription.py`, `src/echo_app/alignment.py`,
  `src/echo_app/jobs.py`, `src/echo_app/repository.py`, `src/echo_app/config.py`,
  `src/echo_app/app.py`, `scripts/benchmark_transcription.py`
- UI ustawień: `src/echo_app/static/index.html`, `src/echo_app/static/app.js`
- Środowisko GPU: `Dockerfile`, `compose.yaml`, `.env.example`,
  `docs/04_guides/serwer_gpu_popos.md`
- Zewnętrzne: [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
  [WhisperX](https://github.com/m-bain/whisperX),
  [pyannote community-1](https://huggingface.co/pyannote/speaker-diarization-community-1),
  [jiwer](https://github.com/jitsi/jiwer),
  [pyannote.metrics](https://github.com/pyannote/pyannote-metrics)

## Implementacja (sekwencyjna)

- [x] 1. Ustalić i udokumentować kontrakty przed zmianą kodu.
  - Utworzyć specyfikację kryteriów jakości i stanów joba w
    `docs/00_specification/pipeline_transkrypcji.md`.
  - Utworzyć opis aktualnego i docelowego przepływu w
    `docs/01_architecture/pipeline_transkrypcji.md`.
  - Zdefiniować wersję `benchmark-artifact/v1` oraz pola `PipelineManifest`,
    `StageTiming`, `PipelineWarning`, `AsrSegment` i `AsrWord`.
  - Określić stany `queued -> running -> completed|failed|interrupted` oraz regułę
    deduplikacji aktywnego joba dla nagrania.
  - Zapisać ADR, jeśli format artefaktu lub trwała kolejka wymagają decyzji trudnej
    do odwrócenia.
  - Testy: walidacja serializacji/deserializacji kontraktów i zgodności wstecznej
    minimalnego starego `result_json`.

- [x] 2. Uporządkować cykl życia planów i migrację danych.
  - Zmapować otwarte kryteria planu 01 na checkpointy planu 03, opisać zastąpienie
    w planie 01 i przenieść go przez `git mv` do `docs/99_archive/`.
  - Rozszerzyć SQLite o pola/statusy potrzebne do provenance, warningów i recovery,
    bez utraty istniejących transkryptów.
  - Dodać idempotentną migrację oraz test bazy tworzonej od zera i aktualizowanej
    ze starego schematu.

- [x] 3. Naprawić konfigurację runtime i ustawienia UI.
  - Dodać jawne `alignment_enabled`, kanoniczny identyfikator modelu i
    `whisper_compute_type=auto`; wartość efektywna ma być wyliczana atomowo po
    zmianie device.
  - Ujednolicić aliasy `large-v3-turbo`/`turbo` w backendzie, API i UI; nieznany
    model ma zostać pokazany lub odrzucony z błędem, nigdy zmieniony na `small`.
  - Dodać osobne `asr_filter_preset` i `diarization_filter_preset` z migracją
    starego `prepare_filter_preset`; domyślny tor diaryzacji ustawić na neutralny.
  - Zapisać wszystkie zmienne wpływające na wynik w runtime overrides.
  - Testy: CPU/CUDA i `auto`, aliasy, nieznany model, persistence settings oraz
    faktyczne `alignment_enabled=False` w providerze.

- [x] 4. Zastąpić pozorną kolejkę pojedynczym trwałym workerem GPU.
  - Oddzielić `submit` od wykonania; jeden worker pobiera najstarszy `queued` job.
  - Wymusić najwyżej jeden aktywny job dla nagrania i jeden ciężki job na GPU.
  - Przy starcie oznaczać osierocone `running` jako `interrupted`, przywracać stan
    nagrania i pozostawiać jawne ponowienie zamiast automatycznego duplikowania.
  - Dodać bezpieczne zatrzymanie workera, timeout etapów oraz best-effort cancel
    między etapami; określić zachowanie, gdy biblioteka ML nie daje się przerwać.
  - Logować stack trace z `job_id` i etapem po stronie serwera, a w API zapisywać
    sanitizowany błąd.
  - Testy: FIFO, deduplikacja, dwie równoległe próby, restart recovery, cancel,
    timeout, wyjątek providera i shutdown.

- [x] 5. Wprowadzić neutralny tor audio i osobne wejścia etapów.
  - Dekodować oryginał raz do neutralnego mono PCM 16 kHz.
  - Z neutralnego pliku tworzyć wariant ASR według presetu; alignment i pyannote
    domyślnie zasilać neutralnym audio, z możliwością jawnego nadpisania.
  - Zachować spójne timestampy 1:1 między wariantami i nie wykonywać zbędnej
    wielokrotnej konwersji.
  - Testy komend ffmpeg, fallbacków, wyboru ścieżek dla każdego etapu oraz cleanup
    plików tymczasowych po sukcesie, błędzie i anulowaniu.

- [x] 6. Zachować strukturę ASR i alignować fragmentami.
  - Zwracać z ASR `AsrResult` z oryginalnymi segmentami, słowami i tekstem zamiast
    spłaszczonej listy `WordToken`.
  - Dzielić alignment po segmentach ASR lub bezpiecznych chunkach/pauzach z jawnym
    limitem długości; fallback wykonywać per chunk.
  - Aligner może poprawić timestampy, ale nie może cicho usunąć tekstu; token bez
    alignmentu zachowuje timestamp ASR i warning.
  - Zdefiniować jedno źródło prawdy dla `TranscriptResult.text` i tekstów segmentów,
    zachowując interpunkcję i zgodność eksportu.
  - Testy: godzina reprezentowana wieloma chunkami, częściowy/pusty wynik alignera,
    interpunkcja, brak słów, granice chunków i zgodność tekstu z segmentami.

- [x] 7. Poprawić diaryzację i przypisanie słów do speakerów.
  - Przypisywać speakerów według największej części wspólnej słowa i tury; dodać
    konfigurowalny próg dla luki i `UNKNOWN`, zamiast zawsze wybierać najbliższą
    osobę.
  - Zachować surowy identyfikator speakera i informację o overlapie/niepewności w
    danych pośrednich; display label nadal nadawać stabilnie chronologicznie.
  - Sparametryzować próg scalania 1,2 s i nie sklejać przez zmianę speakera lub
    istotną lukę.
  - Przy awarii pyannote zachować ASR jako wynik jednego speakera z warningiem i
    statusem degradacji; jawny tryb strict może nadal kończyć job błędem.
  - Testy: największy overlap, dokładna granica, luka, overlap dwóch osób, brak tur,
    krótkie wtrącenie, stabilne labelki i fallback/strict diarization.

- [x] 8. Zapisywać provenance, czasy i warningi każdego joba.
  - Mierzyć osobno prepare, load/cold start, ASR, alignment, diarization, merge i
    zapis; policzyć RTF wobec długości audio.
  - Zapisać efektywne parametry, wersje modeli/bibliotek, commit aplikacji oraz —
    gdy dostępne — GPU, sterownik, peak VRAM/RAM.
  - Zapisać warningi o fallbackach, liczbie słów przed/po alignment i degradacji
    diaryzacji; wystawić je w istniejącym API jobów.
  - Testy: deterministyczny manifest z mockowanym zegarem/sprzętem, zgodność starego
    joba bez metadanych oraz brak sekretów/tokenów w payloadzie.

- [x] 9. Przebudować harness benchmarkowy na `benchmark-artifact/v1`.
  - Naprawdę zastosować model, filtry, VAD, alignment on/off i liczbę powtórzeń z
    wariantu; nie sterować niewspieranymi zmiennymi środowiskowymi.
  - Reużywać provider/model w obrębie wariantu; raportować osobno cold load,
    warm-up i warmed inference.
  - Przyjmować manifest datasetu z tagami scenariusza, referencją tekstową i
    opcjonalnymi RTTM/segmentami speakerów; prywatne audio i gold labels domyślnie
    ignorować w git.
  - Zapisywać atomowo run manifest, wynik per plik/wariant/powtórzenie, transkrypt,
    segmenty, warningi i podsumowanie; przerwany run ma być czytelny, nie udawać
    ukończonego.
  - Testy: macierz wariantów, reuse/warm-up, trzy powtórzenia, partial failure,
    wznowienie/ponowienie, zgodność schematu i bezpieczne nazwy/ścieżki.

- [x] 10. Rozszerzyć metryki i reguły porównania.
  - Liczyć normalized/raw WER, CER i osobno substitutions/deletions/insertions.
  - Dodać hallucination/false-speech na oznaczonych fragmentach ciszy oraz recall
    ręcznie oznaczonych wypowiedzi.
  - Gdy dostępne są oznaczenia speakerów, liczyć DER/JER, cpWER lub tcpWER i błąd
    timestampów; brak danych raportować jako `N/A` z powodem, nigdy jako zero.
  - Agregować per scenariusz i globalnie, z medianą/p95 dla czasu i pamięci.
  - Testy metryk na małych ręcznie policzonych przykładach, permutacji speakerów,
    overlapie i pustej referencji.

- [x] 11. Wykonać kontrolny benchmark obecnego pipeline'u.
  - Przygotować lokalny manifest dla minimum: cicha mowa, normalna rozmowa, szum,
    cisza, szybka zmiana speakerów i overlap; nie commitować prywatnego audio.
  - Uruchomić na Pop!_OS co najmniej `large-v3` i `large-v3-turbo`, alignment on/off
    oraz neutralny/full tor ASR przy stałym neutralnym torze diaryzacji.
  - Wykonać trzy warmed powtórzenia trudnych fragmentów i potwierdzić, że artefakty
    są kompletne i możliwe do porównania przez plan 04.
  - Nie zmieniać domyślnego VAD/filtra wyłącznie na podstawie jednego pliku; decyzję
    o nowych defaultach zapisać jako ADR dopiero przy wystarczającym gold secie.

## Strumienie niezależne (równolegle ⇄)

- [x] ⇄ A. Utwardzić sposób uruchamiania instancji GPU.
  - Zakres plików/modułów: `compose.yaml`, opcjonalny override dev, `Dockerfile`,
    `.env.example`, constraints/lock środowiska GPU, przewodnik Pop!_OS.
  - Zależności i kontrakt wejścia/wyjścia: nie zmienia kontraktu pipeline'u;
    wymaga tylko ustalonej listy efektywnych ustawień z checkpointu 3.
  - Zakres: związać host port z `127.0.0.1`, usunąć `--reload` z trybu stałego,
    zachować jawny tryb dev, dodać health/preflight CUDA-ffmpeg-dysk-model i
    odtwarzalny zestaw wersji zweryfikowany na Blackwell/CUDA 12.8.
  - Kryterium scalenia: SSH tunnel nadal działa, port nie odpowiada bezpośrednio z
    LAN, kontener przechodzi preflight i pełne testy bez zmiany danych w volume.

## Weryfikacja końcowa

- [ ] Testy zakresowe dla zmiany:
  `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`
- [ ] Pełny zestaw testów uruchomiony lokalnie i w kontenerze GPU na Pop!_OS;
  brak pobierania ciężkich modeli w zwykłych testach jednostkowych.
- [ ] Test E2E kolejki: dwa joby zgłoszone równocześnie wykonują się sekwencyjnie,
  a trzeci duplikat nie tworzy drugiej inferencji tego samego nagrania.
- [ ] Test restartu: aktywny job po restarcie ma `interrupted`, nagranie jest
  ponownie dostępne, a retry tworzy nowy jednoznaczny job.
- [ ] Benchmark smoke potwierdza różnicę alignment on/off, cold/warm timings,
  powtórzenia, kompletne provenance i `N/A` dla brakujących gold metryk.
- [ ] Kryteria jakości: częściowy alignment nie gubi słów, diarization failure daje
  jawny zdegradowany wynik, a luki nie są arbitralnie przypisywane speakerowi.
- [ ] Kryteria prywatności: API nie ujawnia tokenów, port GPU jest localhost-only,
  prywatny dataset i artefakty nie trafiają przypadkiem do repo.
- [ ] Dokumentacja/spec/architektura, README, `.env.example` i przewodnik Pop!_OS
  odpowiadają wdrożeniu.
- [ ] `git diff --check` oraz
  `.venv/bin/python .codex/hooks/workflow-check.py --project-root .` przechodzą.
- [ ] Brak znanych regresji i nierozwiązanych blockerów.

## Wynik weryfikacji

<!-- Wypełnia verify: data, dokładne komendy, wyniki, testy manualne/E2E i ograniczenia. -->
Nie przeprowadzono.

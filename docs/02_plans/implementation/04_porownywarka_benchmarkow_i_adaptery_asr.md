# 04 — Porównywarka benchmarków w UI i adaptery modeli ASR

## Kontekst

Po ustabilizowaniu pipeline'u i formatu `benchmark-artifact/v1` w planie 03 Echo
ma umożliwić łatwe porównanie wyników wielu modeli na tych samych nagraniach.
Obecny `LocalTranscriptionProvider` jest związany z faster-whisper, a UI pokazuje
pojedyncze joby produkcyjne, nie serię benchmarkową. Pierwsza runda ma objąć:

- kontrolę `faster-whisper large-v3`;
- `large-v3-turbo`;
- `nvidia/parakeet-tdt-0.6b-v3`;
- `Qwen3-ASR-0.6B` i `Qwen3-ASR-1.7B`;
- `nvidia/canary-1b-v2`;
- opcjonalnie Cohere Transcribe jako rozszerzenie, które nie blokuje pierwszej
  wersji.

Plan obejmuje kontrakt adapterów, środowisko GPU, indeksowanie wyników i
read-only UI do analizy. Uruchamianie arbitralnych benchmarków z przeglądarki nie
wchodzi do pierwszej wersji — benchmark nadal startuje kontrolowanym CLI/workerem,
a UI czyta gotowe artefakty.

## Cel końcowy / Definicja ukończenia

- Core pipeline używa generycznego `AsrBackend`/registry i nie zawiera warunków
  rozrzuconych po kodzie dla konkretnych rodzin modeli.
- Każdy adapter zwraca wspólny `AsrResult` i deklaruje capabilities: języki,
  timestampy, punctuation, hotwords, VAD, maksymalną długość i wymagany alignment.
- Na Pop!_OS można wykonać ten sam benchmark dla baseline `large-v3`, turbo,
  Parakeeta, Qwen 0.6B/1.7B i Canary; opcjonalny Cohere jest obsługiwany za flagą
  i nie jest wymagany do ukończenia planu.
- Brak natywnych timestampów nie daje fałszywej precyzji: pipeline stosuje
  zewnętrzny alignment lub raportuje ograniczenie. Qwen ForcedAligner nie jest
  używany dla PL, dopóki oficjalnie nie obsługuje polskiego.
- Backend indeksuje artefakty `benchmark-artifact/v1` idempotentnie i wystawia
  bezpieczne API listy runów, wyników, metryk, transkryptów i segmentów.
- UI pokazuje historię runów, tabelę metryk, ostrzeżenia i środowisko, pozwala
  wybrać 2-4 warianty oraz porównać ich tekst, speakerów i timestampy obok siebie.
- Kliknięcie fragmentu odtwarza ten sam zakres audio dla wszystkich wariantów;
  różnice tekstu są oznaczone jako insertion/deletion/substitution, a brak metryki
  jest pokazany jako `N/A` z wyjaśnieniem.
- Widok umożliwia sortowanie/filtrowanie oraz eksport porównania do CSV/JSON, ale
  nie ogłasza automatycznego zwycięzcy przy niekompletnych danych.

## Status operacyjny

zablokowany — implementacja wymaga ukończonego i zweryfikowanego kontraktu
`benchmark-artifact/v1`, provenance oraz `AsrResult` z planu 03.

## Referencje

- Analiza: `docs/03_reports/2026-07-18_audyt_pipeline_transkrypcji_i_diaryzacji.md`
- Plan zależny: `docs/02_plans/implementation/03_stabilizacja_pipeline_i_benchmarku.md`
- Spec/architektura po planie 03: `docs/00_specification/pipeline_transkrypcji.md`,
  `docs/01_architecture/pipeline_transkrypcji.md`
- Kod backendu: `src/echo_app/transcription.py`, `src/echo_app/config.py`,
  `src/echo_app/schemas.py`, `src/echo_app/repository.py`, `src/echo_app/app.py`
- UI: `src/echo_app/static/index.html`, `src/echo_app/static/app.js`,
  `src/echo_app/static/app.css`
- Benchmark: `scripts/benchmark_transcription.py`, `data/benchmarks/`
- Modele: [Whisper turbo](https://huggingface.co/openai/whisper-large-v3-turbo),
  [Parakeet v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3),
  [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR),
  [Canary v2](https://huggingface.co/nvidia/canary-1b-v2),
  [Cohere Transcribe](https://huggingface.co/CohereLabs/cohere-transcribe-03-2026)

## Implementacja (sekwencyjna)

- [ ] 1. Zdjąć blokadę dopiero po weryfikacji planu 03 i zamrozić kontrakty.
  - Potwierdzić wersję `benchmark-artifact/v1`, `AsrRequest`, `AsrResult`,
    `AsrSegment`, `AsrWord`, warningów, timings i capability flags.
  - Dodać fixture artefaktu v1 z co najmniej dwoma modelami, pełnymi i brakującymi
    metrykami; będzie kontraktem dla API i UI.
  - Ustalić limit rozmiaru, retencję i zasady dostępu do prywatnych artefaktów.
  - Testy kontraktowe: stary/minimalny artefakt, pełny artefakt, nieznana wersja,
    uszkodzony/niepełny run i bezpieczna obsługa rozszerzeń schematu.

- [ ] 2. Wykonać spike zgodności zależności i zapisać decyzję runtime.
  - Sprawdzić na zweryfikowanym CUDA 12.8/Torch stosie współistnienie
    faster-whisper/CTranslate2, Transformers/Qwen/Parakeet i NeMo/Canary.
  - Zmierzyć rozmiar obrazu, cold load i peak VRAM dla jednego modelu naraz;
    potwierdzić, że registry zwalnia/offloaduje poprzedni backend przed następnym.
  - Jeśli jeden proces/obraz powoduje konflikt wersji lub niekontrolowane trzymanie
    pamięci, zapisać ADR i zastosować osobne runner images/procesy ze wspólnym
    protokołem JSON zamiast wyjątków zależnych od importów w core.
  - Wynikiem checkpointu jest jedna przyjęta topologia runtime, lock/constraints i
    komenda smoke dla każdego wymaganego backendu.

- [ ] 3. Wydzielić generyczny provider ASR i registry modeli.
  - Zdefiniować `AsrBackend` z metodami load/transcribe/unload i jednolitymi
    błędami; core pipeline odpowiada nadal za prepare, alignment policy,
    diaryzację i merge.
  - Dodać `ModelDescriptor`/capabilities oraz registry zwracające katalog modeli
    dostępnych w danym obrazie/runnerze.
  - Rozszerzyć settings o `asr_backend`, `asr_model`, `asr_device`,
    `asr_compute_type` i backend options; zachować migrację starego
    `whisper_model` oraz starego `provider=local`.
  - API ustawień ma zwracać katalog descriptorów, a aktualizacja ma walidować
    kombinację backend-model-device zamiast przyjmować dowolny string.
  - Testy: registry, capabilities, brak zależności opcjonalnej, load/unload,
    migracja starych settings i odrzucenie nieobsługiwanej konfiguracji.

- [ ] 4. Ustalić capability-driven alignment i segmentację.
  - Native word timestamps (Parakeet/Canary/faster-whisper) mapować bez ponownego
    forced alignmentu, chyba że wariant benchmarku jawnie go wymaga.
  - Segment-only/no timestamps mapować przez zewnętrzny aligner wspierający PL lub
    uruchamiać ASR na bezpiecznych segmentach VAD/diaryzacji i raportować
    rzeczywistą dokładność timestampu.
  - Dla Qwen PL nie używać `Qwen3-ForcedAligner-0.6B`, ponieważ jego opublikowana
    lista języków nie obejmuje polskiego; użyć alignmentu z planu 03.
  - Normalizować interpunkcję wyłącznie do metryk, nie niszczyć tekstu modelu w
    artefakcie raw.
  - Testy macierzy capabilities i każdej polityki, w tym brak timestampów,
    częściowe timestampy i nieobsługiwany język.

- [ ] 5. Rozszerzyć benchmark runner o backends i warianty modeli.
  - Ten checkpoint finalizować po scaleniu obowiązkowych strumieni adapterów A-C;
    wcześniej można wdrożyć i testować sam kontrakt runnera na fake backendach.
  - Wariant ma wskazywać backend, model, revision, device/dtype, language,
    alignment policy, VAD/filters i opcje backend-specific w wersjonowanym polu.
  - Jeden run wykonuje wszystkie modele na identycznym dataset manifest i zapisuje
    wspólne metryki bez nadpisywania surowych odpowiedzi.
  - Obsłużyć brak/gated model jako `unavailable/skipped` z powodem, nie jako zero
    jakości ani błąd całego runu.
  - Dodać CLI preset `first-round` z baseline, turbo, Parakeet, Qwen 0.6B/1.7B i
    Canary; Cohere jako jawny preset rozszerzony po zaakceptowaniu dostępu.
  - Testy parsera, planowania kolejności, unload między modelami, partial failure,
    capabilities i kompletności manifestu.

- [ ] 6. Dodać indeks benchmarków i bezpieczne API read-only.
  - Dodać idempotentny importer/indexer `benchmark-artifact/v1`; w SQLite trzymać
    pola do wyszukiwania i ścieżki/identyfikatory artefaktów, bez niekontrolowanego
    duplikowania dużych payloadów.
  - Wystawić: listę runów z filtrami, szczegóły runu, listę wyników, pojedynczy
    wynik/transkrypt/segmenty i eksport porównania CSV/JSON.
  - Umożliwić reindex po dodaniu artefaktów przez CLI oraz oznaczać run
    partial/interrupted/corrupt.
  - Wszystkie ścieżki rozwiązywać pod skonfigurowanym benchmark root; zablokować
    traversal, symlinki wychodzące poza root i zwracanie HF tokenów/ścieżek hosta.
  - Dodać paginację/limity oraz testy migracji, importu, reindex, filtrów,
    uszkodzonego artefaktu, traversal i eksportu.

- [ ] 7. Zbudować ekran historii benchmarków.
  - Dodać osobną sekcję/nawigację „Benchmarki”, nie mieszać runów z produkcyjną
    historią jobów nagrania.
  - Lista pokazuje dataset, datę, status, commit, host/GPU, liczbę modeli/plików,
    powtórzenia i kompletność gold labels.
  - Filtry: run, model/backend, scenariusz datasetu, status/warning i obecność
    metryk; sortowanie po jakości, czasie i VRAM.
  - Tabela wyników pokazuje WER/CER/S-D-I, DER/JER, cpWER/tcpWER, timestamp error,
    RTF, cold/warm time, peak VRAM i warningi. `N/A` zawiera tooltip z powodem.
  - UI ma zachować filtry w URL/local state i być użyteczne przy częściowym runie.
  - Testy API/HTML dla pustego stanu, partial/corrupt run, missing metrics,
    paginacji i escaping nazw/model output.

- [ ] 8. Zbudować widok porównania 2-4 wariantów.
  - Pozwolić przypiąć baseline i wybrać do trzech challengerów dla tego samego
    pliku/powtórzenia; nie porównywać przypadkiem różnych źródeł audio.
  - Pokazać równoległe kolumny: metryki, raw/normalized transcript, speaker lanes,
    timestampy, warningi i parametry pipeline'u.
  - Wyliczyć/odczytać alignment tekstowy do wizualizacji insertion/deletion/
    substitution; kolory mają być dostępne także przez etykietę/ikonę.
  - Dodać zsynchronizowany scroll, wyszukiwanie, przejście do następnej różnicy i
    przełącznik raw/normalized.
  - Brak timestampu/speakera ma być pokazany jawnie, bez sztucznego podstawiania
    danych baseline.
  - Testy funkcji diff/match, polskich znaków, pustego tekstu, bardzo długiego
    tekstu i niespójnej liczby segmentów.

- [ ] 9. Zintegrować porównanie z odsłuchem audio.
  - Wykorzystać istniejący mechanizm klipów/slotów A-B, rozszerzając go na zakres
    czasu wybrany z dowolnego wariantu.
  - Kliknięcie słowa/segmentu odtwarza identyczny zakres źródłowego audio i
    podświetla odpowiadające fragmenty we wszystkich kolumnach.
  - Dodać regulowany padding, zapętlenie fragmentu i skróty poprzednia/następna
    różnica bez generowania osobnych kopii całego nagrania.
  - Testy walidacji zakresów, nagrań bez timestampów, końca pliku i bezpiecznego
    mapowania benchmark result -> recording/source audio.

- [ ] 10. Dodać ranking pomocniczy i eksport bez fałszywej pewności.
  - Udostępnić widoki `quality`, `speaker accuracy`, `speed` i `balanced` z jawnymi
    wagami; użytkownik może zmienić wagi, ale surowe metryki pozostają widoczne.
  - Nie liczyć composite score, gdy wymaganej metryki brakuje; pokazać powód i
    zakres porównywalnych wyników.
  - Eksportować aktualne zestawienie, filtry, wagi, provenance i link/ID artefaktu
    do CSV/JSON bez danych audio.
  - Testy rankingu, remisów, missing metrics, różnych jednostek i stabilności
    eksportu.

- [ ] 11. Zaktualizować dokumentację i instrukcję pierwszej rundy.
  - Opisać instalację/cache/licencje/gated access, komendy prefetch/smoke oraz
    oczekiwane capabilities każdego modelu.
  - Udokumentować tworzenie dataset manifestu, gold transcript/RTTM, uruchomienie
    presetu `first-round`, reindex i użycie porównywarki.
  - Zapisać ograniczenia: Qwen PL bez własnego forced alignera, Cohere bez
    timestampów, VAD na ciszy, local attention/chunking Parakeeta, wymagania NeMo.
  - Nie commitować modeli, prywatnych nagrań, tokenów ani dużych artefaktów.

## Strumienie niezależne (równolegle ⇄)

Po ukończeniu checkpointów 1-4 adaptery korzystają z zamrożonego kontraktu i mogą
być implementowane równolegle w osobnych modułach, bez zmian w core registry.

- [ ] ⇄ A. Adapter faster-whisper.
  - Zakres plików/modułów: moduł adaptera Whisper + testy kontraktowe.
  - Zależności i kontrakt wejścia/wyjścia: `AsrBackend`/`AsrResult` z checkpointu
    3; obsługuje `large-v3`, `large-v3-turbo`, FP16 i wyłącznie zweryfikowane
    compute types na Blackwell.
  - Kryterium scalenia: baseline i turbo przechodzą wspólny contract test i realny
    smoke na Pop!_OS.

- [ ] ⇄ B. Adaptery Transformers dla Parakeet i Qwen.
  - Zakres plików/modułów: osobne moduły adapterów, wspólne utilities audio/batch,
    testy kontraktowe; bez zmian w UI/API.
  - Zależności i kontrakt wejścia/wyjścia: capabilities z checkpointu 3 oraz
    alignment policy z checkpointu 4.
  - Kryterium scalenia: Parakeet i oba Qwen zwracają poprawny `AsrResult`, zwalniają
    model i przechodzą realny smoke PL bez przekroczenia limitu VRAM.

- [ ] ⇄ C. Adapter NeMo dla Canary.
  - Zakres plików/modułów: moduł Canary/NeMo, opcjonalne zależności/runner image,
    testy kontraktowe.
  - Zależności i kontrakt wejścia/wyjścia: topologia runtime z checkpointu 2,
    wspólny `AsrBackend` i natywne timestamp capabilities.
  - Kryterium scalenia: Canary przechodzi contract test, realny smoke PL i nie
    pozostawia zajętej pamięci przed uruchomieniem następnego backendu.

- Opcjonalne rozszerzenie po wykonaniu obowiązkowej pierwszej rundy: adapter
  Cohere Transcribe.
  - Zakres plików/modułów: adapter i gated dependency path; brak wpływu na status
    ukończenia pierwszej rundy.
  - Zależności i kontrakt wejścia/wyjścia: dostęp do modelu zaakceptowany osobno,
    VAD i zewnętrzny alignment z checkpointu 4.
  - Kryterium scalenia: niedostępny model daje `unavailable` bez awarii runu; przy
    dostępie smoke PL zapisuje brak natywnych timestampów zgodnie z prawdą.

## Weryfikacja końcowa

- [ ] Testy zakresowe dla zmiany:
  `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`
- [ ] Pełny zestaw testów backendu i API przechodzi bez pobierania ciężkich modeli
  w zwykłym trybie; GPU smoke jest jawnie opt-in.
- [ ] Na Pop!_OS wykonano realny smoke dla large-v3, turbo, Parakeet, Qwen 0.6B,
  Qwen 1.7B i Canary na tym samym krótkim polskim audio; zapisano czas, peak VRAM,
  capabilities, warningi i sposób alignmentu.
- [ ] Preset `first-round` kończy partial run poprawnie nawet wtedy, gdy jeden
  backend jest niedostępny, i nie uruchamia dwóch modeli GPU jednocześnie.
- [ ] API poprawnie indeksuje fixture, pełny run i partial/corrupt run; traversal,
  symlink escape, tokeny i ścieżki hosta nie są ujawniane.
- [ ] UI działa dla pustego stanu, pełnego i częściowego runu; wybór 2-4 wyników,
  diff, `N/A`, filtry, ranking i eksport są spójne.
- [ ] Manualny test w przeglądarce potwierdza zsynchronizowany odsłuch tego samego
  zakresu, czytelność różnic oraz obsługę klawiatury i wąskiego ekranu.
- [ ] Wartości UI odpowiadają surowemu JSON/CSV artefaktu; nie ma automatycznego
  zwycięzcy przy brakujących gold metrics.
- [ ] Dokumentacja model catalog, instalacji, benchmarku i UI odpowiada wdrożeniu;
  prywatne audio/modele/artefakty są poza repo.
- [ ] `git diff --check` oraz
  `.venv/bin/python .codex/hooks/workflow-check.py --project-root .` przechodzą.
- [ ] Brak znanych regresji i nierozwiązanych blockerów.

## Wynik weryfikacji

<!-- Wypełnia verify: data, dokładne komendy, wyniki, testy manualne/E2E i ograniczenia. -->
Nie przeprowadzono.

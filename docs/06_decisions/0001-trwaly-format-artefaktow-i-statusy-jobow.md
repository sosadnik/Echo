# ADR-0001: Wersjonowany format artefaktów i jawne statusy jobów

- **Status:** Zaakceptowana
- **Data:** 2026-07-18
- **Powiązania:** plan `docs/02_plans/completed/03_stabilizacja_pipeline_i_benchmarku.md`, raport `docs/03_reports/2026-07-18_audyt_pipeline_transkrypcji_i_diaryzacji.md`

## Kontekst

Wynik joba był dotąd luźnym JSON-em z segmentami, bez wersji, provenance i
możliwości odróżnienia awarii od restartu. Benchmark potrzebuje artefaktów
porównywalnych między uruchomieniami i wersjami pipeline'u.

## Rozważane opcje

- **Opcja A — luźne słowniki JSON bez wersji.** Mały koszt teraz, ale brak
  jednoznacznej migracji i słaba porównywalność wyników.
- **Opcja B — wersjonowany manifest oraz jawny automat stanów.** Wymaga migracji,
  lecz pozwala ewoluować format bez zgadywania semantyki starych wpisów.
- **Opcja C — osobna zewnętrzna kolejka i magazyn artefaktów.** Ułatwia skalowanie,
  ale nie odpowiada obecnemu lokalnemu zakresowi aplikacji.

## Decyzja

Wybieramy `benchmark-artifact/v1` z `PipelineManifest` oraz stany `queued`,
`running`, `completed`, `failed`, `interrupted`. SQLite pozostaje trwałym źródłem
stanu kolejki; stary minimalny `result_json` nadal odczytujemy bez syntetyzowania
provenance.

## Konsekwencje

Nowe wyniki są porównywalne, a restart ma jednoznaczną semantykę. Migracje muszą
być idempotentne, API nie może ujawniać sekretów, a kolejne wersje formatu będą
wymagały nowego identyfikatora artefaktu i migracji odczytu.

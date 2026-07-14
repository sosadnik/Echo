<!-- agent-workflow:start version=1.1.1 -->
# Echo — reguły pracy

Projekt: **Echo** — aplikacja do przeglądu nagrań z dyktafonu (lokalny backend FastAPI + Web UI + pipeline faster-whisper/pyannote). Stack: **Python 3.11+ / FastAPI**.
Komunikacja i dokumentacja: **polski**.

## Sposób pracy: Analiza → Plan → Wdrożenie → Weryfikacja

Dla każdego nietrywialnego zadania trzymaj się pętli (skupiamy się na problemie, nie na metodzie):

```
worklog-resume → analyze → plan-create → implement → verify → worklog-save
```

1. **Analiza** (`analyze`) — ustal, jak rozwiązać problem / skąd błąd / w którą stronę rozwijać
   projekt; rozważ sprawdzone wzorce. Wynik: raport w `docs/03_reports/`. **Nie kodujemy bez tego**,
   gdy zadanie jest nietrywialne. Jeśli analiza kończy się **decyzją trudną do odwrócenia**
   (wybór technologii, kształt API, model danych, granice modułów) — zapisz ją jako **ADR**
   w `docs/06_decisions/`, zanim ruszysz z planem.
2. **Plan** (`plan-create`) — zamień rekomendację na plan w `docs/02_plans/implementation/NN_...`
   z osobnymi checklistami implementacji i weryfikacji.
3. **Wdrożenie** (`implement`) — realizuj checkpoint po checkpointcie. **Każdy** checkpoint =
   implementacja **+ napisane i uruchomione testy** (`PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`). Po zielonych testach
   **odhacz** punkt `[x]` w sekcji implementacji, potem przenieś plan do `verification/`.
4. **Weryfikacja** (`verify`) — uruchom pełne kontrole i kryteria akceptacji, zapisz dowody.
   Dopiero wtedy przenieś plan do `completed/`; defekt cofa go do `implementation/`.

Zasady przekrojowe:
- **Nie kodować bez planu** dla nietrywialnych zmian.
- **Każdy ukończony punkt odhaczać** w pliku planu (`[ ]` → `[x]`).
- **Zawsze testy** — bez przechodzących testów checkpoint nie jest ukończony.
- **Żadnej poprawki bez przyczyny źródłowej** — przy błędzie/nieprzechodzącym teście użyj `debug`
  (znajdź root-cause i napisz test odtwarzający, zanim naprawisz).
- Nie zmieniaj kodu produkcyjnego, pozostawiając plan w `verification/`.
- `completed/` wymaga pełnej weryfikacji i zapisanych wyników, nie tylko gotowego kodu.
- Dla zadania trywialnego wystarcza kod i test; pełnego raportu analizy nie twórz mechanicznie.

## Skille i subagenci

| Faza / cel | Użyj | Wspomaga (subagenci) |
|------------|------|----------------------|
| Wejście w temat po przerwie | `worklog-resume` | — |
| Analiza problemu/kierunku | `analyze` | `Explore`, `thorough-analyst`, `solution-researcher` |
| Budowa planu | `plan-create` | `Plan` |
| Wdrożenie + testy | `implement` | `code-implementer` (strumienie `⇄` równolegle) |
| Weryfikacja końcowa | `verify` | — |
| Błąd / nieprzechodzący test | `debug` | `Explore`, `thorough-analyst`, `code-implementer` |
| Zapis podsumowania sesji | `worklog-save` | — |
| Porządek w `docs/` | `docs-organizer` | — |

Subagenci (`.claude/agents/`): **`code-implementer`** (pisze i uruchamia testy),
**`solution-researcher`** (sprawdzone wzorce + referencje, tylko-do-odczytu) oraz
**`thorough-analyst`** (głęboka analiza przyczyny źródłowej).

## Struktura projektu

- Kod produkcyjny: `src/echo_app`. Testy: `tests`. Uruchomienie: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`.
- `docs/` — dokumentacja w kategoriach `NN_` (po **rodzaju** dokumentu); reguły: `docs/README.md`,
  pilnuje ich skill `docs-organizer` + hook `docs-guard`. Plany przechodzą przez
  `02_plans/implementation/`, `02_plans/verification/` i `02_plans/completed/`,
  raporty/analizy w `03_reports/`, dziennik pracy w `05_worklog/`, decyzje (ADR) w `06_decisions/`.
<!-- agent-workflow:end -->

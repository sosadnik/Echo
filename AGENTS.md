<!-- agent-workflow:start version=1.1.1 -->
# Echo — reguły pracy

Projekt: **Echo** — aplikacja do przeglądu nagrań z dyktafonu (lokalny backend FastAPI + Web UI + pipeline faster-whisper/pyannote). Stack: **Python 3.11+ / FastAPI**.
Komunikacja i dokumentacja: **polski**.

## Sposób pracy: Analiza → Plan → Wdrożenie → Weryfikacja

Dla każdego nietrywialnego zadania trzymaj się pętli:

```text
worklog-resume → analyze → plan-create → implement → verify → worklog-save
```

1. **Analiza** (`analyze`) — zbadaj problem i zapisz rekomendację w `docs/03_reports/`. Przed planem
   zapisz w `docs/06_decisions/` decyzję trudną do odwrócenia.
2. **Plan** (`plan-create`) — utwórz `docs/02_plans/implementation/NN_...` z osobnymi checklistami
   implementacji i końcowej weryfikacji.
3. **Wdrożenie** (`implement`) — realizuj checkpointy wraz z testami automatycznymi
   (`PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`), potem przenieś plan do `verification/`.
4. **Weryfikacja** (`verify`) — wykonaj pełne kontrole, zapisz dowody i dopiero wtedy przenieś
   plan do `completed/`. Defekt wymagający zmiany kodu cofa plan do `implementation/`.

Zasady przekrojowe:

- Nie koduj bez planu dla nietrywialnych zmian.
- Nie uznawaj checkpointu za ukończony bez napisanych i uruchomionych testów.
- Przy błędzie użyj `debug`: najpierw przyczyna źródłowa i test odtwarzający, potem poprawka.
- Nie zmieniaj kodu produkcyjnego dla planu pozostającego w `verification/`.
- Plan przenieś do `completed/` dopiero po pełnej weryfikacji i zapisaniu jej wyników.
- Deleguj równolegle tylko zadania rzeczywiście niezależne, oznaczone `⇄`.
- Dla zadań trywialnych wystarcza kod i test. Pełny raport analizy stosuj do zmian złożonych;
  ADR do decyzji trudnych do odwrócenia.

## Skille i subagenci

| Cel | Skill | Subagenci |
|---|---|---|
| Powrót po przerwie | `worklog-resume` | — |
| Analiza | `analyze` | `explorer`, `thorough-analyst`, `solution-researcher` |
| Plan | `plan-create` | `planner` |
| Wdrożenie i testy | `implement` | `code-implementer` dla strumieni `⇄` |
| Weryfikacja końcowa | `verify` | — |
| Debugowanie | `debug` | `explorer`, `thorough-analyst`, `code-implementer` |
| Zapis sesji | `worklog-save` | — |
| Porządek w dokumentacji | `docs-organizer` | — |

Skille projektu znajdują się w `.agents/skills/`, a konfiguracje agentów w `.codex/agents/`.

## Struktura projektu

- Kod produkcyjny: `src/echo_app`.
- Testy: `tests`. Uruchomienie: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`.
- `docs/` — dokumentacja klasyfikowana po rodzaju; reguły w `docs/README.md`.
- Plany: `docs/02_plans/implementation/` → `verification/` → `completed/`; raporty: `docs/03_reports/`; worklog:
  `docs/05_worklog/`; ADR: `docs/06_decisions/`.
<!-- agent-workflow:end -->

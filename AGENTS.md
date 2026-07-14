<!-- agent-workflow:start version=1.0.0 -->
# Echo — reguły pracy

Projekt: **Echo** — aplikacja do przeglądu nagrań z dyktafonu (lokalny backend FastAPI + Web UI + pipeline faster-whisper/pyannote). Stack: **Python 3.11+ / FastAPI**.
Komunikacja i dokumentacja: **polski**.

## Sposób pracy: Analiza → Plan → Wdrożenie

Dla każdego nietrywialnego zadania trzymaj się pętli:

```text
worklog-resume → analyze → plan-create → implement → worklog-save
```

1. **Analiza** (`analyze`) — zbadaj problem i zapisz rekomendację w `docs/03_reports/`. Przed planem
   zapisz w `docs/06_decisions/` decyzję trudną do odwrócenia.
2. **Plan** (`plan-create`) — utwórz `docs/02_plans/active/NN_...` z kontekstem, referencjami,
   checklistą, zależnościami i niezależnymi strumieniami `⇄`.
3. **Wdrożenie** (`implement`) — realizuj checkpointy z testami (`PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`). Odhacz `[x]`
   dopiero po zielonej weryfikacji.

Zasady przekrojowe:

- Nie koduj bez planu dla nietrywialnych zmian.
- Nie uznawaj checkpointu za ukończony bez napisanych i uruchomionych testów.
- Przy błędzie użyj `debug`: najpierw przyczyna źródłowa i test odtwarzający, potem poprawka.
- Plan ukończony w 100% przenieś do `docs/02_plans/completed/` przez `docs-organizer`.
- Deleguj równolegle tylko zadania rzeczywiście niezależne, oznaczone `⇄`.

## Skille i subagenci

| Cel | Skill | Subagenci |
|---|---|---|
| Powrót po przerwie | `worklog-resume` | — |
| Analiza | `analyze` | `explorer`, `thorough-analyst`, `solution-researcher` |
| Plan | `plan-create` | `planner` |
| Wdrożenie i testy | `implement` | `code-implementer` dla strumieni `⇄` |
| Debugowanie | `debug` | `explorer`, `thorough-analyst`, `code-implementer` |
| Zapis sesji | `worklog-save` | — |
| Porządek w dokumentacji | `docs-organizer` | — |

Skille projektu znajdują się w `.agents/skills/`, a konfiguracje agentów w `.codex/agents/`.

## Struktura projektu

- Kod produkcyjny: `src/echo_app`.
- Testy: `tests`. Uruchomienie: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`.
- `docs/` — dokumentacja klasyfikowana po rodzaju; reguły w `docs/README.md`.
- Aktywne plany: `docs/02_plans/active/`; raporty: `docs/03_reports/`; worklog:
  `docs/05_worklog/`; ADR: `docs/06_decisions/`.
<!-- agent-workflow:end -->

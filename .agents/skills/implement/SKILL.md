---
name: implement
description: Faza WDROŻENIA. Realizuje plan z docs/02_plans/implementation/ wraz z testami automatycznymi. Po zakończeniu checklisty przenosi plan do verification/, gdzie przejmuje go verify.
---

# implement

Faza **Wdrożenia** w pętli `analyze → plan-create → implement → verify`. Realizuje plan z
`docs/02_plans/implementation/` checkpoint po checkpointcie — z testami automatycznymi.

## Procedura

1. **Wczytaj plan** — wskazany (lub jedyny) plan z `docs/02_plans/implementation/`.
   Pokaż następny niezrobiony punkt `[ ]` oraz ewentualną grupę `⇄` (niezależne).

2. **Wybierz zakres iteracji:**
   - następny **sekwencyjny** punkt `[ ]`, albo
   - całą grupę **`⇄` niezależnych** — wtedy deleguj **równolegle** do subagenta
     **`code-implementer`** (jeden subagent na strumień, uruchomiony równolegle z pozostałymi).

3. **Dla każdego checkpointu** (samodzielnie lub przez `code-implementer`):
   1. zaimplementuj zmianę w katalogach źródeł: `src/echo_app`;
   2. **napisz testy** w katalogach testów: `tests`;
   3. **uruchom testy**: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`;
   4. dopiero **po zielonych testach** odhacz punkt na `[x]` w pliku planu
      (zgodnie z regułą planów — po zatwierdzeniu przez użytkownika).

4. **Przekazanie do weryfikacji** — gdy wszystkie punkty sekcji implementacyjnych mają `[x]`,
   testy zakresowe są zielone i nie ma blockera:
   - uruchom walidator workflow;
   - `git mv` plan do `docs/02_plans/verification/`;
   - zaproponuj lub uruchom `verify`.

5. **Koniec sesji** — zaproponuj `worklog-save`, by następnym razem łatwo wrócić do tematu.

## Delegacja do subagentów
- **`code-implementer`** — wykonuje strumień wdrożeniowy: kod + testy + uruchomienie `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`.
  Zwraca wynik testów i które punkty planu spełnił; **nie odhacza planu sam** — to robi orkiestrator
  po weryfikacji.
- Strumienie `⇄` z planu są właśnie po to, by puścić je równolegle.

## Zasady
- **Żaden checkpoint bez testów** — implementacja bez napisanych i przechodzących testów nie jest
  ukończona i nie zostaje odhaczona.
- Odhaczaj wyłącznie punkty implementacji. Checklisty weryfikacyjnej nie odhacza `implement`.
- Trzymaj się planu — nowe ustalenia/rozszerzenia zakresu wracają do `plan-create` (dopisz punkty),
  a większe wątpliwości co do podejścia → do `analyze`.
- **Żadnej poprawki bez przyczyny źródłowej** — przy nieprzechodzącym teście użyj `debug`.
- Nie przenoś planu bezpośrednio z `implementation/` do `completed/`.

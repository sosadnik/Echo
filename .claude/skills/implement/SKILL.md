---
name: implement
description: Faza WDROŻENIA. Użyj, gdy istnieje gotowy plan w docs/02_plans/active/ i trzeba go zrealizować punkt po punkcie. Dla każdego checkpointu: implementacja + napisanie i uruchomienie testów, a po zielonych testach odhaczenie [x] w planie. Zadania niezależne (⇄) deleguje równolegle do subagenta code-implementer. Trzeci krok pętli: analyze → plan-create → implement.
---

# implement

Faza **Wdrożenia** w pętli `analyze → plan-create → implement`. Realizuje plan z
`docs/02_plans/active/` checkpoint po checkpointcie — z testami i odhaczaniem postępu.

## Procedura

1. **Wczytaj plan** — wskazany (lub jedyny) aktywny plan z `docs/02_plans/active/`.
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

4. **Domknięcie planu** — gdy wszystkie pozycje `[x]`: przypomnij o przeniesieniu planu do
   `docs/02_plans/completed/` (obsługuje skill `docs-organizer`, `git mv`, zachowaj numer).

5. **Koniec sesji** — zaproponuj `worklog-save`, by następnym razem łatwo wrócić do tematu.

## Delegacja do subagentów
- **`code-implementer`** — wykonuje strumień wdrożeniowy: kod + testy + uruchomienie `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`.
  Zwraca wynik testów i które punkty planu spełnił; **nie odhacza planu sam** — to robi orkiestrator
  po weryfikacji.
- Strumienie `⇄` z planu są właśnie po to, by puścić je równolegle.

## Zasady
- **Żaden checkpoint bez testów** — implementacja bez napisanych i przechodzących testów nie jest
  ukończona i nie zostaje odhaczona.
- Odhaczaj **dokładnie** zrealizowane punkty; nie hurtem „na zapas”.
- Trzymaj się planu — nowe ustalenia/rozszerzenia zakresu wracają do `plan-create` (dopisz punkty),
  a większe wątpliwości co do podejścia → do `analyze`.
- **Żadnej poprawki bez przyczyny źródłowej** — przy nieprzechodzącym teście użyj `debug`.

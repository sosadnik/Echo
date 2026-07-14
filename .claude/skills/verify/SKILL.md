---
name: verify
description: Faza WERYFIKACJI po implementacji. Sprawdza plan z docs/02_plans/verification/, uruchamia pełne testy i kryteria akceptacji, zapisuje dowody, a następnie przenosi plan do completed/ albo cofa go do implementation/ po wykryciu defektu.
---

# verify

Faza końcowa pętli `analyze → plan-create → implement → verify`. Nie służy do odkładania testów
automatycznych na koniec — te powstają razem z kodem. Tutaj niezależnie potwierdzasz, że cały
rezultat spełnia definicję ukończenia.

## Procedura

1. Wczytaj wskazany lub jedyny plan z `docs/02_plans/verification/`.
2. Potwierdź, że wszystkie punkty implementacji mają `[x]`; w przeciwnym razie przenieś plan z
   powrotem do `implementation/`.
3. Wykonuj kolejno checklistę `Weryfikacja końcowa`: testy zakresowe, pełny zestaw testów,
   build/lint/typecheck, kryteria akceptacji, przypadki brzegowe i dokumentację.
4. Po każdej kontroli zapisz dokładną komendę, wynik i datę w `Wynik weryfikacji`, a dopiero potem
   odhacz odpowiadający punkt.
5. Jeśli wykryjesz defekt wymagający zmiany kodu:
   - nie naprawiaj go w stanie `verification`;
   - zapisz wynik i przyczynę niepowodzenia;
   - przywróć `[ ]` dla unieważnionych kontroli;
   - `git mv` plan do `docs/02_plans/implementation/` i użyj `debug`.
6. Jeśli wszystkie checkboxy mają `[x]`, wynik zawiera dowody i walidator przechodzi, `git mv`
   plan do `docs/02_plans/completed/`.

## Zasady

- Nie uznawaj samego kodu ani raportu subagenta za dowód weryfikacji.
- Wynik „0 testów” / „no tests ran” nie jest pozytywnym dowodem, nawet gdy runner zwróci kod 0;
  zaakceptuj go tylko, jeśli brak testów jest świadomie oczekiwany i jawnie uzasadniony w planie.
- Nie zmieniaj kodu produkcyjnego w tej fazie; defekt cofa plan do implementacji.
- Zaznacz ograniczenia środowiska. Kontroli niewykonanej nie oznaczaj jako zaliczonej.
- `completed/` oznacza zweryfikowany rezultat, nie tylko zakończone kodowanie.

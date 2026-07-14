# 02 — Plany / checklisty

Mapy drogowe i checklisty wdrożeniowe. Każdy plan śledzi postęp znacznikami `[ ]` / `[x]`.

## Cykl życia

```text
implementation/ -> verification/ -> completed/
       ^                  |
       +---- defekt ------+
```

- `implementation/` — plany oczekujące na wdrożenie lub właśnie wdrażane. Kod i testy
  automatyczne powstają razem.
- `verification/` — implementacja jest gotowa, ale trwa pełna weryfikacja: cały zestaw testów,
  build/lint/typecheck, kryteria akceptacji, testy manualne/E2E i dokumentacja.
- `completed/` — wdrożenie oraz weryfikacja zostały zakończone, a dowody zapisano w planie.

## Zasady

1. Numery planów są unikalne globalnie — następny numer wyznaczaj ze wszystkich trzech katalogów.
2. Nowy plan zawsze startuje w `implementation/` i ma osobne checklisty implementacji oraz
   weryfikacji.
3. Do `verification/` przenieś go dopiero po zakończeniu checklisty implementacji i zielonych
   testach zakresowych.
4. Zmiana kodu produkcyjnego podczas weryfikacji unieważnia jej wynik: plan wraca do
   `implementation/`, a odpowiednie punkty weryfikacji ponownie dostają `[ ]`.
5. Do `completed/` można przenieść plan wyłącznie z `verification/`, gdy wszystkie checkboxy są
   `[x]` i sekcja `Wynik weryfikacji` zawiera komendy oraz rezultaty.
6. Plan zablokowany pozostaje w bieżącym katalogu z opisem blokera. Plan anulowany lub zastąpiony
   przenieś do `99_archive/` z podaniem powodu i ewentualnego planu następcy.
7. Przejścia wykonuj przez `git mv`, żeby zachować historię.

Plany tworzy `plan-create`, wdraża `implement`, weryfikuje `verify`, a reguł przejść pilnują
`docs-organizer` i walidator workflow.

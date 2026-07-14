---
name: worklog-resume
description: Odczytuje najnowszy wpis dziennika pracy z docs/05_worklog/, żeby szybko wrócić do projektu po przerwie. Użyj na starcie sesji albo gdy pytasz „na czym ostatnio skończyliśmy / nad czym pracowaliśmy". Pokazuje najpierw TL;DR, potem rozwinięcie i następny krok.
---

# worklog-resume

Wczytuje **najnowszy** wpis z dziennika pracy `docs/05_worklog/` i przedstawia go tak, by
użytkownik w kilka sekund wrócił do tematu. Konwencja katalogu: `docs/05_worklog/README.md`.

## Procedura

1. **Znajdź najnowszy wpis** — plik o najwyższym `NNN`:
   `ls docs/05_worklog/ | grep -E '^[0-9]{3}_' | sort | tail -1`
   - Jeśli brak wpisów → poinformuj, że dziennik jest pusty i zaproponuj skill `worklog-save`.

2. **Sprawdź stan planów** — najpierw `docs/02_plans/verification/`, potem `implementation/`.
   Plan oczekujący na weryfikację ma pierwszeństwo przed rozpoczynaniem nowego wdrożenia. Zaznacz
   plan zablokowany i jego powód.

3. **Odczytaj plik** i przedstaw użytkownikowi w kolejności:
   - **najpierw TL;DR** (to wystarcza do szybkiego wejścia w temat),
   - potem skrót „Co zrobione" / „Gdzie skończyłem",
   - na końcu **wyraźnie wyróżniony „Następny krok"**.

4. **Zweryfikuj aktualność** kontekstu względem stanu repo (lekko, nie rozwlekle):
   - `git branch --show-current` — czy jesteśmy na tej samej gałęzi co we wpisie.
   - `git log --oneline -5` i `git status -s` — czy coś się zmieniło od ostatniego wpisu.
   - Jeśli stan się rozjechał z wpisem — zaznacz to krótko.

5. **Zaproponuj wejście w „następny krok"** — jeśli istnieje plan w `verification/`, zaproponuj
   `verify`; w przeciwnym razie pierwszy niezrobiony punkt planu z `implementation/`.

## Opcjonalnie
- Jeśli użytkownik chce zobaczyć wcześniejsze sesje, wymień dostępne wpisy
  (`ls docs/05_worklog/`) i odczytaj wskazany.

## Zasady
- Zwięźle. Cel to szybki powrót, nie streszczanie całej historii projektu.
- Nie modyfikuj wpisów (to robi `worklog-save`).

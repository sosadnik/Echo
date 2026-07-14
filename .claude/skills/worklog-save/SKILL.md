---
name: worklog-save
description: Zapisuje krótkie podsumowanie bieżącej sesji pracy do dziennika docs/05_worklog/. Użyj, gdy kończysz pracę lub robisz przerwę i chcesz móc szybko wrócić do tematu. Nadaje kolejny numer NNN i datę DD-MM, wypełnia szablon (TL;DR + rozwinięcie + następny krok) na podstawie tego, co zrobiono.
---

# worklog-save

Tworzy nowy wpis w dzienniku pracy `docs/05_worklog/`. Konwencja katalogu: `docs/05_worklog/README.md`.

Cel wpisu: po nieregularnej przerwie wrócić do tematu w kilka sekund. Najpierw **TL;DR**
(stan + następny krok), potem **niedługie** rozwinięcie.

## Procedura

1. **Zbierz kontekst bieżącej pracy** (nie zmyślaj — opieraj się na faktach):
   - `git log --oneline -10` — co ostatnio zrobione.
   - `git status -s` — co w toku / niezacommitowane.
   - `git branch --show-current` — gałąź.
   - Jeśli sesja dotyczyła konkretnych plików/modułów — wymień je.

2. **Ustal numer wpisu** — znajdź najwyższy istniejący `NNN`:
   `ls docs/05_worklog/ | grep -E '^[0-9]{3}_' | sort | tail -1`
   Nowy numer = poprzedni + 1, zero-padded do 3 cyfr (`001`, `002`, …). Jeśli brak wpisów → `001`.

3. **Ustal datę** `DD-MM` z dnia dzisiejszego (np. `18-06`).

4. **Dobierz `slug`** — krótki temat sesji w kebab-case (np. `player-audio-sync`).

5. **Zapisz plik** `docs/05_worklog/NNN_DD-MM_slug.md` wg szablonu:

```markdown
# NNN — <temat> (DD-MM)

## TL;DR
<2–4 zdania: co zrobione, gdzie skończyliśmy, jaki następny krok>

## Co zrobione
- <punkty, oparte na git log / realnej pracy>

## Gdzie skończyłem / kontekst
<gałąź, kluczowe pliki/moduły, decyzje, otwarte wątki, niezacommitowane zmiany>

## Następny krok
- [ ] <konkretne, pierwsze działanie po powrocie>
```

## Zasady

- **TL;DR musi być samowystarczalne** — z samego TL;DR ma być jasne, na czym skończyliśmy i co
  robić dalej.
- Rozwinięcie krótkie — to notatka, nie raport.
- **Nie nadpisuj** istniejących wpisów; zawsze nowy numer. Dziennika się nie czyści.
- „Następny krok" to najważniejsza część — zapisz go nawet, gdy jest oczywisty.

## Po zapisaniu
- Potwierdź użytkownikowi ścieżkę nowego pliku i pokaż samo TL;DR.

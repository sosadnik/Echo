---
name: docs-organizer
description: Utrzymuje porządek w katalogu docs/. Użyj przy dodawaniu nowego dokumentu, przy porządkowaniu docs/, gdy plik trafił poza kategorię, albo gdy plan został w pełni zrealizowany i trzeba go przenieść. Klasyfikuje dokumenty po RODZAJU do kategorii 00_specification / 01_architecture / 02_plans / 03_reports / 04_guides / 05_worklog / 06_decisions / 99_archive.
---

# docs-organizer

Skill pilnujący konwencji katalogu `docs/`. Pełny opis kategorii i reguł: `docs/README.md`.

## Kategorie (klasyfikuj po RODZAJU dokumentu, nie po temacie)

| Katalog | Rodzaj | Pytanie kwalifikujące |
|---------|--------|----------------------|
| `00_specification/` | Źródło prawdy | Czy opisuje, co system **ma** robić (spec) lub jest materiałem źródłowym? |
| `01_architecture/` | Stan obecny | Czy opisuje, jak system **jest** zbudowany teraz (utrzymywane na żywo)? |
| `02_plans/` | Plan / checklista | Czy to mapa drogowa z pozycjami `[ ]`/`[x]` do realizacji? |
| `03_reports/` | Raport analizy | Czy to jednorazowa **migawka** analizy/audytu z danego momentu? |
| `04_guides/` | Instrukcja / prompt | Czy to instrukcja **dla agenta AI**, a nie opis systemu? |
| `05_worklog/` | Dziennik pracy | Czy to podsumowanie **sesji pracy** (na czym skończyliśmy)? |
| `06_decisions/` | Decyzja (ADR) | Czy to **decyzja projektowa z uzasadnieniem** (dlaczego tak, a nie inaczej)? |
| `99_archive/` | Archiwum | Czy to porzucone/nieaktualne podejście trzymane dla kontekstu? |

Rozróżnienie graniczne: `01_architecture` = stan trwały i aktualny; `03_reports` = zdjęcie stanu w czasie;
`06_decisions` = **dlaczego** dany stan wybrano (nie *jak* działa i nie *co* przeanalizowano).

> Kategoria `06_decisions/` (ADR) ma konwencję nazw `NNNN-slug.md` i wpisy **niezmienne**.
> Nie przepisuj istniejącego ADR — zmianę decyzji zapisuje się **nowym** ADR-em, a stary dostaje
> status `Zastąpiona przez ADR-NNNN`. ADR-a nie przenosi się też do `99_archive/`
> (status `Wycofana` zostaje w miejscu). Szczegóły: `docs/06_decisions/README.md`.

> Kategoria `05_worklog/` ma **własne skille** (`worklog-save` / `worklog-resume`) i konwencję
> nazw `NNN_DD-MM_slug.md` — nie przeklasyfikowuj jej wpisów do `03_reports`. Tu jednorazowo
> tworzy/odczytuje się dziennik pracy, a nie raporty analizy.

## Procedura

### Klasyfikacja nowego dokumentu
1. Ustal rodzaj wg tabeli powyżej (zadaj pytanie kwalifikujące).
2. Umieść plik w odpowiednim katalogu — **nigdy bezpośrednio w `docs/`** (jedyny dozwolony plik w korzeniu to `docs/README.md`).
3. Jeśli to **plan**: nadaj globalnie unikalny prefiks `NN_`, sprawdzając `implementation/`,
   `verification/` i `completed/`, następnie umieść go w `02_plans/implementation/`.

### Przenoszenie istniejącego pliku
- Zawsze `git mv` (zachowaj historię). Dla plików nieśledzonych zwykłe `mv`.
- Po przeniesieniu **zaktualizuj odwołania** do starej ścieżki w pozostałych dokumentach
  (`grep -rn 'stara/ścieżka' docs`).

### Cykl życia planu
- Niedokończona implementacja → `02_plans/implementation/`.
- Implementacja zakończona, końcowe kontrole jeszcze trwają → `02_plans/verification/`.
- Wszystkie checkboxy `[x]` i zapisane dowody kontroli → `02_plans/completed/`.
- Defekt wymagający zmiany kodu podczas weryfikacji → cofnij plan do `implementation/`.
- Nigdy nie pomijaj `verification/` i nie zmieniaj kodu produkcyjnego, pozostawiając plan w tym stanie.
- Plan zablokowany pozostaje w bieżącym stanie z opisem blokera. Anulowany lub zastąpiony przenieś
  do `99_archive/`, wskazując powód/następcę.

### Wycofywanie
- Nieaktualnego dokumentu **nie usuwaj** — przenieś do `99_archive/`.

## Weryfikacja po pracy
- Brak plików `.md` w korzeniu `docs/` poza `README.md`:
  `find docs -maxdepth 1 -name '*.md' ! -name 'README.md'` (powinno być puste).
- Brak zwisających odwołań do starych ścieżek (`grep` jak wyżej).
- Każdy katalog kategorii ma `README.md`.
- Uruchom walidator workflow i usuń wszystkie zgłoszone niespójności.

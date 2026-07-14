# Dokumentacja projektu

Katalog `docs/` jest podzielony na kategorie według **rodzaju** dokumentu. Numerowane prefiksy
wymuszają stałą, logiczną kolejność: od źródła prawdy, przez stan obecny, plany i raporty,
po instrukcje i archiwum.

| Katalog | Rodzaj | Co tu trafia |
|---------|--------|--------------|
| [`00_specification/`](00_specification/) | **Źródło prawdy** | Specyfikacja (co system *ma* robić) oraz materiały źródłowe. Zmienia się rzadko. |
| [`01_architecture/`](01_architecture/) | **Stan obecny** | Opis tego, jak system *jest* zbudowany teraz: architektura kodu, kluczowe moduły, API. |
| [`02_plans/`](02_plans/) | **Plany / checklisty** | Cykl `implementation/` → `verification/` → `completed/`, z osobną implementacją i końcową weryfikacją. |
| [`03_reports/`](03_reports/) | **Raporty analizy** | Audyty, analizy wymagań i badania — fotografia stanu w danym momencie. |
| [`04_guides/`](04_guides/) | **Instrukcje / prompty** | Instrukcje operacyjne i prompty dla agentów AI pracujących nad projektem. |
| [`05_worklog/`](05_worklog/) | **Dziennik pracy** | Krótkie podsumowania sesji pracy (TL;DR + rozwinięcie), by szybko wrócić do tematu po przerwie. Prowadzony skillami `worklog-save` / `worklog-resume`. |
| [`06_decisions/`](06_decisions/) | **Decyzje (ADR)** | *Dlaczego* system jest taki, jaki jest: decyzje projektowe z uzasadnieniem, alternatywami i konsekwencjami. Wpisy niezmienne (`NNNN-slug.md`). |
| [`99_archive/`](99_archive/) | **Archiwum** | Porzucone podejścia i nieaktualne dokumenty zachowane dla kontekstu historycznego. |

## Reguły utrzymania porządku

1. **Każdy nowy dokument** musi trafić do jednej z kategorii powyżej — nigdy bezpośrednio do `docs/`
   (wyjątkiem jest tylko ten plik `README.md`).
2. **Klasyfikuj po rodzaju, nie po temacie.** Pytanie pomocnicze: czy to opis docelowy (spec),
   opis bieżący (architecture), plan działania (plans), jednorazowa analiza (reports),
   czy instrukcja dla agenta (guides)?
3. **Plany** przechodzą przez `02_plans/implementation/`, `02_plans/verification/` i dopiero po
   pełnej weryfikacji do `02_plans/completed/`. Numery są unikalne we wszystkich stanach.
4. **Nie usuwaj** nieaktualnych dokumentów — przenoś je do `99_archive/`.
5. **Decyzje projektowe** (trudne do odwrócenia, z rozważanymi alternatywami) zapisuj jako ADR
   w `06_decisions/` — wpisy są **niezmienne**: zmianę decyzji odnotowuje się nowym ADR-em,
   a stary dostaje status `Zastąpiona przez ADR-NNNN` (szczegóły: `06_decisions/README.md`).
6. Klasyfikację wspiera skill `docs-organizer` oraz hook `docs-guard` przypominający przy zmianach w `docs/`.

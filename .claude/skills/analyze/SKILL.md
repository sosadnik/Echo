---
name: analyze
description: Faza ANALIZY przed kodowaniem. Użyj, gdy trzeba ustalić jak rozwiązać problem, skąd bierze się błąd, w którą stronę rozwijać projekt albo jakie są sprawdzone wzorce (architektoniczne, podejścia profesjonalnych firm). Bada root-cause, zestawia podejścia z zaletami/wadami, wskazuje rekomendację i zapisuje raport analizy do docs/03_reports/. Pierwszy krok pętli: analyze → plan-create → implement.
---

# analyze

Faza **Analizy** w pętli pracy `analyze → plan-create → implement`. Cel: zanim napiszemy choć
linijkę kodu, ustalić **konkrety i sposób wykonania** — żeby plan i wdrożenie były świadome,
a nie zgadywane.

Wynik fazy: **raport analizy** w `docs/03_reports/` (migawka analizy — zgodnie z `docs-organizer`),
zakończony jasną **rekomendacją**, którą podejmie `plan-create`.

## Kiedy używać
- „Skąd ten błąd / jaka jest przyczyna źródłowa?”
- „Jak najlepiej rozwiązać X / w którą stronę rozwijać projekt?”
- „Jakie są sprawdzone wzorce / jak robią to profesjonalne firmy?”

## Procedura

1. **Zdefiniuj problem** — jednym akapitem: objawy, zakres, czego dotyczy, co jest celem analizy.
   Nazwij, czego analiza **ma** dostarczyć (decyzja? przyczyna? kierunek?).

2. **Rozeznanie w kodzie** (gdy problem dotyczy istniejącego kodu):
   - szeroki przegląd / lokalizacja → deleguj do subagenta **`Explore`**;
   - głęboka, dociekliwa analiza przyczyny źródłowej → deleguj do **`thorough-analyst`**.
   Odwołuj się do `docs/01_architecture/` (stan obecny) i `docs/00_specification/` (czego się oczekuje).

3. **Sprawdzone wzorce z zewnątrz** (gdy to wybór architektury/podejścia):
   - deleguj do subagenta **`solution-researcher`** — zwróci 2–4 sprawdzone wzorce/podejścia
     z zaletami, wadami i referencjami.

4. **Zestaw podejścia** — dla każdej rozważanej opcji krótko: na czym polega, zalety, wady, koszt.
   Wskaż **jedną rekomendację** i uzasadnij wybór.

5. **Zapisz raport** `docs/03_reports/YYYY-MM-DD_<temat>_analiza.md` wg szablonu poniżej.

6. **Zakończ** — jeśli analiza kończy się **decyzją trudną do odwrócenia** (wybór technologii,
   kształt API, model danych, granice modułów) — zaproponuj zapis **ADR** w `docs/06_decisions/`.
   Następnie zaproponuj przejście do `plan-create` na bazie rekomendacji.

## Szablon raportu analizy

```markdown
# Analiza: <temat> (YYYY-MM-DD)

## Problem / Cel
<objawy, zakres, czego dotyczy, co analiza ma rozstrzygnąć>

## Ustalenia
<przyczyna źródłowa / stan obecny / kierunek — fakty z kodu i specyfikacji>

## Rozważane podejścia
### A. <nazwa>
- Na czym polega: …
- Zalety: …
- Wady / koszt: …
### B. <nazwa>
- …

## Rekomendacja
<wybrane podejście + uzasadnienie>

## Referencje
- Spec: `docs/00_specification/...`
- Kod: `src/echo_app`
- Zewnętrzne: <linki/źródła od solution-researcher>

## Otwarte pytania
- [ ] …
```

## Zasady
- **Nie koduj** w tej fazie — analiza kończy się decyzją, nie zmianą w kodzie.
- Rekomendacja musi być jednoznaczna — to ona staje się wejściem dla `plan-create`.
- Opieraj się na faktach (kod, specyfikacja, źródła), nie na domysłach.

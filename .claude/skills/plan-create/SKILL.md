---
name: plan-create
description: "Faza PLANU. Użyj po analizie, aby utworzyć plan w docs/02_plans/implementation/ z osobnymi checklistami implementacji i końcowej weryfikacji. Drugi krok pętli: analyze → plan-create → implement → verify."
---

# plan-create

Faza **Planu** w pętli `analyze → plan-create → implement → verify`. Zamienia ustalone podejście
w **wykonalny plan** w `docs/02_plans/implementation/`.

Plan ma pozwolić skupić się w fazie wdrożenia na samym wykonaniu — dlatego musi nieść pełny
kontekst, cel, referencje i jednoznaczną kolejność/niezależność zadań.

## Procedura

1. **Wejście** — raport analizy (`docs/03_reports/..._analiza.md`) lub ustalenia użytkownika.
   Jeśli brak analizy dla nietrywialnego zadania → najpierw zaproponuj skill `analyze`.

2. **Projekt kroków** — przy złożonych zadaniach deleguj projekt strategii do wbudowanego
   subagenta **`Plan`**, potem złóż wynik w plan wg szablonu.

3. **Ustal kolejność i niezależność** — rozdziel zadania na:
   - **sekwencyjne** (zależne od poprzednich) — numerowana checklista w kolejności;
   - **niezależne** (bez zależności) — oznaczone `⇄`, do równoległego podziału na subagentów.

4. **Numer planu** — kolejny wolny `NN_` ze wszystkich stanów. Użyj:
   `python3 .claude/hooks/workflow-check.py --project-root . --next-plan-number`.

5. **Zapisz** `docs/02_plans/implementation/NN_<temat>.md` wg szablonu poniżej.

6. **Zakończ** — zaproponuj `implement`.

## Szablon planu (sekcje obowiązkowe)

```markdown
# NN — <temat>

## Kontekst
<po co to robimy: problem/potrzeba, co z tego wynika; link do raportu analizy
docs/03_reports/..._analiza.md>

## Cel końcowy / Definicja ukończenia
<mierzalny stan „gotowe” — po czym poznamy, że zadanie zrealizowane>

## Status operacyjny
normalny
<!-- Dla blokady: zablokowany — <powód>. Dla anulowania/zastąpienia przenieś do 99_archive/. -->

## Referencje
- Spec: `docs/00_specification/...` (konkretne fragmenty)
- Architektura: `docs/01_architecture/...`
- Kod: `src/echo_app`
- Zewnętrzne: <linki istotne do poprawnego wykonania>

## Implementacja (sekwencyjna)
- [ ] 1. <krok zależny od porządku>
- [ ] 2. <krok>
- [ ] 3. <krok>

## Strumienie niezależne (równolegle ⇄)
<sekcja opcjonalna — tylko gdy są zadania bez wzajemnych zależności;
każdy strumień może iść do osobnego subagenta code-implementer>
- [ ] ⇄ A. <niezależne zadanie>
  - Zakres plików/modułów: …
  - Zależności i kontrakt wejścia/wyjścia: …
  - Kryterium scalenia: …
- [ ] ⇄ B. <niezależne zadanie wraz z tymi samymi polami>

## Weryfikacja końcowa
- [ ] Testy zakresowe dla zmiany: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`
- [ ] Pełny zestaw testów / build / lint / typecheck właściwy dla projektu
- [ ] Kryteria akceptacji i istotne przypadki brzegowe
- [ ] Dokumentacja i opis architektury są zgodne z wdrożeniem
- [ ] Brak znanych regresji i nierozwiązanych blockerów

## Wynik weryfikacji
<!-- Wypełnia verify: data, dokładne komendy, wyniki, testy manualne/E2E i ograniczenia. -->
Nie przeprowadzono.
```

## Zasady
- **Każda** sekcja obowiązkowa musi być wypełniona — plan bez kontekstu/celu/referencji jest
  niekompletny.
- Punkty implementacji obejmują kod oraz testy automatyczne zmienionej logiki.
- Punkty weryfikacji odhacza dopiero `verify`, zapisując dowody w sekcji wyniku.
- `⇄` oznacza „można robić niezależnie/równolegle” — to wskazówka do podziału na subagentów.
- Nie oznaczaj `⇄`, jeśli strumienie zmieniają te same pliki, wspólne API lub migrację bez
  ustalonego kontraktu i kolejności scalenia.
- `implement` przenosi gotowy plan do `verification/`; `verify` przenosi zweryfikowany plan do
  `completed/`. Nie pomijaj żadnego stanu.

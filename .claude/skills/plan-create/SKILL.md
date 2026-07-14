---
name: plan-create
description: Faza PLANU. Użyj po analizie (skill analyze), gdy znasz już sposób wykonania i trzeba zamienić go na wykonalny plan. Tworzy plan w docs/02_plans/active/ z numerem NN_, zawierający kontekst (po co), cel końcowy, referencje oraz checklistę z zachowaną kolejnością lub oznaczeniem zadań niezależnych (⇄) do podziału na subagentów, plus strategię testów. Drugi krok pętli: analyze → plan-create → implement.
---

# plan-create

Faza **Planu** w pętli `analyze → plan-create → implement`. Zamienia ustalone podejście
(z raportu `analyze` lub bezpośrednich ustaleń) w **wykonalny plan** w `docs/02_plans/active/`.

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

4. **Numer planu** — kolejny wolny `NN_` w `docs/02_plans/active/`
   (`ls docs/02_plans/active/ | grep -E '^[0-9]{2}_' | sort | tail -1`, +1).

5. **Zapisz** `docs/02_plans/active/NN_<temat>.md` wg szablonu poniżej.

6. **Zakończ** — zaproponuj `implement`.

## Szablon planu (sekcje obowiązkowe)

```markdown
# NN — <temat>

## Kontekst
<po co to robimy: problem/potrzeba, co z tego wynika; link do raportu analizy
docs/03_reports/..._analiza.md>

## Cel końcowy / Definicja ukończenia
<mierzalny stan „gotowe” — po czym poznamy, że zadanie zrealizowane>

## Referencje
- Spec: `docs/00_specification/...` (konkretne fragmenty)
- Architektura: `docs/01_architecture/...`
- Kod: `src/echo_app`
- Zewnętrzne: <linki istotne do poprawnego wykonania>

## Checklista (sekwencyjna)
- [ ] 1. <krok zależny od porządku>
- [ ] 2. <krok>
- [ ] 3. <krok>

## Strumienie niezależne (równolegle ⇄)
<sekcja opcjonalna — tylko gdy są zadania bez wzajemnych zależności;
każdy strumień może iść do osobnego subagenta code-implementer>
- [ ] ⇄ A. <niezależne zadanie>
- [ ] ⇄ B. <niezależne zadanie>

## Strategia testów
<co testujemy dla każdego strumienia i jak uruchomić — `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`;
jakie przypadki brzegowe muszą być pokryte>
```

## Zasady
- **Każda** sekcja obowiązkowa musi być wypełniona — plan bez kontekstu/celu/referencji jest
  niekompletny.
- Markery `[ ]` — pojedyncze, atomowe checkpointy; w fazie `implement` odhaczane na `[x]`.
- `⇄` oznacza „można robić niezależnie/równolegle” — to wskazówka do podziału na subagentów.
- Plan żyje w `active/` aż wszystkie pozycje będą `[x]`, wtedy `docs-organizer` przenosi go do
  `completed/`.

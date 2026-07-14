# 02 — Plany / checklisty

Mapy drogowe i checklisty wdrożeniowe. Każdy plan śledzi postęp znacznikami `[ ]` / `[x]`.

## Podział wg statusu

- `active/` — plany **w toku lub niewdrożone** (zawierają jeszcze pozycje `[ ]`).
- `completed/` — plany **w pełni zrealizowane** (wszystkie pozycje `[x]`).

## Zasady

1. Pliki planów są **numerowane** (np. `01_…`, `02_…`) dla zachowania kolejności.
2. Gdy wszystkie pozycje planu są odhaczone, **przenieś plik** z `active/` do `completed/`
   (`git mv`), zachowując numer.
3. Nowy plan zawsze startuje w `active/`.
4. Plany tworzy skill `plan-create`, realizuje `implement`, a przenoszeniem zajmuje się
   `docs-organizer`.

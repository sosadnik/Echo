# 03 — Raporty analizy

Analizy wykonane w określonym momencie: audyty, raporty pokrycia, analizy wymagań, badania.
W odróżnieniu od `01_architecture/` (stan utrzymywany na żywo) to materiał analityczny,
do którego wracamy jak do dziennika.

## Konwencja nazw — dwa rodzaje

Kategoria mieści dwa rodzaje dokumentów; **nazwa sygnalizuje, który to**:

| Rodzaj | Konwencja nazwy | Charakter |
|--------|-----------------|-----------|
| **Zamrożona migawka** | `RRRR-MM-DD_slug.md` (data z przodu) | Jednorazowa analiza z konkretnego dnia. **Nie edytujemy** po zapisaniu — to zdjęcie stanu. |
| **Żywy tracker** | `NAZWA_WIELKIMI.md` (bez daty) | Dokument analityczny **utrzymywany na żywo** (np. odhaczanie/usuwanie pozycji w miarę wdrażania). |

**Reguła:** datę w nazwie dostają **tylko** dokumenty zamrożone. Żywemu trackerowi daty **nie
nadawaj** — data kłamałaby o jego naturze. Jeśli tracker przestaje być aktualizowany i staje się
zdjęciem stanu, wtedy możesz go zamrozić i nazwać z datą.

> Raporty analizy tworzy skill `analyze`. Wniosek z raportu, który staje się stałym planem
> działania, przenieś/streszcz w `02_plans/`. Decyzję trudną do odwrócenia zapisz jako ADR w
> `06_decisions/`.

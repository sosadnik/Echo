# 05 — Dziennik pracy (worklog)

Krótkie podsumowania **sesji pracy nad projektem**. Cel: po nieregularnej przerwie wrócić do
tematu w kilka sekund — bez przypominania sobie, na czym się skończyło.

Każdy wpis zaczyna się od **TL;DR** (2–4 zdania: co zrobione, gdzie skończyliśmy, jaki następny
krok), a poniżej ma **niedługie rozwinięcie**. To nie jest raport ani plan — to notatka „dla
siebie z przyszłości".

## Konwencja nazw plików

```
NNN_DD-MM_slug.md
```

- `NNN` — kolejny numer wpisu, zero-padded (`001`, `002`, …). **Numer wyznacza kolejność** —
  najwyższy = najnowszy.
- `DD-MM` — dzień i miesiąc rozpoczęcia/zapisu sesji (np. `18-06`).
- `slug` — krótki temat, kebab-case (np. `player-audio-sync`).

Przykład: `001_18-06_player-audio-sync.md`.

## Struktura wpisu

```markdown
# NNN — <temat> (DD-MM)

## TL;DR
<2–4 zdania: stan na teraz + następny krok>

## Co zrobione
- …

## Gdzie skończyłem / kontekst
<pliki, gałąź, decyzje, otwarte wątki>

## Następny krok
- [ ] …
```

## Skille

- **`worklog-save`** — tworzy nowy wpis (nadaje numer i datę, wypełnia szablon na podstawie
  bieżącej pracy).
- **`worklog-resume`** — odczytuje najnowszy wpis, żeby szybko wrócić do tematu.

> Wpisów **nie usuwamy** — to dziennik. Stare wpisy zostają jako ślad postępu.

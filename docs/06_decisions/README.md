# 06_decisions — Architecture Decision Records (ADR)

Ta kategoria zbiera **decyzje projektowe wraz z ich uzasadnieniem** — *dlaczego* wybraliśmy
dane podejście, a nie inne. Uzupełnia pozostałe kategorie: `01_architecture/` mówi **jak** system
jest zbudowany, a `06_decisions/` mówi **dlaczego** tak jest.

## Po co to jest

Analiza (`03_reports/`) i plan (`02_plans/`) opisują *co* i *jak* zrobić. Ale samo uzasadnienie
wyboru — rozważane alternatywy, kompromisy, konsekwencje — łatwo ginie między raportem a kodem.
ADR utrwala je w jednym, krótkim, niezmiennym wpisie, żeby za pół roku (albo na innej maszynie)
nie odtwarzać rozumowania od zera.

## Kiedy pisać ADR

Twórz ADR, gdy podejmujesz decyzję, która:

- jest **trudna do odwrócenia** (wybór technologii, kształt API, model danych, granice modułów),
- **wpływa na wiele miejsc** w systemie lub wiąże ręce na przyszłość,
- **wymagała rozważenia alternatyw** (padło pytanie „A vs B?").

Nie pisz ADR dla decyzji trywialnych, lokalnych i łatwo odwracalnych.

> Naturalny moment: gdy analiza (`analyze`) rekomenduje kierunek, a Ty go akceptujesz —
> zapisz **decyzję** jako ADR, zanim rekomendacja zamieni się w plan (`plan-create`).

## Konwencja nazw

```
NNNN-slug-decyzji.md
```

- `NNNN` — kolejny numer ADR z zerami wiodącymi (`0001`, `0002`, …). **Numer jest trwały** —
  nie zmienia się nawet, gdy decyzja zostanie później wycofana lub zastąpiona.
- `slug-decyzji` — krótki, małe litery, myślniki.

Przykład: `0001-sqlite-jako-lokalne-repozytorium.md`

## Cykl życia (pole `Status`)

| Status | Znaczenie |
|--------|-----------|
| `Proponowana` | Decyzja rozważana, jeszcze nie zatwierdzona |
| `Zaakceptowana` | Obowiązująca decyzja |
| `Wycofana` | Porzucona, ale wpis zostaje dla kontekstu |
| `Zastąpiona przez ADR-NNNN` | Nieaktualna; wskaż nowszy ADR, który ją zastępuje |

**ADR-a się nie usuwa i nie przepisuje.** Gdy decyzja się zmienia — nadaj staremu wpisowi status
`Zastąpiona przez ADR-NNNN` i napisz **nowy** ADR. Historia decyzji jest tak samo cenna jak sama
decyzja. ADR-a nie przenosi się też do `99_archive/` (status `Wycofana` zostaje w miejscu).

## Jak dodać

1. Skopiuj `template.md` na `NNNN-slug.md` (następny wolny numer).
2. Wypełnij: Kontekst → Rozważane opcje → Decyzja → Konsekwencje.
3. Ustaw `Status: Zaakceptowana` (lub `Proponowana`, jeśli jeszcze dyskutujemy).
4. Jeśli ADR zastępuje inny — zaktualizuj status starego wpisu.

---
name: debug
description: Systematyczne debugowanie. Użyj przy KAŻDYM błędzie przed poprawką. Wymusza przyczynę źródłową i test odtwarzający; podczas verify cofa wadliwy plan do implementation przed zmianą kodu.
---

# debug

Dyscyplina dochodzenia do **przyczyny źródłowej** zanim cokolwiek naprawisz. Losowe poprawki
marnują czas i tworzą nowe błędy; łatka na objaw maskuje prawdziwy problem.

## Żelazne prawo

```
ŻADNEJ POPRAWKI BEZ WCZEŚNIEJSZEGO USTALENIA PRZYCZYNY ŹRÓDŁOWEJ.
```

Jeśli nie ukończyłeś Fazy 1 — **nie wolno** proponować poprawek. Złamanie litery tej procedury
jest złamaniem jej ducha.

Jeśli błąd wykryto dla planu w `docs/02_plans/verification/`, przed zmianą kodu zapisz wynik
weryfikacji, unieważnij zależne kontrole i przenieś plan do `docs/02_plans/implementation/`.

## Kiedy używać (i kiedy NIE pomijać)

Dla **każdego** problemu technicznego: nieprzechodzący test, błąd w działaniu, nieoczekiwane
zachowanie, błąd budowania, rozjazd na granicy komponentów.

**Zwłaszcza gdy** kusi „jeden szybki fix”, jesteś pod presją czasu, poprzednia poprawka nie
zadziałała, albo nie rozumiesz w pełni problemu. **Nie pomijaj**, bo „błąd wygląda na prosty” —
proste błędy też mają przyczynę źródłową, a procedura jest dla nich szybka.

> Relacja do `analyze`: `debug` to **operacyjne** dojście do root-cause konkretnego błędu,
> zakończone fixem + testem. Gdy dochodzenie odsłoni problem **architektoniczny** (patrz Faza 4,
> pkt 5) — eskaluj do `analyze` (analiza strategiczna), a wynikającą decyzję zapisz jako ADR
> w `docs/06_decisions/`.

## Cztery fazy

Każdą fazę **ukończ przed przejściem** do następnej.

### Faza 1 — Ustalenie przyczyny źródłowej

Zanim spróbujesz **jakiejkolwiek** poprawki:

1. **Przeczytaj komunikat błędu dokładnie** — cały stack trace, numery linii, klasy, kody.
   Często zawiera gotowe rozwiązanie. Nie przeskakuj ostrzeżeń.
2. **Odtwórz powtarzalnie** — czy umiesz wywołać błąd niezawodnie? Jakie dokładnie kroki? Jeśli
   nie jest powtarzalny → zbieraj więcej danych, **nie zgaduj**.
3. **Sprawdź ostatnie zmiany** — `git diff`, ostatnie commity, nowe zależności, zmiany
   konfiguracji. Co się zmieniło, co mogło to spowodować?
4. **Zbierz dowody na granicach komponentów** — zinstrumentuj każdą granicę i uruchom raz,
   żeby zobaczyć, **gdzie** się psuje:
   ```
   Dla KAŻDEJ granicy (wejście → komponent → wynik):
     - zaloguj, co WCHODZI do komponentu (argumenty, stan)
     - zaloguj, co WYCHODZI (wynik, wyjątek)
     - sprawdź, czy kontekst/konfiguracja się propaguje
   Najpierw ustal, KTÓRA warstwa zawodzi — dopiero potem badaj tę jedną warstwę.
   ```
5. **Prześledź przepływ danych wstecz** — gdy błąd jest głęboko: skąd pochodzi zła wartość?
   Co wywołało to ze złą wartością? Idź w górę aż do **źródła** i napraw u źródła, nie na objawie.
   Do szerokiej lokalizacji użyj subagenta **`explorer`**; do głębokiego śledztwa — **`thorough-analyst`**.

### Faza 2 — Analiza wzorca

1. **Znajdź działający przykład** — podobny kod w repo, który **działa**.
2. **Porównaj z referencją** — jeśli wdrażasz jakiś wzorzec, przeczytaj referencję **w całości**
   (nie skanuj). Sprawdź spec w `docs/00_specification/` i stan w `docs/01_architecture/`.
3. **Wypisz różnice** — każdą, choćby drobną, między działającym a zepsutym. Nie zakładaj
   „to nie może mieć znaczenia”.

### Faza 3 — Hipoteza i test

1. **Jedna hipoteza** — sformułuj wprost: „Przyczyną jest X, bo Y”. Konkretnie, nie mgliście.
2. **Testuj minimalnie** — **najmniejsza możliwa** zmiana sprawdzająca hipotezę. Jedna zmienna
   naraz. Nie naprawiaj kilku rzeczy jednocześnie.
3. **Zweryfikuj przed dalszym krokiem** — zadziałało? → Faza 4. Nie? → **nowa** hipoteza
   (nie dokładaj kolejnych poprawek na wierzch).
4. **Gdy nie wiesz** — powiedz „nie rozumiem X”, nie udawaj. Dobierz więcej danych albo poproś
   o pomoc.

### Faza 4 — Wdrożenie poprawki

1. **Napisz test odtwarzający błąd** — najprostsza reprodukcja w katalogach testów: `tests`.
   **Musisz go mieć przed poprawką** — czerwony test dowodzi, że problem istnieje.
2. **Jedna poprawka** — adresuj **przyczynę źródłową**, jedna zmiana naraz. Żadnych „przy okazji”
   refaktorów.
3. **Zweryfikuj**: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v` — czerwony test jest teraz zielony? Żaden inny test się nie
   wywalił? (Wdrożenie możesz delegować do subagenta **`code-implementer`**.)
4. **Gdy poprawka nie działa** — STOP. Policz próby. Jeśli < 3 → wróć do Fazy 1 z nową wiedzą.
   **Jeśli ≥ 3 → nie próbuj czwarty raz**, przejdź do pkt 5.
5. **Gdy 3+ poprawek zawiodło — zakwestionuj architekturę.** Wzorzec problemu architektonicznego:
   każdy fix odsłania nowy współdzielony stan/sprzężenie gdzie indziej, fixy wymagają „wielkiego
   refaktoru”, każdy tworzy nowe objawy. **To nie jest błędna hipoteza — to zła architektura.**
   Zatrzymaj się, **eskaluj do `analyze`** i przedyskutuj z użytkownikiem, zanim spróbujesz dalej.

## Czerwone flagi — STOP, wróć do Fazy 1

Jeśli łapiesz się na myśli:
- „Szybki fix teraz, zbadam później”
- „Spróbuję zmienić X i zobaczę, czy zadziała”
- „Zmienię kilka rzeczy naraz i puszczę testy”
- „Pominę test, sprawdzę ręcznie”
- „Pewnie chodzi o X, naprawię to” (przed prześledzeniem przepływu danych)
- „Jeszcze jedna próba” (gdy już były 2+)

**Wszystkie znaczą: STOP. Wróć do Fazy 1.** Przy 3+ nieudanych — kwestionuj architekturę.

## Typowe wymówki

| Wymówka | Rzeczywistość |
|---------|---------------|
| „Błąd prosty, procedura zbędna” | Proste błędy też mają root-cause; procedura jest dla nich szybka. |
| „Nie ma czasu, to pilne” | Systematyczne debugowanie jest SZYBSZE niż zgadywanka i cofanie zmian. |
| „Najpierw spróbuję, potem zbadam” | Pierwsza poprawka nadaje ton. Zrób dobrze od początku. |
| „Test napiszę po potwierdzeniu fixu” | Nieprzetestowane poprawki się nie utrzymują. Czerwony test najpierw dowodzi problemu. |
| „Kilka fixów naraz oszczędzi czas” | Nie wyizolujesz, co zadziałało; rodzi nowe błędy. |

## Zamknięcie
- Po naprawie: jeśli błąd był nietrywialny — odnotuj wniosek w `worklog-save`.
- Jeśli dochodzenie zakończyło się **decyzją architektoniczną** — zapisz ADR w `docs/06_decisions/`.
- „Brak przyczyny źródłowej” (błąd czysto środowiskowy/czasowy) to prawda w ~5% przypadków —
  pozostałe 95% to niedokończone śledztwo. Zanim tak uznasz, udokumentuj, co sprawdziłeś.

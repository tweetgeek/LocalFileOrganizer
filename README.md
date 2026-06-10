# Local File Organizer (lfo)

CLI do katalogowania i reorganizacji plikow na lokalnym dysku.

## Instalacja

    python -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"

## Uzycie

Dry-run (domyslnie, nic nie rusza):

    lfo run --config examples/lfo.yaml

Wykonanie:

    lfo run --config examples/lfo.yaml --apply

Cofniecie ostatniego przebiegu (sciezka bazy z konfiguracji):

    lfo undo last --config examples/lfo.yaml

albo wskaz baze bezposrednio:

    lfo undo last --db ./.lfo_cache.sqlite

Parametry bez pliku konfiguracyjnego:

    lfo run --source ./balagan --dest ./uporzadkowane --mode type --apply

## Tryby klasyfikacji bazowej

- `type` — folder na kazde rozszerzenie (zip/, stl/, ...)
- `category` — mapa rozszerzenie -> kategoria (z sekcji `categories`)

Duplikaty (po hashu) trafiaja do `duplikaty/`, pliki bez dopasowania do `unsorted/`.
Pliki zabezpieczone haslem sa wykrywane i oznaczane w raporcie.

## Bezpieczenstwo

- Domyslnie **dry-run** — realne przeniesienie tylko z flaga `--apply`.
- Nigdy nie nadpisujemy istniejacych plikow (auto-rename albo pominiecie).
- Kazdy `--apply` zapisuje log w SQLite, ktory mozna cofnac (`lfo undo`).

## Wymagania zewnetrzne

Wykrywanie hasla dla archiwow `.rar` wymaga zewnetrznego narzedzia `unrar`
lub `bsdtar` w PATH. Jego brak nie powoduje bledu — taki plik jest po prostu
traktowany jako niezabezpieczony (detekcja jest best-effort).

## Klasyfikacja AI (Ollama)

Gdy `ai.enabled: true`, dla rozszerzen z `ai.extensions` aplikacja czyta tresc,
wysyla fragment do Ollamy i przypisuje podkategorie z `ai.taxonomy`
(np. `dokumenty/faktury/`). Niepewne wyniki (ponizej `confidence_threshold`)
i sugestie nowych kategorii trafiaja do `do_przejrzenia/`. Wyniki sa
cache'owane po hashu pliku — duplikaty i ponowne uruchomienia nie wolaja
modelu. Przy niedostepnej Ollamie `on_error: fallback` schodzi do trybu
bazowego (a `abort` przerywa z czytelnym komunikatem).

Wymaga uruchomionej Ollamy (`ollama serve`) i pobranego modelu
(`ollama pull llama3.2`).

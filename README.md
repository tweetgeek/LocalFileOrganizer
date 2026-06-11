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

## Klasyfikacja AI (Ollama / OpenAI-compatible)

Gdy `ai.enabled: true`, dla rozszerzen z `ai.extensions` aplikacja czyta tresc,
wysyla fragment do Ollamy i przypisuje podkategorie z `ai.taxonomy`
(np. `dokumenty/faktury/`). Niepewne wyniki (ponizej `confidence_threshold`)
i sugestie nowych kategorii trafiaja do `do_przejrzenia/`. Wyniki sa
cache'owane po hashu pliku — duplikaty i ponowne uruchomienia nie wolaja
modelu. Przy niedostepnej Ollamie `on_error: fallback` schodzi do trybu
bazowego (a `abort` przerywa z czytelnym komunikatem).

Wymaga uruchomionej Ollamy (`ollama serve`) i pobranego modelu
(`ollama pull llama3.2`).

### Inne backendy (OpenAI-compatible)

Zamiast Ollamy mozna uzyc dowolnego serwera zgodnego z OpenAI API
(LM Studio, llama.cpp server, vLLM, LocalAI, a takze Ollama przez `/v1`).
Ustaw w konfiguracji:

    ai:
      provider: openai
      endpoint: http://localhost:1234/v1   # LM Studio: baza z /v1
      model: google/gemma-4-e4b            # nazwa modelu zaladowanego w serwerze
      api_key: null                        # opcjonalnie, dla serwerow wymagajacych klucza

Klient wysyla `POST /chat/completions` z `response_format: json_object` i
`temperature: 0`. Male modele (np. Gemma 4B) bywaja mniej karne w formacie
JSON — pojedyncza wadliwa odpowiedz jest pomijana (plik leci dalej), a trwaly
blad serwera (np. 401 zly klucz, 404 zly model) przerywa caly etap AI
(w trybie `fallback` schodzi do trybu bazowego, w `abort` daje czytelny blad).

# Local File Organizer — specyfikacja projektu

- **Data:** 2026-06-09
- **Status:** zaakceptowany do planowania implementacji
- **Język/stack:** Python 3.13 (środowisko `.venv` już istnieje)

## 1. Cel

Narzędzie CLI do katalogowania i reorganizacji plików oraz katalogów na lokalnym
dysku. Skanuje katalog roboczy, klasyfikuje pliki (po typie/kategorii oraz
opcjonalnie po treści za pomocą lokalnego modelu w Ollamie), przenosi je do
uporządkowanej struktury i generuje podsumowanie (ile przeniesiono, ile zajmują,
duplikaty, pliki zabezpieczone hasłem).

Uruchamiane przez plik konfiguracyjny YAML lub parametry CLI (CLI nadpisuje YAML).

## 2. Decyzje kierunkowe

| Obszar | Decyzja |
|---|---|
| Architektura | Hybryda: jednorazowa reorganizacja + **undo log** + **cache klasyfikacji AI** po hashu pliku. Brak trwałej bazy katalogu. |
| Bezpieczeństwo | **Dry-run domyślnie**; realne przeniesienie po fladze `--apply`. Operacja **move**. Undo log umożliwia cofnięcie. |
| Klasyfikacja | Jeden **tryb bazowy** wybierany w configu: `type` (folder per rozszerzenie) **albo** `category` (mapa rozszerzenie→kategoria). **AI** jako opcjonalna nakładka doprecyzowująca podkatalog. |
| Logika AI | **Zamknięta taksonomia** z configu (preferowana); przy niskiej pewności lub nowej sugestii → folder `do_przejrzenia/`. AI nie tworzy automatycznie nowych folderów najwyższego poziomu. |
| Duplikaty | Wykrywanie po **hashu treści** (SHA-256 z pre-filtrem rozmiaru). Działanie: **kwarantanna** — oryginał organizowany normalnie, pozostałe kopie → `duplikaty/`. |
| Zakres skanu | **Rekurencyjnie** z konfigurowalnym `max_depth`, listą `ignore` i pomijaniem symlinków. |
| Pliki z hasłem | **Wykrywaj i flaguj** (pdf/zip/7z/rar/office); organizuj trybem bazowym, AI pomijane. |
| Podejście | A — **modularny potok** z solidnymi zależnościami (Typer, pydantic, klient Ollamy, SQLite). |

## 3. Architektura i przepływ

Potok pięciu etapów, każdy jako osobny, testowalny moduł:

```
scan ─▶ analyze ─▶ plan ─▶ apply ─▶ report
 │         │          │        │        │
skaner   hash +       budowa   move +   konsola
+ignore  klasyfikacja decyzji  undo-log + JSON
+depth   + hasła      +konfl.  +kwarant.
         (cache AI)
```

„Plan" to serializowalny obiekt — sedno bezpieczeństwa. Dry-run go tylko wypisuje;
`--apply` wykonuje dokładnie ten sam Plan.

### Przepływ decyzji per plik (etap `analyze`)

1. Hash treści → grupowanie duplikatów (pierwsza kopia wg posortowanej ścieżki =
   „oryginał"; reszta → `duplikaty/`).
2. Detekcja zabezpieczenia hasłem → flaga w raporcie, AI pominięte.
3. Klasyfikacja:
   - **tryb bazowy** (`type`/`category`) ustala folder docelowy;
   - jeśli AI włączone dla rozszerzenia i plik czytelny → **nakładka AI**
     doprecyzowuje podkatalog z taksonomii;
   - cache po hashu — duplikaty i ponowne uruchomienia nie wołają Ollamy.
4. Niepewna klasyfikacja AI (poniżej progu) lub nowa sugestia → `do_przejrzenia/`.
   Brak dopasowania trybu bazowego → `unsorted/`.
5. Konflikt nazw w docelowym → auto-rename z sufiksem (nigdy nadpisanie).

## 4. Struktura projektu

```
local_file_organizer/
  cli.py          # Typer: komendy `run`, `undo`; scalanie CLI + YAML
  config.py       # modele pydantic, loader YAML, walidacja
  models.py       # FileEntry, PlannedMove, Plan, Report (dataclasses)
  scanner.py      # walk + ignore + max_depth + symlinks → FileEntry[]
  hashing.py      # sha256 z pre-filtrem rozmiaru; grupowanie duplikatów
  security.py     # detekcja haseł: pdf/zip/7z/rar/office
  classify/
    base.py       # tryb type/category → folder bazowy
    ai.py         # klient Ollamy, prompt z taksonomią, próg pewności
    extractors.py # ekstrakcja tekstu per rozszerzenie
  planner.py      # FileEntry[] + klasyfikacja → Plan (konflikty, kwarantanna)
  executor.py     # wykonanie Plan (move) + zapis undo-log
  undo.py         # odczyt logu i odwrócenie przeniesień
  cache.py        # SQLite: cache AI po hashu
  report.py       # konsola (rich) + JSON/MD
pyproject.toml
tests/            # pytest, po module
```

**Zależności:** `typer`, `pydantic`, `pyyaml`, `httpx`/klient ollama, `pypdf`,
`pikepdf`, `msoffcrypto-tool`, `py7zr`, `rarfile`, `python-docx`/`docx2txt`,
`rich`. Testy: `pytest`.

## 5. Konfiguracja (YAML + CLI)

Domyślnie **dry-run**; `--apply` wykonuje. CLI nadpisuje YAML.
Komendy: `lfo run [--config lfo.yaml] [--apply]` oraz `lfo undo <id|last>`.

```yaml
source_dir: /sciezka/balagan
dest_dir:   /sciezka/uporzadkowane
mode: category            # "type" | "category"
recursive: true
max_depth: 5
ignore: [".git", "node_modules", ".*"]
follow_symlinks: false

categories:               # tylko dla mode: category
  apps:      [zip, dmg, exe, pkg]
  3dprint:   [stl, 3mf, obj, gcode]
  dokumenty: [pdf, doc, docx, odt]
  obrazy:    [jpg, png, gif, webp]

unknown_dir:    unsorted
duplicates_dir: duplikaty
review_dir:     do_przejrzenia
conflict:       rename     # rename | skip (nigdy overwrite)

dedup:   { method: hash, action: quarantine }
password_detection: { enabled: true, formats: [pdf, zip, 7z, rar, docx, xlsx] }

ai:
  enabled: true
  provider: ollama
  endpoint: http://localhost:11434
  model: llama3.2
  extensions: [pdf, txt, md, docx]   # które pliki czytamy dla AI
  max_chars: 4000                    # ile tekstu wysyłamy do modelu
  confidence_threshold: 0.7          # poniżej → do_przejrzenia
  on_error: fallback                 # fallback do trybu bazowego | abort
  allow_suggestions: true            # nowa kategoria → do_przejrzenia
  taxonomy:
    faktury: "zawiera NIP, słowo 'faktura', kwoty, dane firmy"
    umowy:   "zawiera 'umowa', strony, paragrafy"

report: { format: [console, json], output: ./lfo-report.json }
cache:  { enabled: true, path: ./.lfo_cache.sqlite }
```

Walidacja przez pydantic: istnienie `source_dir`, sensowność `mode`,
niesprzeczne ścieżki, poprawne wartości enumów (`conflict`, `dedup.action`,
`ai.on_error`).

## 6. Bezpieczeństwo, undo i konflikty

- **Dry-run vs apply.** Bez `--apply` potok kończy się na zbudowaniu i wypisaniu
  Planu. Z `--apply` `executor` wykonuje ten sam Plan.
- **Undo log.** Każdy `run --apply` tworzy w SQLite rekord przebiegu z `id`
  (znacznik czasu) i listą wykonanych przeniesień (`src → dst`) oraz utworzonych
  folderów. Log zapisywany inkrementalnie podczas `apply` → nawet częściowy
  przebieg da się cofnąć. `lfo undo <id|last>` przesuwa pliki z powrotem i usuwa
  puste utworzone foldery.
- **Konflikty nazw.** Gdy w docelowym istnieje plik o tej nazwie → auto-rename
  `nazwa (1).ext`, `nazwa (2).ext`. **Nigdy nie nadpisujemy.** Przy
  `conflict: skip` plik zostaje w miejscu i trafia do raportu jako pominięty.
- **Duplikaty.** Grupowanie po hashu (pre-filtr rozmiarem). „Oryginał" = pierwszy
  wg posortowanej ścieżki (deterministycznie), organizowany normalnie; reszta →
  `duplikaty/`. Raport wskazuje oryginał każdej grupy.
- **Guardy.** `dest_dir` automatycznie wykluczony ze skanu; odmowa przy
  zagnieżdżeniu `source`/`dest` powodującym pętlę; błędy uprawnień per plik →
  log + pomiń + kontynuuj.

## 7. Wykrywanie haseł i ekstrakcja tekstu

**Detekcja zabezpieczeń (best-effort, bez prób łamania):**

| Format | Metoda |
|---|---|
| `pdf` | `pypdf`/`pikepdf` (`is_encrypted`) |
| `zip` | flaga szyfrowania w nagłówku (`zipfile`, bez rozpakowania) |
| `7z` | `py7zr.needs_password()` |
| `rar` | `rarfile.needs_password()` |
| `docx/xlsx/pptx` | `msoffcrypto-tool` (`is_encrypted()`) |

Plik zabezpieczony: organizowany trybem bazowym (znamy rozszerzenie), AI
pominięte, flaga w raporcie. Błąd detekcji → traktowany jako nieczytelny + log.

**Ekstrakcja tekstu (tylko dla rozszerzeń z `ai.extensions`):** `txt/md/csv`
wprost; `pdf` przez `pypdf`; `docx` przez `python-docx`/`docx2txt`. Wycinamy
pierwsze `max_chars` znaków. Brak ekstraktora → AI pomijane, plik leci trybem
bazowym.

## 8. Klasyfikacja AI

Prompt z **zamkniętą taksonomią** (klucze + podpowiedzi z configu). Model dostaje
nazwę pliku + wycinek tekstu i zwraca **JSON**:

```json
{ "category": "<klucz | nieznane | sugestia>", "confidence": 0.0, "suggested_name": "<opcjonalnie>" }
```

- `category` z taksonomii i `confidence ≥ threshold` → podkatalog kategorii
  (np. `dokumenty/faktury/`).
- `confidence < threshold` lub `nieznane` → `do_przejrzenia/`.
- `allow_suggestions` + nowa nazwa od modelu → `do_przejrzenia/`, sugestia w
  raporcie (**nie** tworzymy automatycznie nowego folderu najwyższego poziomu).

**Cache (SQLite):** klucz = `hash pliku + model + hash taksonomii`. Zmiana
taksonomii/modelu unieważnia wpis. Duplikaty i ponowne uruchomienia nie wołają
Ollamy. `on_error: fallback` → przy braku połączenia pomijamy AI i schodzimy do
trybu bazowego z ostrzeżeniem; `abort` → przerywamy.

## 9. Raport i podsumowanie

Konsola (tabele `rich`) zawsze; JSON/MD opcjonalnie. W dry-run sformułowania
w trybie „zostałoby przeniesione". Zawartość (pokrywa brief):

- **Przeniesiono:** liczba plików + **rozmiar na dysku** (np. „1,2 GB"), rozbicie
  per folder docelowy.
- **Duplikaty:** liczba grup i plików, lista ze wskazaniem oryginału.
- **Zabezpieczone hasłem:** lista plików + format.
- **Do przejrzenia / unsorted / pominięte / błędy:** liczby + listy.
- **Skrót klasyfikacji:** ile trybem bazowym vs AI, ile z cache.

## 10. Testowanie i obsługa błędów

TDD per moduł (`pytest`). Testy na syntetycznych plikach w `tmp_path`; **klient
Ollamy mockowany** (żadnych wywołań sieci w testach); małe próbki zaszyfrowanych
plików jako fixtures do detekcji haseł. „Golden" testy `planner` (te same
wejścia → ten sam Plan).

Krytyczne ścieżki do pokrycia:

- dry-run niczego nie rusza,
- `apply` + `undo` wraca do stanu wyjściowego,
- konflikt nie nadpisuje,
- `dest_dir` wykluczony ze skanu,
- `on_error: fallback` działa przy niedostępnej Ollamie,
- detekcja haseł dla każdego wspieranego formatu.

Obsługa błędów: brak `source_dir` → błąd i wyjście; błędy uprawnień per plik →
log + kontynuacja; częściowy `apply` → sukcesy zapisane w undo logu, porażki
w raporcie.

## 11. Poza zakresem (YAGNI dla MVP)

- Trwała baza katalogu/indeks plików w czasie.
- Architektura wtyczkowa (entry points) — modularność i tak ją później ułatwi.
- Inni dostawcy AI niż Ollama (interfejs zostawiamy czysty, ale implementujemy
  tylko Ollamę).
- Kopiowanie zamiast przenoszenia (tylko `move` w MVP).
- GUI / interfejs webowy.

# NinjaNodeEditor

[English](README.md) · [Magyar](README.hu.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Polski](README.pl.md) · [Srpski](README.sr.md) · [Español](README.es.md)

Wizualny edytor logiki PLC i generator komponentów HAL LinuxCNC, napisany w Pythonie z PySide6. Twórz typowane grafy, symuluj je lokalnie i eksportuj cały projekt jako `.comp`. Edytor działa bez LinuxCNC na pulpicie lub bezpośrednio na ekranie Raspberry Pi przez Qt EGLFS/KMS. Interfejs zaprojektowano dla 800 × 600.

[Szczegółowa polska instrukcja](docs/USER_GUIDE.pl.md) · [Licencja MIT](LICENSE)

## Funkcje

- Counter: Zliczanie w górę/w dół na zboczu narastającym, reset, włączenie, wartość s32 i sygnał progu. [counter.json](examples/counter.json).
- Timer: start zboczem, reset, całe ms i wyjście poziom/impuls; szczegóły w instrukcji.
- Typy `bit`, `float`, `s32`, `u32`; automatyczna konwersja oznaczona czerwonym tekstem.
- Wejścia wykrywane w wyrażeniach, matematyka, porównania, logika i przesunięcia `<<`/`>>`.
- Eliminacja drgań i zbocza na wejściu; opóźnienia ON/OFF i inwersja na wyjściu.
- FIFO `last`/`now` z automatycznym dziedziczeniem typu.
- PID z ograniczeniami, anti-windup, filtrem D, opcjonalnym feedforward i wyjściem error.
- Komunikaty błędów z wyzwalaniem, blokadą czasową i resetem.
- Parametry `@name` eksportowane jako regulowane wejścia HAL.
- Szablony Math, moduły edycji i grupowany monitor symulacji.
- Siedem języków z instrukcjami; przywracanie ostatniego projektu.
- Grupy Project, Settings, Modules, Nodes; pełny ekran w prawym dolnym rogu i właściwości zależne od zaznaczenia.

## Instalacja i uruchamianie

Python 3 i PySide6 według [requirements.txt](requirements.txt). Aktualne środowisko rozwojowe używa Pythona 3.13. LinuxCNC nie jest potrzebny do edycji ani symulacji.

Po pobraniu lub sklonowaniu:

```sh
cd NinjaNodeEditor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./run.sh --windowed
```

Interpreter można wskazać: `PLC_PYTHON="$PWD/.venv/bin/python" ./run.sh --windowed`.

DietPi ze zgodnymi systemowymi pakietami Qt/PySide6:

```sh
cd ~/NinjaNodeEditor
bash ./setup-dietpi.sh
./run-eglfs.sh
```

Skrypt aktualizuje apt i instaluje pakiety przez sudo. EGLFS domyślnie wybiera `/usr/bin/python3`, niezależnie od aktywnego venv. Uruchamiaj z lokalnej konsoli, z wolnym ekranem i uprawnieniami do urządzeń. `QT_QPA_EGLFS_KMS_CONFIG` wybiera własny profil; profil card1 wymaga odpowiedniego układu urządzeń DRM.

## Obsługa

```sh
./run.sh --windowed --project examples/bit-to-u32.json
```

Dodawaj węzły w Nodes, ustawiaj właściwości i łącz porty. Podczas Simulate prawy panel pokazuje wszystkie moduły; wejścia i parametry można zmieniać. Po zatrzymaniu właściwości są widoczne tylko dla zaznaczonego węzła. Przycisk w prawym dolnym rogu lub F11 włącza pełny ekran; nad grafem pozostaje tylko Nodes.

Ctrl+S zapisuje, Delete usuwa; kółko zmienia skalę, przeciąganie tła przesuwa widok. Strukturę podłączonego Math/Condition zmieniaj dopiero po Disconnect all.

`--project path.json` wybiera projekt, `--no-restore`/`--empty` uruchamia pusty, `--language pl` wybiera język. Opcje projektu i pustego startu wykluczają się. Preferencje: `.state/`, alternatywnie `PLC_STATE_DIR`. Niezapisane zmiany nie zapisują się automatycznie.

## Eksport i kompatybilność

Export tworzy `.comp`; Build .so lub:

```sh
halcompile --compile machine_plc.comp
```

Wymagane są narzędzia programistyczne LinuxCNC i kompilator C. Operacja nie instaluje/ładuje modułu. Kompiluj dla architektury docelowej, a `update` dodaj do HAL servo-thread. Wszystkie moduły eksportują się jako jeden komponent.

Eksport używa `pin_set(...)` API 2.10 z obsługą starszego halcompile 2.9. Sprawdzenia: kompilacja na zainstalowanym 2.9 oraz obecny generator/nagłówki 2.10; bez uruchamiania zainstalowanego 2.10. Po zmianie wersji eksportuj i kompiluj ponownie.

## Przykłady i rozwój

[examples](examples): bity→U32, konwersje, kierunek kołowy, różnica FIFO, PID/feedforward i komunikaty. Kierunek kołowy nie jest pełną wymianą narzędzia. [templates](templates): szablony Math; [locales](locales): katalogi UTF-8.

Testy z PySide6 i kompilatorem `cc`:

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest test_model test_session test_ui test_i18n
```

Symulacja nie steruje sprzętem. To eksperymentalny edytor skończonego przepływu danych; cykle grafu, polecenia ruchu i aktywny monitor HAL nie są obsługiwane. Display nie wydaje polecenia abort NC. Instrukcja szczegółowo opisuje instalację, węzły i diagnostykę.

## Licencja

[MIT License](LICENSE), © 2026 NinjaNodeEditor contributors. Python, PySide6/Qt i LinuxCNC zachowują własne licencje.

## Logger: zapis historii przez trigger

**+ Logger** ma 1–18 wejść `in1`, `in2` itd. Typ (bit, float, s32, u32) wynika ze źródła; zapisywane są moduł, symbol i nazwa wyjścia. Niepodłączone wejście daje float 0. Zbocze narastające `trigger` zapisuje bufor od najstarszej próbki. HIGH zapisuje raz; przed następnym wyzwoleniem ustaw LOW. Zapis nie czyści historii.

## Globalne I/O i debugowanie Live HAL

**Globalne I/O** zarządza wspólnymi wejściami/wyjściami widocznymi we wszystkich obecnych i nowych modułach. Każdy sygnał ma jedną definicję i jeden eksportowany pin. Pozycje bloków są zapamiętywane osobno; przeciągaj ramkę/nagłówek, edytuj dwuklikiem w liście. Zwykły Input/Output można ustawić jako globalny. Usunięcie kasuje wszystkie jego połączenia. Wyjście globalne ma jedno źródło; odłącz przed zmianą. Etykieta lub **Przejdź do źródła** otwiera moduł i zaznacza node.

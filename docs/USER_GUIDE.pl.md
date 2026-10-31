# NinjaNodeEditor — szczegółowa instrukcja obsługi

NinjaNodeEditor służy do edycji logiki całego komponentu PLC jako grafu węzłów, lokalnej symulacji i eksportu źródła LinuxCNC `.comp`. Symulator nie łączy się z działającym HAL ani sprzętem. **Build .so** tylko kompiluje; instalacja i ładowanie są osobnymi czynnościami.

## Spis treści

1. Uruchamianie i język
2. Interfejs i edycja
3. Projekty i moduły
4. Typy i konwersja
5. Węzły
6. Wyrażenia i odwołania
7. Szablony Math
8. Symulacja i diagnostyka
9. Eksport, kompilacja i integracja HAL
10. Przykłady
11. Rozwiązywanie problemów
12. LinuxCNC 2.9 / 2.10

## 1. Uruchamianie i język

Na Raspberry Pi, z katalogu aplikacji:

```sh
cd ~/NinjaNodeEditor
./run-eglfs.sh
```

Na pulpicie użyj `./run.sh --windowed`. EGLFS wymaga zgodnych bibliotek Qt EGLFS/KMS i dostępu do ekranu oraz urządzeń wejściowych. Ekran może być zajęty przez inną aplikację. Na DietPi polecenie `bash ./setup-dietpi.sh` instaluje zgodne pakiety systemowe. Skrypt EGLFS domyślnie używa `/usr/bin/python3`. Inny interpreter wybierz jawnie:

```sh
PLC_PYTHON="$PWD/.venv/bin/python" ./run-eglfs.sh
```

| Opcja | Działanie |
| --- | --- |
| `--project path.json` | Otwiera wskazany projekt zamiast zapamiętanego pliku. |
| `--no-restore` / `--empty` | Uruchamia pusty graf bez odczytywania ostatniego projektu. |
| `--windowed` | Żąda trybu okienkowego. |
| `--language pl` | Wybiera język startowy. |
| `--screenshot /tmp/preview.png` | Zapisuje zrzut i kończy pracę. |

`--project` i `--no-restore` wzajemnie się wykluczają. Dostępne języki: angielski (`en`), węgierski (`hu`), niemiecki (`de`), francuski (`fr`), polski (`pl`), serbski alfabetem łacińskim (`sr`) i hiszpański (`es`). Zmiana działa natychmiast i jest zapamiętywana. `--language` lub `PLC_LANGUAGE` nadpisuje język startowy; domyślny to angielski. **Manual** otwiera instrukcję w wybranym języku, a przy braku pliku po angielsku.

Identyfikatory, formuły, nazwy modułów/szablonów i własne komunikaty nie są tłumaczone. Preferencje są w `.state/`; `PLC_STATE_DIR` wybiera inny katalog.

## 2. Interfejs i edycja

Górne grupy to Projekt, Ustawienia, Moduły i Węzły, w tej kolejności. Zawierają operacje plikowe, język/instrukcję/symulację, organizację modułów i dodawanie węzłów. Graf znajduje się po lewej, właściwości po prawej.

Grupy narzędzi to **Projekt**, **Ustawienia**, **Moduły**, **Węzły**, w tej kolejności. **Pełny ekran** w prawym dolnym rogu lub **F11** pozostawia nad grafem tylko grupę Węzły. Ten sam przycisk lub F11 przywraca zwykły widok; na EGLFS fizyczny ekran pozostaje pełnoekranowy. Po zatrzymaniu symulacji właściwości pokazują się tylko dla zaznaczonego węzła; kliknięcie pustego tła je ukrywa i powiększa obszar grafu. Podczas symulacji monitor jest widoczny bez zaznaczenia. Zmiana widoku zachowuje graf i historię.

Projekt, Ustawienia i Moduły są zwartymi wierszami z etykietą na początku. Węzły zachowują ramkę z tytułem, oszczędzając miejsce na małym ekranie.

| Czynność | Obsługa |
| --- | --- |
| Tworzenie/wybór/przenoszenie węzła | Odpowiedni przycisk `+`; kliknięcie lub przeciągnięcie korpusu. |
| Wybór wielu węzłów | Ctrl i kliknięcie. |
| Łączenie | Kliknij wyjście, potem wejście, albo przeciągnij połączenie. |
| Anulowanie połączenia | Escape. |
| Przesuwanie widoku / skala | Przeciąganie pustego tła / kółko myszy. |
| Cały graf w widoku | **Fit**. |
| Usuwanie / zapis | Delete / Ctrl+S lub odpowiedni przycisk. |

Żółte wejścia odbierają sygnały, niebieskie wyjścia je wysyłają. Wejście ma jedno źródło; nowe połączenie zastępuje poprzednie. **Disconnect inputs** usuwa przewody wejściowe, **Disconnect all** wszystkie połączenia węzła.

Zmiany tekstu są zatwierdzane po opuszczeniu pola. W wyrażeniu Enter zatwierdza, Shift+Enter dodaje wiersz. Liczby zatwierdza się po zakończeniu wpisywania, bez wykonywania każdej niepełnej wartości pośredniej.

## 3. Projekty i moduły

JSON przechowuje węzły, parametry, przewody, pozycje i moduły. Zwykły start przywraca ostatni pomyślnie otwarty lub zapisany projekt; bez zapamiętanego pliku pojawia się demonstracja. Niezapisane zmiany nie zapisują się automatycznie. **New** tworzy pusty graf, nie kasując zapamiętanej ścieżki. Brak lub uszkodzenie pliku powoduje pusty start i komunikat; użyj **Open**.

Moduły porządkują edycję jednego komponentu. **New module** tworzy grupę, **Rename** zmienia nazwę, **Move selected** przenosi węzły. **Remove module** przenosi jego węzły do pierwszego pozostałego modułu i zachowuje połączenia; co najmniej jeden moduł musi pozostać. **All modules** pokazuje cały graf i umożliwia połączenia między modułami.

Ukryte połączenia nadal działają. Podpowiedź portu wskazuje drugi moduł i węzeł. Symulacja, stałe i nazwy HAL są globalne; eksport obejmuje wszystkie moduły. Nowy węzeł należy do wybranego modułu, a w widoku całości do pierwszego. Format 4 zachowuje organizację. Formaty 1–3 są czytelne i umieszczają stare węzły w Main; starszy edytor może nie czytać formatu 4.

## 4. Typy i konwersja

| Typ | Znaczenie |
| --- | --- |
| `bit` | 0 lub 1; każda liczba niezerowa oznacza prawdę. |
| `float` | Liczba zmiennoprzecinkowa podwójnej precyzji. |
| `s32` | Ze znakiem, −2147483648…2147483647. |
| `u32` | Bez znaku, 0…4294967295. |

Różne typy można połączyć. Konwersja na wejściu odbiorcy jest automatyczna i oznaczona czerwonym tekstem. Konwersja całkowita obcina w kierunku zera i ogranicza do zakresu: `3.9` → s32 `3`, `-2` → u32 `0`.

Eliminacja drgań, opóźnienia ON/OFF, odstęp komunikatów i filtr D PID używają całych milisekund z krokiem 1 ms. Zero wyłącza opóźnienie/filtr. Rzeczywista rozdzielczość wynika z okresu aktualizacji; symulacja 20 ms nie rozróżnia pojedynczych zdarzeń 1 ms.

## 5. Węzły

### Input

Nazwane zewnętrzne wejście HAL. Nazwa jest unikalna, zaczyna się małą literą i może zawierać cyfry oraz myślniki, np. `pressure`, `door-closed`. **Simulated input** podaje lokalną surową wartość. Bit można też przełączyć kliknięciem tekstu stanu symulowanego na węźle.

Przetwarzanie bitu: inwersja, eliminacja drgań, wyzwalanie. Zmieniony stan musi pozostać stabilny przez zadany czas. `level` daje stabilny poziom; `rising`, `falling`, `both` dają impuls długości jednej aktualizacji. Początkowo aktywne wejście może dać impuls narastający. Eksport czyta rzeczywisty pin HAL; wartość symulowana nie zastępuje połączenia sprzętowego.

### Output

Wyjście HAL z portem `in`. Bez połączenia używa wartości/stanu początkowego. Opóźnienia ON/OFF wymagają utrzymania żądania; jego cofnięcie anuluje oczekujące przejście. Inwersja następuje po opóźnieniu. Stan początkowy ustala zapamiętany stan logiczny przy starcie.

### Const

Nazwany parametr z typem i wartością domyślną, bez portów. Formuły używają `@gain`, pola liczbowe mają wybór referencji. Nazwy zaczynają się małą literą i mogą zawierać cyfry oraz podkreślenia. `@speed_limit` eksportuje się jako `<component>.speed-limit`.

Każda Const staje się **pinem wejściowym HAL** z wartością domyślną i może być zmieniana przez `setp` lub sygnał. Własna wartość domyślna musi być dosłowna, nie kolejną referencją. Przed usunięciem używanej Const usuń odwołania do niej.

### Math i Condition

Zmienne wyrażenia automatycznie tworzą wejścia. Każda ma typ, źródło i wartość domyślną. **Input port** tworzy port; **Constant** używa podanej wartości bez portu. Wartości zmiennych mogą używać `@name`.

Math daje wyjście `result` z wyborem typu. Condition daje dopełniające bity `true` i `false`, nie gałęzie wykonania. Podłączone węzły blokują zmiany struktury formuły, typów, źródeł i szablonów do czasu **Disconnect all**.

### Invert

Logiczne NIE bitu. Niepodłączone wejście to 0, więc wyjście wynosi 1.

### FIFO

`now` to bieżąca próbka, `last` próbka poprzedniej aktualizacji. Przy pierwszej aktualizacji `last` jest wartością początkową. Typ podłączonego źródła określa typy wszystkich portów; bez połączenia można wybrać typ zastępczy.

Próbkowanie odbywa się raz na aktualizację, także dla niezmienionej wartości. To historia dwóch próbek, nie kolejka push/pop. Cykle sprzężenia w grafie pozostają niedozwolone, ponieważ `now` zależy od bieżącego wejścia.

### Timer / przekroczenie czasu

**+ Timer** ma wejścia bit `trigger`, `reset` i wyjście bit `out`. **Czas ms** to nieujemna liczba całkowita, krok 1 ms, domyślnie 1000; można użyć Const. Narastające zbocze uruchamia timer, także początkowo wysoki trigger przy pierwszej aktualizacji. Opadający trigger nie przerywa; zbocza podczas pracy są ignorowane. Czas jest pobierany przy starcie i nie zmienia się w tym przebiegu. Licznik zaczyna od 0, kolejne aktualizacje dodają okres. Zero upływa natychmiast.

Tryb `level`: po upływie `out=1` aż do resetu, bez dalszych startów. `pulse`: 1 przez jedną aktualizację, następnie 0; nowe zbocze może uruchomić ponownie. Reset działa poziomem i ma pierwszeństwo: HIGH przerywa i zeruje wyjście. Trigger utrzymany wysoko przez reset nie uruchomi po jego zwolnieniu; musi opaść i wzrosnąć. Reset w cyklu upływu blokuje wyjście. Niepodłączone wejścia są 0. Symulacja ma krok 20 ms; HAL używa okresu wątku. Niepoprawny/niedodatni okres zeruje stan.

Timeout: start operacji na trigger, pomyślne zakończenie na reset. Poziom do zapamiętanego błędu, impuls do pojedynczego powiadomienia. [timeout.json](../examples/timeout.json): 1000 ms, wyjście HAL timeout i Display. Start/stop symulacji zeruje historię.

### PID

Wejścia: `setpoint`, `feedback`, `enable`, `reset`. Wyjścia float: `out`, `error`. Podczas pracy `error = setpoint − feedback`.

Kp to człon proporcjonalny, Ki całkuje w czasie, Kd różniczkuje pomiar zamiast skoku wartości zadanej. **D filter ms** filtruje pochodną. **Output min/max** ogranicza wynik, a anti-windup ogranicza narastanie całki poza dopuszczalny zakres.

Opcjonalny feedforward dodaje `FF gain × setpoint`. Wyłączony lub resetowany regulator zeruje oba wyjścia i historię. Niepodłączone setpoint, feedback i enable używają wartości właściwości; reset domyślnie wynosi 0.

### Display

Wejścia: `trigger`, `value`, `reset`. Przejście do skonfigurowanego aktywnego poziomu wysyła jeden komunikat. **Append value** dodaje wartość liczbową. Aktywacje w okresie blokady są odrzucane, nie kolejkowane; utrzymanie aktywnego triggera nie powtarza komunikatu.

Narastające zbocze reset omija blokadę i ponownie uzbraja komunikat; reset utrzymany wysoko nie powoduje powtórzeń. Symulacja pokazuje tekst na pasku stanu. Eksport emituje błąd RTAPI, bez polecenia przerwania programu NC.

## 6. Wyrażenia i odwołania

Obsługiwane operacje:

```text
+  -  *  /  %  ^  **  <<  >>
==  !=  <  <=  >  >=
and  or  not
```

`^` i `**` oznaczają potęgowanie, nie XOR. Reszta `%` ma znak dzielnika; dzielenie/modulo przez niemal zero daje zero. `pi` i `e` nie tworzą portów.

`<<` i `>>` to logiczne przesunięcia 32-bitowe z uzupełnianiem zerami: `1 << 3` daje 8, `128 >> 3` daje 16. Lewy operand jest obcinany w kierunku zera i redukowany do dolnych 32 bitów; liczby ujemne używają kodu uzupełnień do dwóch. Wysunięte bity przepadają, przesunięcie w prawo nie rozszerza znaku. Liczba pozycji musi być całkowita 0–31; inne liczby lub nieskończone/nieokreślone operandy dają zero. Następnie obowiązuje zwykła konwersja typu wyniku. Dodawanie ma pierwszeństwo przed przesunięciem: używaj nawiasów.

Funkcje: `abs`, `min`, `max`, `clamp`, `pow`, `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `log`, `log10`, `exp`, `floor`, `ceil`. Kąty w radianach; min/max przyjmują dwa argumenty, clamp trzy. Niedozwolona dziedzina lub wynik nieskończony/nieokreślony daje zero. Dowolny kod Pythona nie jest wykonywany.

```text
(n0 << 0) + (n1 << 1) + (n2 << 2) + (n3 << 3)
clamp(x * @gain, 0, @maximum)
abs(actual - requested) < tolerance
sin(angle * pi / 180)
```

`@name` wymaga istniejącej Const i nie tworzy portu. Referencje działają w parametrach liczbowych, wartościach początkowych i domyślnym enable PID. Konwersja odpowiada typowi odbiorcy; czas jest zaokrąglany do całych milisekund. Referencje stanu początkowego eksport odczytuje przy pierwszej aktualizacji. Nazwy nieznane, zastrzeżone i powtórzone są odrzucane.

## 7. Szablony Math

Szablon zapisuje się/wczytuje w właściwościach Math albo wybiera z listy. Zawiera formułę, typ wyniku, źródła/typy/wartości zmiennych i nazwę, bez przewodów. Nazwa pojawia się w nagłówku węzła.

`templates/` zawiera AND2, OR2 oraz składanie czterech/ośmiu bitów w U32. Własne szablony z tego katalogu pojawią się po odtworzeniu panelu. Przed wczytaniem szablonu lub zmianą struktury podłączonego Math/Condition/FIFO odłącz wszystkie wejścia i wyjścia. Const używane przez szablon muszą już istnieć w projekcie docelowym.

## 8. Symulacja i diagnostyka

**Simulate** zeruje historię i uruchamia kroki modelu 20 ms; **Stop** przywraca właściwości. Timer Qt nie jest harmonogramem czasu rzeczywistego. Monitor pokazuje wszystkie moduły, po jednym wierszu na wejście, stałą, wyjście i sygnał wewnętrzny. Wejścia i stałe można zmieniać; podpowiedzi zawierają pełne nazwy, typy i moduły. Wartość przetworzona różna od surowej jest pokazana osobno. Gdy wejściem steruje Const, zmień tę Const.

Zmiany wejść/stałych na żywo zachowują historię. Zmiany strukturalne i konfiguracji mogą ją wyzerować. Język i moduł zmieniają tylko widok. Symulacja nie steruje sprzętem.

## 9. Eksport, kompilacja i integracja HAL

1. Zapisz projekt JSON.
2. Eksportuj `.comp`: nazwa zaczyna się małą literą i zawiera wyłącznie małe litery, cyfry i podkreślenia, np. `machine_plc.comp`.
3. **Build .so** ponownie eksportuje graf do ostatniej ścieżki i uruchamia `halcompile --compile`.
4. Wynik to `.so`, dziennik `.build.txt`. Wymagane są narzędzia programistyczne LinuxCNC.

Kompiluj dla architektury docelowej: moduł x86 nie działa na Raspberry Pi ARM64. Edytor nie instaluje/ładuje modułu ani nie podłącza sprzętu. Komponent ma jedną funkcję `update` obejmującą wszystkie moduły i wejścia Const. Dodaj ją do istniejącego servo-thread po odczycie i przed zapisem sprzętu.

Przykład dla już zainstalowanego komponentu i istniejącego wątku:

```hal
loadrt machine_plc
addf machine-plc.update servo-thread
setp machine-plc.gain 2.5
```

Użyj rzeczywistych nazw z eksportu i połącz piny. Input czyta zewnętrzny pin HAL; Const zaczyna od wartości domyślnej i można ją zmienić przez `setp` lub sygnał.

## 10. Przykłady

### Cztery bity do U32

Cztery wejścia bit podłącz do n0…n3 szablonu Math. Dla własnej formuły wybierz zmienne bit i wynik u32:

```text
n0 + n1 * 2 + n2 * 4 + n3 * 8
```

n0=1, n1=0, n2=1, n3=0 daje 5.

### Różnica FIFO

Wejście float do FIFO, `now` i `last` do Math `now - last`. Dla szybkości zmian podziel także przez rzeczywisty okres próbkowania.

### Regulowane wzmocnienie

Const `gain`, float, 2; Input `reading`, float; Math `x * @gain`; Output `scaled`, float. Reading podłącz do x. Reading=4 daje 8; gain=3 daje 12 bez zmiany przewodów.

### Podział logiki maszyny

Utwórz moduły Wejścia, Smarowanie i Wrzeciono; przenieś węzły i połącz je w All modules. Monitor pokazuje całość, a eksport pozostaje jednym komponentem. `examples/circular-direction.json` wybiera tylko kierunek; pełna wymiana narzędzia wymaga sekwencji, zatrzasków, czujników, opóźnień i obsługi błędów.

## 11. Rozwiązywanie problemów

| Problem | Sprawdź |
| --- | --- |
| Brak wejścia wyrażenia | Źródło Input port; Constant i @referencje nie tworzą portów. |
| Zablokowana formuła/typ/szablon | Najpierw Disconnect all. |
| Czerwony typ | Automatyczna konwersja wejściowa. |
| Niewidoczny węzeł/przewód | All modules, Fit, podpowiedzi portów. |
| Const nie można usunąć / nieznana referencja | Usuń użycia / sprawdź dokładną nazwę. |
| Niedokładne opóźnienie symulacji | Krok 20 ms; HAL ma własny okres. |
| Uszkodzony projekt startowy | `--no-restore`, potem poprawny plik. |
| Błąd kompilacji | `.build.txt`, halcompile, nazwy plików/pinów. |
| FIFO nie pozwala na sprzężenie | Cykle grafu nie są obsługiwane. |
| Display nie zatrzymuje NC | Komunikat błędu nie jest poleceniem abort. |

Diagnostyka systemu/kompilatora zachowuje własny język. Katalogi są w `locales/`; brak tłumaczenia powoduje użycie angielskiego.

## 12. LinuxCNC 2.9 / 2.10

Obecne rozwojowe API 2.10 zapisuje wyjścia przez `pin_set(value)` zamiast `pin = value`. Eksport tworzy settery i warunkowe makra przypisania dla starszego halcompile 2.9. Typy `bit`, `float`, `s32`, `u32` nadal są akceptowane, ale mogą wywołać ostrzeżenia o przestarzałych nazwach.

Po aktualizacji LinuxCNC ponownie eksportuj i kompiluj jego halcompile. Stara `.so` tego nie zastępuje. Sprawdzenia obejmują kompilację na zainstalowanym 2.9 i kontrolę C z obecnym generatorem/nagłówkami HAL/RTAPI 2.10; nie oznaczają testu uruchomienia zainstalowanego 2.10 ani testu sprzętu.

## Logger: zapis historii przez trigger

**+ Logger** ma 1–18 wejść `in1`, `in2` itd. Typ (bit, float, s32, u32) wynika ze źródła; zapisywane są moduł, symbol i nazwa wyjścia. Niepodłączone wejście daje float 0. Zbocze narastające `trigger` zapisuje bufor od najstarszej próbki. HIGH zapisuje raz; przed następnym wyzwoleniem ustaw LOW. Zapis nie czyści historii.

Okres to dodatnie całe milisekundy, także `@constant`; bufor mieści 1–100000 próbek. Najwyżej jedna próbka na aktualizację; symulacja ma okres 20 ms. Trigger między próbkami zapisuje istniejącą historię. Bez próbek CSV/TSV zawiera tylko nagłówek, JSONL jest pusty. CSV/TSV zawiera nazwy i typy w nagłówku, JSONL w każdym wierszu; `time_ms` oznacza czas od startu. Format liczb: `.0g`–`.17g`, `.0f`–`.17f`, `.0e`–`.17e`; liczby całkowite pozostają dokładne. Nazwa pliku obsługuje `{timestamp}` (UTC), `{sequence}`, `{node}`. Stała nazwa atomowo zastępuje poprzedni plik. Format treści nie zależy od rozszerzenia.

Ścieżki względne odnoszą się do katalogu zapisanego projektu, a bez zapisu do katalogu edytora; w LinuxCNC do katalogu eksportu. Eksport tworzy `.comp`, `.logger.py`, `.logger.json`, `.hal`. Zainstaluj komponent przez `halcompile`, następnie wczytaj `.hal` po utworzeniu `servo-thread`. Plik ładuje komponent, uruchamia kolektor Python z modułem LinuxCNC `hal` i dodaje update. Zastąp wcześniejsze linie `loadrt`/`addf`. Zachowaj pliki razem; po przeniesieniu eksportuj ponownie ze względu na ścieżki bezwzględne.

Wątek czasu rzeczywistego wysyła ograniczone rekordy HAL; kolektor przechowuje historię i zapisuje poza realtime. Musi działać podczas próbkowania. Przepełnienie może zgubić próbki/triggery. Nowy zapis podczas trwającego zapisu tego samego Loggera jest zgłaszany i pomijany. Wyniki/błędy trafiają do paska stanu lub stderr kolektora. Duże bufory wymagają więcej pamięci. Przykład: `examples/logger-history.json`.

Kliknij blisko przewodu, także po oddaleniu widoku. Wybrany przewód jest żółty; Delete usuwa go bez usuwania node’ów. Ctrl-klik pozwala wybierać kilka przewodów.

## Globalne I/O i debugowanie Live HAL

**Globalne I/O** zarządza wspólnymi wejściami/wyjściami widocznymi we wszystkich obecnych i nowych modułach. Każdy sygnał ma jedną definicję i jeden eksportowany pin. Pozycje bloków są zapamiętywane osobno; przeciągaj ramkę/nagłówek, edytuj dwuklikiem w liście. Zwykły Input/Output można ustawić jako globalny. Usunięcie kasuje wszystkie jego połączenia. Wyjście globalne ma jedno źródło; odłącz przed zmianą. Etykieta lub **Przejdź do źródła** otwiera moduł i zaznacza node.

**Wybierz pin / sygnał HAL** oferuje wyszukiwanie i filtry typu, kierunku, zgodności. **Odśwież** asynchronicznie odczytuje `halcmd -s show pin` i `halcmd -s show sig`. Widać wartość, sygnał HAL, źródło w projekcie i pozostałe piny. Katalog można zapisać/wczytać do pracy offline. Typ jest kopiowany; usunięcie powiązania pozostawia pin do ręcznego łączenia. Wyjście wymaga IN lub sygnału bez istniejącego źródła. Istniejące nety są używane, podłączone piny nie są przepinane. Konflikty są odrzucane.

Eksport tworzy `.comp`, `.hal`, `.unload.hal`, `.test.hal`, `.test.unload.hal`, `.hal.json` i pomocniki Logger. `.hal` ładuje projekt, łączy I/O, ustawia stałe, uruchamia Logger i dodaje update do `servo-thread`. Ładuj po utworzeniu pinów sprzętu/GUI i wątku, także postgui. Motion/sprzęt pozostaje w konfiguracji maszyny. `.test.hal` łączy tylko wejścia. Pliki unload dotyczą poprawnie załadowanych konfiguracji; częściowe błędy ręcznego ładowania wymagają sprawdzenia. Live automatycznie cofa ukończone kroki przy błędzie startu.

**Debug** eksportuje piny pośrednie: `name.debug-n12-result`, FIFO `last`/`now`, PID `out`/`error`. Stałe ID i manifest zapewniają mapowanie. Zwykły eksport ich nie zawiera. **Test Live HAL** i Simulate automatycznie budują/instalują debug przez `halcompile --install` jako `nne_live_<uid>`. Potrzebne działające HAL, `servo-thread`, Python `hal` i narzędzia deweloperskie. Instalacja wymaga uprawnień; wcześniej autoryzowane `sudo -n` może pomóc, w przeciwnym razie hasło sudo jest wpisywane w ukrytym polu, bez zapisywania ani logowania. Błędy są w pasku stanu.

Tylko wejścia są połączone z maszyną. Komponent liczy realtime; Python HAL odczytuje około 20 Hz, bez równoległej symulacji Python. Wejścia przypisane są tylko do odczytu, wolne można ustawiać. Stop przed zmianami struktury. Krótkie impulsy mogą umknąć ekranowi; do historii służy Logger. Stan pokazuje czas i maksimum w µs oraz natywne `.update.time`. Jednostki HAL zależą od backendu; debug mierzy też nanosekundy przez `rtapi_get_time()`. Pomiar obejmuje instrumentowane update, nie cały servo-thread. Stop/wyjście usuwa test i jego połączenia, zachowując istniejące sygnały. Odcisk czeka na rzeczywistą aktualizację RT. Jeden test na użytkownika Unix; moduł instalowany jest używany ponownie, źródła tymczasowe usuwane. Odczyty live nie nadpisują zapisanych wartości symulacji.

Ręcznie: `sudo halcompile --install name.comp`, następnie `halcmd -f name.hal`; dla samych wejść eksport debug i `name.test.hal`. Usuń wcześniejszą instancję przed ponownym ładowaniem; instalacja nie zastępuje aktywnego modułu. RIP wymaga swojego środowiska. Przykłady: `examples/global-io.json`, `examples/hal-catalogue.json` (katalog przykładowy).

Bezpośrednie połączenie Input → Output między zewnętrznymi powiązaniami HAL tego samego typu jest eksportowane jako sieć HAL. Piny komponentu używane tylko do tego połączenia są pomijane. Przetwarzanie, konwersja, piny wewnętrzne lub różne istniejące sygnały HAL zachowują połączenie przez komponent. Wejścia zasilające również logikę wewnętrzną pozostają. Projekt samych połączeń bezpośrednich nie wymaga loadrt/addf. Debug zachowuje piny obserwacji; test Live wejść nie łączy zewnętrznych celów wyjściowych.

Live HAL zapisuje czas, wyniki kompilacji i instalacji, polecenia HAL i błędy w `.state/logs/live-hal.log` (lub `PLC_STATE_DIR/logs/live-hal.log`). Ścieżka pojawia się przy błędzie. Rotacja: 1 MiB na plik, trzy kopie. Hasła nie są logowane. Kompilacja działa w tymczasowym katalogu źródeł zamiast katalogu SSHFS.

## Counter – licznik

**+ Licznik**: wejścia `up`, `down`, `enable`, `reset` (`bit`); wyjścia `count` (`s32`), `reached` (`bit`). Zbocza narastające dodają/odejmują 1; jednoczesne zbocza znoszą się. HIGH w pierwszym cyklu jest zboczem. Wartość początkowa, próg i domyślne włączenie są konfigurowalne, także przez odwołania do stałych.

Niepodłączone wejścia mają LOW, oprócz `enable` (ustawienie domyślne, początkowo włączone). Reset HIGH przywraca wartość początkową w każdym cyklu, również po wyłączeniu. Wyłączenie zachowuje wartość. Zbocza podczas resetu/wyłączenia przepadają; utrzymane HIGH nie zlicza po ponownym włączeniu. Nasycenie: −2147483648 do 2147483647. `reached = count >= próg` jest obliczane w każdym cyklu, także podczas resetu/wyłączenia, bez zatrzasku. Wartość początkowa jest odczytywana przy starcie/resecie, próg w każdym cyklu. Restart usuwa historię.

Przykład: [counter.json](../examples/counter.json). W symulacji przełącz `pulse-up` trzy razy LOW/HIGH: wartość 3 i aktywny próg. `pulse-down` zmniejsza do 2; `clear-count` zeruje. JSON, symulacja, eksport `.comp` i monitory obsługują oba typy wyjść. Szybkie impulsy fizyczne wymagają licznika sprzętowego/enkodera.

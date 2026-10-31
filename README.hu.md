# NinjaNodeEditor

[English](README.md) · [Magyar](README.hu.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Polski](README.pl.md) · [Srpski](README.sr.md) · [Español](README.es.md)

Vizuális PLC-logikai szerkesztő és LinuxCNC HAL-komponensgenerátor Python és PySide6 alapokon. Típusos node-gráfokat szerkeszthetsz, helyben szimulálhatod őket, majd a teljes projektet `.comp` fájlként exportálhatod. A szerkesztő LinuxCNC nélkül is fut, asztali környezetben vagy Raspberry Pi-n közvetlen Qt EGLFS/KMS kijelzővel. A felület alapmérete 800 × 600.

[Részletes magyar használati útmutató](docs/USER_GUIDE.hu.md) · [MIT licenc](LICENSE)

## Funkciók

- Counter: Felfutó élre fel-/leszámlálás, reset, engedélyezés, s32 érték és küszöbjelzés. [counter.json](examples/counter.json).
- Timer: élre indítható, resetelhető időzítő egész ms-os idővel, szint- vagy impulzuskimenettel; részletek az útmutatóban.
- `bit`, `float`, `s32`, `u32` típusok, automatikus konverzió piros jelzéssel.
- Kifejezésekből létrejövő bemenetek, matematikai függvények, összehasonlítások, logikai műveletek, `<<` és `>>` biteltolás.
- Bemeneti debounce és élfigyelés; kimeneti ON/OFF késleltetés és invertálás.
- FIFO `last`/`now` mintákkal és automatikus típusátvétellel.
- PID korlátozással, anti-windup működéssel, D-szűrővel, választható feedforwarddal és error kimenettel.
- Display hibaüzenet triggerrel, cooldownnal és reset felülbírálással.
- `@név` paraméterek, exportáláskor állítható HAL input pinek.
- Math sablonok, projekten belüli modulok és csoportos szimulációs állapotmonitor.
- Hét felületi nyelv és részletes útmutató, utolsó projekt visszatöltése.
- Project, Settings, Modules, Nodes sávok; jobb alsó teljesképernyő-kapcsoló és kijelöléshez kötött tulajdonságpanel.

## Telepítés és indítás

Python 3 és a [requirements.txt](requirements.txt) szerinti PySide6 szükséges. A jelenlegi fejlesztői környezet Python 3.13-at használ. Szerkesztéshez és szimulációhoz nem kell LinuxCNC.

Letöltés vagy klónozás után:

```sh
cd NinjaNodeEditor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./run.sh --windowed
```

Az interpreter külön is megadható: `PLC_PYTHON="$PWD/.venv/bin/python" ./run.sh --windowed`.

DietPi-n a rendszerhez illeszkedő Qt/PySide6 csomagokat használhatod:

```sh
cd ~/NinjaNodeEditor
bash ./setup-dietpi.sh
./run-eglfs.sh
```

A setup script sudo-val apt frissítést és csomagtelepítést végez. Az EGLFS launcher alapértelmezése `/usr/bin/python3`, az aktivált venv-től függetlenül. Helyi konzolból indítsd, szabad kijelzővel és megfelelő eszközjogokkal. A `QT_QPA_EGLFS_KMS_CONFIG` saját kijelzőprofilt adhat meg; a mellékelt card1 profil csak megfelelő DRM-kiosztás esetén használható.

## Használat

```sh
./run.sh --windowed --project examples/bit-to-u32.json
```

Adj hozzá node-okat a Nodes sorból, állítsd a tulajdonságaikat és kösd össze a kimeneti/bemeneti pontokat. Simulate közben a jobb panel minden modul állapotát mutatja, a bemenetek és paraméterek állíthatók. Leállítva a tulajdonságpanel csak kijelölt node-nál látszik. Teljes képernyőre a jobb alsó gombbal vagy F11-gyel válthatsz; ekkor a Nodes sor marad a gráf felett.

Ctrl+S ment, Delete töröl; a görgő nagyít, az üres háttér húzása mozgatja a nézetet. Bekötött Math/Condition node szerkezete csak Disconnect all után módosítható.

`--project path.json` fájlt választ, `--no-restore` vagy `--empty` üresen indít, `--language hu` nyelvet ad meg. A projekt- és üresindítási kapcsoló kizárja egymást. Beállítások: `.state/`, felülírható `PLC_STATE_DIR`-rel. A mentetlen változások nem mentődnek automatikusan.

## Export és kompatibilitás

Export készíti a `.comp` forrást. Build .so vagy a következő parancs fordítja:

```sh
halcompile --compile machine_plc.comp
```

Ehhez LinuxCNC fejlesztői eszközök és C-fordító szükséges. A művelet nem telepít és nem tölt be modult. A célgép architektúrájára fordíts, majd a generált `update` függvényt a HAL servo-threadhez rendeld. A komponens minden modult tartalmaz.

Az exportáló a 2.10 `pin_set(...)` hívásait használja, a régi 2.9 fordítóhoz feltételes makróval. Ellenőrzés: telepített 2.9-es fordítás és jelenlegi 2.10 generátor/fejlécek; telepített 2.10 futáspróba nincs. Verzióváltáskor exportálj és fordíts újra.

## Példák és fejlesztés

Az [examples](examples) mappában bit→u32, matematikai konverzió, körirány, FIFO különbség, PID/feedforward és üzenetpéldák vannak. A körirány példa nem teljes szerszámcserélő. [templates](templates): Math sablonok; [locales](locales): UTF-8 nyelvi katalógusok.

Tesztelés PySide6 és `cc` fordító mellett:

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest test_model test_session test_ui test_i18n
```

A szimuláció nem vezérel hardvert. A program kísérleti véges adatfolyam-szerkesztő; gráfkörök, mozgásparancsok és élő HAL-monitorozás nem támogatottak. A Display hibaüzenete önmagában nem ad NC abort parancsot. Részletes telepítési, node- és hibakeresési leírás az útmutatóban található.

## Licenc

[MIT License](LICENSE), © 2026 NinjaNodeEditor contributors. A Python, PySide6/Qt és LinuxCNC saját licencei változatlanul érvényesek.

## Logger: előzmények mentése triggerrel

A **+ Logger** gombbal hozz létre naplózót, állíts be 1–18 adatbemenetet, és kösd a jeleket az `in1`, `in2` stb. pontokra. A bemenet automatikusan átveszi a forrás bit, float, s32 vagy u32 típusát. A minta a modul, a szimbólum és a kimenet nevét is tárolja. A bekötetlen bemenet float nullát ad. A `trigger` bit bemenet felfutó éle menti az aktuális ringbuffert, a legrégebbi mintától kezdve. Tartós HIGH csak egyszer ment; új mentéshez előbb LOW szükséges. A mentés nem törli az előzményeket.

## Globális I/O, LinuxCNC-hozzárendelés és Live HAL debug

A **Globális I/O** ablakban bemenetek és kimenetek adhatók hozzá és távolíthatók el. A közös bemeneti/kimeneti blokkok minden meglévő és új modulban megjelennek; minden jelnek egy definíciója és egy exportált pinje van. A blokk a kereténél/fejlécénél mozgatható, helye modulonként megmarad. A listában dupla kattintással nyitható meg a jel property oldala. Sima Input/Output is globálissá tehető a **Globális (minden modulban)** kapcsolóval. Az eltávolítás minden modulból törli a jel kapcsolatait. Globális kimenetnek egy meghajtója lehet: másik bekötés előtt bontsd a korábbit. A forrás modulnevére vagy az **Ugrás a meghajtóhoz** gombra kattintva a forrásmodul és a kijelölt meghajtó node jelenik meg középre igazítva.


## Feldolgozás és visszacsatoló memória

SR/RS tároló, hiszterézis, watchdog, rámpa, aluláteresztő/átlag/medián szűrő, állapotgép és egyciklusos memóriapár: a **Feldolgozás…** menüben. [Részletes működés, példák és mérés](PROCESSING.hu.md).

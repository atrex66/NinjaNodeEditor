# NinjaNodeEditor

[English](README.md) · [Magyar](README.hu.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Polski](README.pl.md) · [Srpski](README.sr.md) · [Español](README.es.md)

Vizuelni editor PLC logike i generator LinuxCNC HAL komponenti, napisan u Pythonu sa PySide6. Napravite tipizirane grafove, simulirajte ih lokalno i izvezite ceo projekat kao `.comp`. Editor radi bez LinuxCNC-a na radnoj površini ili direktno na Raspberry Pi ekranu preko Qt EGLFS/KMS. Interfejs je predviđen za 800 × 600.

[Detaljno uputstvo na srpskom](docs/USER_GUIDE.sr.md) · [MIT licenca](LICENSE)

## Mogućnosti

- Counter: Brojanje naviše/naniže na rastućoj ivici, reset, dozvola, s32 vrednost i izlaz praga. [counter.json](examples/counter.json).
- Timer: pokretanje ivicom, reset, cele ms i izlaz nivo/impuls; detalji u uputstvu.
- Tipovi `bit`, `float`, `s32`, `u32`; automatska konverzija označena crveno.
- Ulazi iz promenljivih izraza, matematičke funkcije, poređenja, logika i pomeranja `<<`/`>>`.
- Debounce i ivice na ulazu; ON/OFF kašnjenja i invertovanje na izlazu.
- FIFO `last`/`now` sa automatskim preuzimanjem tipa.
- PID sa granicama, anti-windup, D filterom, opcionim feedforward i error izlazom.
- Poruke greške sa triggerom, blokadom i reset zaobilaženjem.
- `@name` parametri kao podesivi HAL ulazni pinovi pri izvozu.
- Math šabloni, moduli za uređivanje i grupisani monitor simulacije.
- Sedam jezika sa uputstvima; pamćenje poslednjeg projekta.
- Project, Settings, Modules, Nodes grupe; ceo ekran dole desno i svojstva samo pri izboru čvora.

## Instaliranje i pokretanje

Python 3 i PySide6 prema [requirements.txt](requirements.txt). Trenutno razvojno okruženje koristi Python 3.13. LinuxCNC nije potreban za uređivanje ili simulaciju.

Posle preuzimanja ili kloniranja:

```sh
cd NinjaNodeEditor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./run.sh --windowed
```

Interpreter se bira i pomoću `PLC_PYTHON="$PWD/.venv/bin/python" ./run.sh --windowed`.

DietPi sa usklađenim sistemskim Qt/PySide6 paketima:

```sh
cd ~/NinjaNodeEditor
bash ./setup-dietpi.sh
./run-eglfs.sh
```

Skripta ažurira apt i instalira pakete pomoću sudo. EGLFS podrazumevano koristi `/usr/bin/python3`, nezavisno od aktivnog venv-a. Pokrenite iz lokalne konzole, sa slobodnim ekranom i pristupom uređajima. `QT_QPA_EGLFS_KMS_CONFIG` bira sopstveni profil; card1 profil zavisi od stvarnog rasporeda DRM uređaja.

## Upotreba

```sh
./run.sh --windowed --project examples/bit-to-u32.json
```

Dodajte čvorove iz Nodes grupe, podesite svojstva i povežite portove. Tokom Simulate desni panel pokazuje sve module; ulazi i parametri se menjaju uživo. Posle zaustavljanja svojstva su vidljiva samo za izabrani čvor. Dugme dole desno ili F11 uključuje ceo ekran; iznad grafa ostaje samo Nodes.

Ctrl+S čuva, Delete briše; točkić menja uvećanje, prevlačenje pozadine pomera pogled. Povezani Math/Condition menjajte tek posle Disconnect all.

`--project path.json` bira projekat, `--no-restore`/`--empty` pokreće prazno, `--language sr` bira jezik. Projektna i prazna opcija se isključuju. Podešavanja su u `.state/` ili `PLC_STATE_DIR`. Nesačuvane izmene se ne čuvaju automatski.

## Izvoz i kompatibilnost

Export pravi `.comp`; Build .so ili:

```sh
halcompile --compile machine_plc.comp
```

Potrebni su LinuxCNC razvojni alati i C kompajler. Operacija ne instalira/učitava modul. Prevodite za ciljnu arhitekturu i dodajte `update` u HAL servo-thread. Izvoz svih modula ostaje jedna komponenta.

Izvoz koristi `pin_set(...)` API 2.10 uz podršku starijem halcompile 2.9. Provereni su instalirano 2.9 prevođenje i trenutni 2.10 generator/zaglavlja; nema testa rada instaliranog 2.10. Posle promene verzije ponovo izvezite i prevedite.

## Primeri i razvoj

[examples](examples) sadrži bitove→U32, konverzije, kružni smer, FIFO razliku, PID/feedforward i poruke. Kružni smer nije potpuna izmena alata. [templates](templates): Math šabloni; [locales](locales): UTF-8 katalozi.

Testovi uz PySide6 i kompajler `cc`:

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest test_model test_session test_ui test_i18n
```

Simulacija ne upravlja hardverom. Eksperimentalni editor konačnog toka podataka ne podržava cikluse grafa, komande kretanja ili aktivno HAL praćenje. Display ne šalje NC abort komandu. Detalji instaliranja, čvorova i rešavanja problema su u uputstvu.

## Licenca

[MIT License](LICENSE), © 2026 NinjaNodeEditor contributors. Python, PySide6/Qt i LinuxCNC zadržavaju sopstvene licence.

## Logger: čuvanje istorije pomoću trigger ulaza

**+ Logger** ima 1–18 ulaza `in1`, `in2` itd. Tip (bit, float, s32, u32) automatski prati izvor; čuvaju se modul, simbol i naziv izlaza. Nepovezan ulaz daje float 0. Rastuća ivica `trigger` ulaza čuva kružni bafer, od najstarijeg uzorka. HIGH čuva jednom; pre novog okidanja vratite LOW. Čuvanje ne briše istoriju.

## Globalni I/O i Live HAL debug

**Globalni I/O** upravlja zajedničkim ulazima/izlazima u svim postojećim i novim modulima. Jedna definicija i jedan izvezeni pin po signalu. Položaj bloka pamti se po modulu; pomerajte okvir/naslov, uređujte dvostrukim klikom u listi. Običan Input/Output može postati globalan. Uklanjanje briše sve njegove veze. Globalni izlaz ima jedan izvor; raskinite staru vezu pre promene. Oznaka izvora ili **Idi do izvora** otvara modul i bira node.

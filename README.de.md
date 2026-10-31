# NinjaNodeEditor

[English](README.md) · [Magyar](README.hu.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Polski](README.pl.md) · [Srpski](README.sr.md) · [Español](README.es.md)

Visueller PLC-Logikeditor und LinuxCNC-HAL-Komponentengenerator mit Python und PySide6. Bearbeiten Sie typisierte Graphen, simulieren Sie diese lokal und exportieren Sie das gesamte Projekt als `.comp`. Der Editor läuft ohne LinuxCNC auf dem Desktop oder direkt am Raspberry-Pi-Display mit Qt EGLFS/KMS. Die Oberfläche ist für 800 × 600 ausgelegt.

[Ausführliche deutsche Anleitung](docs/USER_GUIDE.de.md) · [MIT-Lizenz](LICENSE)

## Funktionen

- Counter: Auf-/Abwärtszähler mit Flankenerkennung, Reset, Freigabe, s32-Wert und Schwellenausgang. [counter.json](examples/counter.json).
- Timer: Startflanke, Reset, ganze Millisekunden und Pegel-/Impulsausgang; Details in der Anleitung.
- Typen `bit`, `float`, `s32`, `u32`; automatische Konvertierung mit roter Kennzeichnung.
- Ausdrucksabhängige Eingänge, Mathematik, Vergleiche, Logik und Bitverschiebungen `<<`/`>>`.
- Eingangs-Entprellung und Flanken; Ausgangsverzögerungen ON/OFF und Invertierung.
- FIFO mit `last`/`now` und automatischer Typübernahme.
- PID mit Ausgangsgrenzen, Anti-Windup, D-Filter, optionalem Feedforward und error-Ausgang.
- Fehlermeldungen mit Trigger, Sperrzeit und Reset-Übersteuerung.
- `@name`-Parameter als einstellbare HAL-Eingänge beim Export.
- Math-Vorlagen, mehrere Editormodule und gruppierter Simulationsmonitor.
- Sieben Sprachen mit Anleitung; Wiederherstellung des letzten Projekts.
- Bereiche Project, Settings, Modules, Nodes; Vollbildschalter unten rechts und Eigenschaften nur bei Auswahl.

## Installation und Start

Benötigt werden Python 3 und PySide6 gemäß [requirements.txt](requirements.txt). Die aktuelle Entwicklungsumgebung verwendet Python 3.13. Bearbeitung und Simulation benötigen kein LinuxCNC.

Nach Herunterladen oder Klonen:

```sh
cd NinjaNodeEditor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./run.sh --windowed
```

Interpreter ausdrücklich wählen: `PLC_PYTHON="$PWD/.venv/bin/python" ./run.sh --windowed`.

DietPi mit passenden Qt/PySide6-Systempaketen:

```sh
cd ~/NinjaNodeEditor
bash ./setup-dietpi.sh
./run-eglfs.sh
```

Das Setup aktualisiert apt und installiert Pakete mit sudo. EGLFS verwendet standardmäßig `/usr/bin/python3`, unabhängig von einer aktivierten venv. Von der lokalen Konsole mit freier Anzeige und passenden Geräterechten starten. `QT_QPA_EGLFS_KMS_CONFIG` wählt eine eigene Displaykonfiguration; das card1-Profil erfordert die passende DRM-Gerätezuordnung.

## Bedienung

```sh
./run.sh --windowed --project examples/bit-to-u32.json
```

Knoten im Bereich Nodes hinzufügen, Eigenschaften einstellen und Ausgangs-/Eingangsports verbinden. Während Simulate zeigt der rechte Monitor alle Module; Eingänge und Parameter sind veränderbar. Im gestoppten Zustand erscheinen Eigenschaften nur bei Knotenauswahl. Unten rechts oder mit F11 auf Vollbild umschalten; über dem Graphen bleibt nur Nodes.

Strg+S speichert, Entf löscht; Mausrad zoomt, Ziehen des Hintergrunds verschiebt die Ansicht. Verbundene Math-/Condition-Strukturen erst nach Disconnect all ändern.

`--project path.json` öffnet eine Datei, `--no-restore`/`--empty` startet leer, `--language de` wählt die Sprache. Projekt- und Leerstartoption schließen sich aus. Einstellungen liegen in `.state/`, überschreibbar mit `PLC_STATE_DIR`. Ungespeicherte Änderungen werden nicht automatisch gespeichert.

## Export und Kompatibilität

Export erstellt `.comp`; Build .so oder folgendes Kommando kompiliert:

```sh
halcompile --compile machine_plc.comp
```

LinuxCNC-Entwicklungswerkzeuge und C-Compiler sind erforderlich. Dies installiert/lädt kein Modul. Für die Zielarchitektur kompilieren und die generierte `update`-Funktion in den HAL-Servo-Thread einfügen. Alle Module werden gemeinsam exportiert.

Der Export verwendet 2.10-Setter `pin_set(...)` mit bedingtem Ersatz für ältere 2.9-Generatoren. Geprüft: installierte 2.9-Kompilierung und aktuelle 2.10-Generator-/Headerprüfung; kein installiertes 2.10-Laufzeittesten. Nach Versionswechsel erneut exportieren und bauen.

## Beispiele und Entwicklung

[examples](examples) enthält Bit→U32, mathematische Konvertierung, Kreisrichtung, FIFO-Differenz, PID/Feedforward und Meldungen. Die Kreisrichtung ist kein vollständiger Werkzeugwechsel. [templates](templates) enthält Math-Vorlagen, [locales](locales) UTF-8-Kataloge.

Tests mit PySide6 und C-Compiler `cc`:

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest test_model test_session test_ui test_i18n
```

Die Simulation steuert keine Hardware. Experimenteller endlicher Datenfluss: Graphzyklen, Bewegungsbefehle und Live-HAL-Monitor fehlen. Display sendet keine NC-Abbruchkommandos. Details zu Installation, Knoten und Fehlerbehebung finden Sie in der Anleitung.

## Lizenz

[MIT License](LICENSE), © 2026 NinjaNodeEditor contributors. Python, PySide6/Qt und LinuxCNC behalten ihre eigenen Lizenzen.

## Logger: Verlauf per Trigger speichern

**+ Logger** bietet 1–18 Eingänge `in1`, `in2` usw. Typen (bit, float, s32, u32) folgen automatisch der Quelle; Modul, Signal und Ausgangsname werden mitgespeichert. Unverbundene Eingänge liefern float 0. Die steigende Flanke von `trigger` speichert den Ringpuffer chronologisch. HIGH speichert einmal; vor dem nächsten Trigger LOW setzen. Der Verlauf bleibt erhalten.

## Globale I/O und Live HAL-Debugging

**Globale I/O** verwaltet gemeinsame Ein-/Ausgänge, sichtbar in allen vorhandenen und neuen Modulen. Jede Definition wird einmal exportiert; Blockpositionen bleiben pro Modul erhalten. Rahmen/Kopf zum Verschieben, Doppelklick in der Verwaltung zum Bearbeiten. Normale Input/Output-Nodes können mit **Global (alle Module)** umgeschaltet werden. Entfernen löscht alle zugehörigen Verbindungen. Globale Ausgänge haben einen Treiber; vor einem Wechsel trennen. Quellenbeschriftung oder **Zum Treiber springen** öffnet dessen Modul und markiert den Node.

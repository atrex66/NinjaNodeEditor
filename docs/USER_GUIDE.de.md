# NinjaNodeEditor — ausführliche Bedienungsanleitung

Mit NinjaNodeEditor bearbeiten Sie die Logik einer vollständigen PLC-Komponente als Knotengraph, simulieren sie lokal und exportieren LinuxCNC-Quellcode im Format `.comp`. Die Simulation ist nicht mit einem laufenden HAL oder mit Hardware verbunden. **Build .so** kompiliert lediglich; Installation und Laden erfolgen separat.

## Inhalt

1. Start und Sprache
2. Oberfläche und Bearbeitung
3. Projekte und Module
4. Typen und Konvertierung
5. Knoten
6. Ausdrücke und Parameterreferenzen
7. Math-Vorlagen
8. Simulation und Fehlersuche
9. Export, Kompilierung und HAL-Integration
10. Beispiele
11. Fehlerbehebung
12. LinuxCNC 2.9 / 2.10

## 1. Start und Sprache

Starten Sie auf dem Raspberry Pi aus dem Programmverzeichnis:

```sh
cd ~/NinjaNodeEditor
./run-eglfs.sh
```

Auf dem Desktop verwenden Sie `./run.sh --windowed`. EGLFS benötigt passende Qt-EGLFS/KMS-Bibliotheken und Zugriff auf Anzeige und Eingabegeräte. Eine andere Anwendung kann die Anzeige bereits belegen. Unter DietPi installiert `bash ./setup-dietpi.sh` die passenden Systempakete. Der EGLFS-Starter verwendet standardmäßig `/usr/bin/python3`. Einen anderen Interpreter wählen Sie ausdrücklich:

```sh
PLC_PYTHON="$PWD/.venv/bin/python" ./run-eglfs.sh
```

| Option | Wirkung |
| --- | --- |
| `--project path.json` | Dieses Projekt statt der zuletzt gespeicherten Auswahl öffnen. |
| `--no-restore` / `--empty` | Leer starten, ohne das gemerkte Projekt einzulesen. |
| `--windowed` | Fensterbetrieb anfordern. |
| `--language de` | Sprache beim Start wählen. |
| `--screenshot /tmp/preview.png` | Fensteraufnahme speichern und beenden. |

`--project` und `--no-restore` schließen sich gegenseitig aus. Die Sprachauswahl bietet Englisch (`en`), Ungarisch (`hu`), Deutsch (`de`), Französisch (`fr`), Polnisch (`pl`), Serbisch in lateinischer Schrift (`sr`) und Spanisch (`es`). Änderungen gelten sofort und werden gespeichert. `--language` oder `PLC_LANGUAGE` überschreibt die Startauswahl; ohne gespeicherte Auswahl gilt Englisch. **Manual** öffnet die Anleitung in der aktuellen Sprache, bei fehlender Datei auf Englisch.

Bezeichner, Formeln, Modul-/Vorlagennamen und eigene Meldungen werden nicht übersetzt. Einstellungen liegen unter `.state/`; mit `PLC_STATE_DIR` lässt sich ein anderes Verzeichnis wählen.

## 2. Oberfläche und Bearbeitung

Oben stehen die Projektaktionen, darunter Sprach-, Anleitungs-, Simulations- und Modulsteuerung. Die Schaltflächen zum Hinzufügen von Knoten bilden die unterste Werkzeugzeile. Links befindet sich der Graph, rechts das Eigenschaftenfenster.

Die Werkzeuggruppen heißen **Projekt**, **Einstellungen**, **Module**, **Knoten**, in dieser Reihenfolge. Mit **Vollbild** unten rechts oder **F11** bleibt nur die Knotenleiste über dem Graphen. Dieselbe Taste/Schaltfläche stellt die normale Arbeitsansicht wieder her; unter EGLFS bleibt die physische Anzeige im Vollbild. Bei gestoppter Simulation erscheinen Eigenschaften nur für ausgewählte Knoten; ein Klick auf den leeren Hintergrund blendet sie aus und vergrößert die Zeichenfläche. Während der Simulation bleibt der Zustandsmonitor ohne Auswahl sichtbar. Der Ansichtswechsel erhält Graph und Simulationsverlauf.

Projekt, Einstellungen und Module sind kompakte Zeilen mit der Beschriftung am Anfang. Knoten behält den beschrifteten Rahmen; so bleibt auf kleinen Bildschirmen mehr Platz.

| Aktion | Bedienung |
| --- | --- |
| Knoten erstellen/auswählen/verschieben | Passende `+`-Schaltfläche; Knotenkörper anklicken oder ziehen. |
| Mehrere Knoten auswählen | Strg gedrückt halten und klicken. |
| Verbinden | Ausgang und dann Eingang anklicken oder Verbindung ziehen. |
| Verbindung abbrechen | Escape. |
| Ansicht verschieben / zoomen | Leeren Hintergrund ziehen / Mausrad. |
| Gesamten Graph anzeigen | **Fit**. |
| Löschen / speichern | Entf / Strg+S oder entsprechende Schaltfläche. |

Gelbe Eingänge empfangen, blaue Ausgänge liefern Signale. Ein Eingang hat eine Quelle; eine neue Verbindung ersetzt die alte. **Disconnect inputs** entfernt Eingangsverbindungen, **Disconnect all** sämtliche Verbindungen des Knotens.

Textänderungen werden beim Verlassen des Felds übernommen. Im Ausdrucksfeld bestätigt Enter; Umschalt+Enter fügt einen Zeilenumbruch ein. Zahlenänderungen werden nach abgeschlossener Eingabe übernommen, nicht nach jedem unvollständigen Zwischenwert.

## 3. Projekte und Module

Die Projekt-JSON enthält Knoten, Parameter, Verbindungen, Positionen und Module. Normalerweise wird das zuletzt erfolgreich geöffnete oder gespeicherte Projekt wiederhergestellt. Ohne gemerkte Datei erscheint eine Demonstration. Ungespeicherte Änderungen werden nicht automatisch gespeichert. **New** öffnet einen leeren Graphen, ohne den gemerkten Dateinamen zu löschen. Bei fehlenden oder ungültigen Dateien startet das Programm leer und meldet den Fehler; öffnen Sie dann ein gültiges Projekt.

Module strukturieren die Bearbeitung einer einzigen Komponente. **New module** erstellt eine Gruppe, **Rename** benennt sie um, **Move selected** verschiebt Knoten. **Remove module** verschiebt ihre Knoten unter Erhalt aller Verbindungen in das erste verbleibende Modul; mindestens eines bleibt erhalten. **All modules** zeigt alle Knoten und ermöglicht modulübergreifende Verbindungen.

Verborgene modulübergreifende Verbindungen bleiben aktiv. Die Port-Hilfe zeigt das andere Modul und den Knoten. Simulation, Konstanten und HAL-Namen gelten projektweit; der Export enthält alle Module. Neue Knoten gehören zum gewählten Modul, in der Gesamtansicht zum ersten Modul. Format 4 speichert die Modulstruktur. Formate 1–3 bleiben lesbar und erhalten Main als Modul; ältere Editoren lesen Format 4 möglicherweise nicht.

## 4. Typen und Konvertierung

| Typ | Bedeutung |
| --- | --- |
| `bit` | 0 oder 1; jeder von null verschiedene Zahlenwert wird wahr. |
| `float` | Gleitkommazahl mit doppelter Genauigkeit. |
| `s32` | Vorzeichenbehaftet, −2147483648…2147483647. |
| `u32` | Vorzeichenlos, 0…4294967295. |

Unterschiedliche Typen können verbunden werden. Am empfangenden Eingang wird automatisch konvertiert; rote Beschriftung zeigt dies an. Ganzzahlkonvertierung schneidet zur null hin ab und begrenzt auf den Wertebereich: `3.9` → s32 `3`, `-2` → u32 `0`.

Entprellung, Ein-/Ausschaltverzögerung, Meldesperrzeit und PID-D-Filter werden in ganzen Millisekunden mit 1-ms-Schritten eingestellt. Null deaktiviert die Verzögerung beziehungsweise den Filter. Die reale Auflösung hängt vom Update-Zyklus ab; die 20-ms-Simulation löst keine einzelnen 1-ms-Ereignisse auf.

## 5. Knoten

### Input

Externer HAL-Eingang mit eindeutigem Namen, beginnend mit einem Kleinbuchstaben; Ziffern und Bindestriche sind möglich, etwa `pressure` oder `door-closed`. **Simulated input** liefert den lokalen Rohwert; Bitwerte lassen sich auch über den Simulationstext im Knoten umschalten.

Bitverarbeitung: Invertierung, Entprellung, Flankenerkennung. Die Entprellung verlangt eine stabile Änderung über die eingestellte Zeit. `level` liefert den stabilen Pegel; `rising`, `falling` und `both` liefern Impulse von einem Update. Ein anfangs aktiver Eingang kann einen steigenden Impuls erzeugen. Im Export kommt der Wert vom echten HAL-Pin; Simulationseinstellungen ersetzen keine Verdrahtung.

### Output

Externer HAL-Ausgang mit einem `in`-Port. Ohne Verbindung gilt der Anfangswert/-zustand. Ein-/Ausschaltverzögerungen verlangen eine anhaltende Anforderung; kehrt diese zurück, entfällt der vorgemerkte Übergang. Invertierung folgt auf die Verzögerung. Der Anfangszustand setzt den gespeicherten logischen Zustand beim Start.

### Const

Benannter typisierter Parameter mit Standardwert, ohne Ports. Ausdrücke verwenden `@gain`; Zahlenfelder bieten einen Referenzwähler. Namen beginnen klein und dürfen Ziffern sowie Unterstriche enthalten. `@speed_limit` wird zu `<component>.speed-limit`.

Jede Const wird als HAL-**Eingangspin** mit Standardwert exportiert und kann über `setp` oder ein Signal geändert werden. Ihr eigener Standardwert muss ein Literal sein, keine weitere Referenz. Vor dem Löschen müssen alle Verwendungen entfernt werden.

### Math und Condition

Ausdrucksvariablen erzeugen automatisch Eingänge mit Typ, Quelle und Standardwert. **Input port** erzeugt einen Port; **Constant** verwendet den eingestellten Wert ohne Port. Variablenwerte dürfen `@name` referenzieren.

Math liefert `result` mit wählbarem Typ. Condition liefert komplementäre Bits `true` und `false`, keine Ausführungszweige. Bei verbundenen Knoten sind strukturelle Formel-, Typ-, Quellen- und Vorlagenänderungen bis **Disconnect all** gesperrt.

### Invert

Logisches NICHT eines Bits. Ein unverbundener Eingang gilt als 0; der Ausgang ist dann 1.

### FIFO

`now` ist die aktuelle Probe, `last` die des vorherigen Updates. Beim ersten Update nutzt `last` den Anfangswert. Die angeschlossene Quelle bestimmt die Typen aller Ports; ohne Verbindung ist ein Ersatztyp wählbar.

Jedes Update übernimmt eine Probe, auch bei unverändertem Wert. Dies ist ein Verlauf aus zwei Proben, keine Warteschlange mit push/pop. Rückkopplungskreise bleiben verboten, da `now` vom aktuellen Eingang abhängt.

### Timer / Zeitüberschreitung

**+ Timer** hat die Bit-Eingänge `trigger`, `reset` und den Bit-Ausgang `out`. **Dauer ms** ist ganzzahlig, nichtnegativ, in 1-ms-Schritten, standardmäßig 1000; Const-Referenzen sind möglich. Eine steigende Triggerflanke startet, auch ein anfangs hoher Trigger im ersten Update. Fallen des Triggers bricht nicht ab; weitere Flanken während des Laufs werden ignoriert. Die Dauer wird beim Start übernommen und bleibt für diesen Lauf fest. Der Start setzt den Zähler auf 0; folgende Update-Perioden zählen weiter. Null läuft sofort ab.

Ausgangsmodus `level`: nach Ablauf bleibt `out=1` bis Reset, weitere Starts sind gesperrt. `pulse`: beim Ablauf ein Update lang 1, danach 0; eine neue steigende Flanke kann erneut starten. Reset ist pegelaktiv und hat Vorrang: HIGH bricht ab und löscht den Ausgang. Ein durch Reset hindurch hoher Trigger startet beim Freigeben nicht neu; er muss erst fallen und steigen. Reset im Ablaufzyklus unterdrückt den Ausgang. Unverbundene Eingänge sind 0. Simulation: 20-ms-Schritte; HAL: Threadperiode. Ungültige/nichtpositive Perioden löschen den Zustand.

Für Timeout den Start an trigger und erfolgreiche Fertigmeldung an reset anschließen. Pegel für gespeicherten Fehler, Impuls für eine Meldung. [timeout.json](../examples/timeout.json) zeigt 1000 ms, HAL-Timeoutausgang und Display. Simulationsstart/-stopp löscht den Verlauf.

### PID

Eingänge: `setpoint`, `feedback`, `enable`, `reset`. Float-Ausgänge: `out`, `error`. Im aktiven Zustand gilt `error = setpoint − feedback`.

Kp ist proportional, Ki integriert zeitabhängig und Kd differenziert die gemessene Rückführung statt des Sollwertsprungs. **D filter ms** filtert den D-Anteil. **Output min/max** begrenzt das Ergebnis; Anti-Windup begrenzt das Integralwachstum nach außen.

Optional addiert Feedforward `FF gain × setpoint`. Bei deaktiviertem Regler oder Reset werden beide Ausgänge null und der Verlauf gelöscht. Unverbundene Sollwert-, Rückführungs- und Freigabeeingänge nutzen Eigenschaftenwerte; Reset ist standardmäßig 0.

### Display

Eingänge: `trigger`, `value`, `reset`. Eintritt in den eingestellten aktiven Triggerpegel erzeugt eine Meldung. **Append value** ergänzt den Zahlenwert. Aktivierungen während der Sperrzeit werden verworfen, nicht vorgemerkt; ein dauerhaft aktiver Trigger wiederholt die Meldung nicht.

Eine steigende Resetflanke umgeht die Sperrzeit und aktiviert die Auslösung erneut; ein dauerhaft hoher Reset wiederholt nichts. Simulation zeigt die Meldung in der Statuszeile. Export erzeugt eine RTAPI-Fehlermeldung, keinen NC-Abbruchbefehl.

## 6. Ausdrücke und Parameterreferenzen

Unterstützte Operationen:

```text
+  -  *  /  %  ^  **  <<  >>
==  !=  <  <=  >  >=
and  or  not
```

`^` und `**` bedeuten Potenzierung, nicht XOR. Der Modulo-Rest folgt dem Vorzeichen des Divisors; Division/Modulo durch einen nahezu null großen Divisor ergibt null. `pi` und `e` erzeugen keine Ports.

`<<` und `>>` sind logische 32-Bit-Verschiebungen mit Nullauffüllung: `1 << 3` ergibt 8, `128 >> 3` ergibt 16. Der linke Operand wird zur null hin abgeschnitten und auf die unteren 32 Bits reduziert; negative Werte verwenden das Zweierkomplement. Herausgeschobene Bits entfallen, Rechtsverschiebung erweitert nicht das Vorzeichen. Ganzzahlige Anzahlen 0–31 sind erlaubt; ungültige Anzahlen oder nicht endliche Operanden ergeben null. Danach gilt die normale Ergebniskonvertierung. Addition bindet stärker als Verschiebung: verschobene Terme einklammern.

Funktionen: `abs`, `min`, `max`, `clamp`, `pow`, `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `log`, `log10`, `exp`, `floor`, `ceil`. Winkel in Radiant; min/max benötigen zwei Argumente, clamp drei. Ungültige Funktionsbereiche oder nicht endliche Ergebnisse ergeben null. Beliebiger Python-Code wird nicht ausgeführt.

```text
(n0 << 0) + (n1 << 1) + (n2 << 2) + (n3 << 3)
clamp(x * @gain, 0, @maximum)
abs(actual - requested) < tolerance
sin(angle * pi / 180)
```

`@name` benötigt eine vorhandene Const und erzeugt keinen Ausdrucksport. Zahlenparameter, Anfangswerte und die Standardfreigabe des PID können Referenzen verwenden. Konvertierung folgt dem Zieltyp; Zeiten werden auf ganze Millisekunden gerundet. Anfangszustandsreferenzen werden im ersten Update gelesen. Doppelte, reservierte und unbekannte Namen werden abgelehnt.

## 7. Math-Vorlagen

Im Eigenschaftenfenster können Sie Vorlagen speichern/laden oder über die Liste wählen. Sie enthalten Formel, Ergebnistyp, Variablenquellen/-typen/-werte und Namen, aber keine Verbindungen. Der Name wird zur Knotenüberschrift.

`templates/` enthält AND2, OR2 und vier/acht Bit zu U32. Eigene Vorlagen erscheinen nach erneutem Aufbau des Eigenschaftenfensters. Vor einem Vorlagenwechsel oder einer Strukturänderung verbundener Math-/Condition-/FIFO-Knoten alle Ein- und Ausgänge trennen. Referenzierte Const-Knoten müssen im Zielprojekt bereits existieren.

## 8. Simulation und Fehlersuche

**Simulate** setzt den Verlauf zurück und startet 20-ms-Modellschritte; **Stop** stellt die Eigenschaftenansicht wieder her. Der Qt-Timer ist kein Echtzeit-Scheduler. Der Monitor zeigt alle Module: eine Zeile je Eingang, Konstante, Ausgang und internem Signal. Eingänge und Konstanten sind direkt veränderbar. Tooltips zeigen vollständige Namen, Typen und Module; vom Rohwert abweichende verarbeitete Eingangswerte erscheinen zusätzlich. Bei Const-gesteuerten Eingangswerten die Const ändern.

Live-Änderungen an Eingängen und Konstanten erhalten den Verlauf. Struktur- und sonstige Konfigurationsänderungen können ihn zurücksetzen. Modul-/Sprachwechsel ändern nur die Ansicht. Die Simulation steuert keine Hardware.

## 9. Export, Kompilierung und HAL-Integration

1. Projekt als JSON speichern.
2. `.comp` exportieren: Dateiname beginnt mit einem Kleinbuchstaben und enthält nur Kleinbuchstaben, Ziffern und Unterstriche, etwa `machine_plc.comp`.
3. **Build .so** exportiert den aktuellen Graph erneut zum letzten Exportpfad und startet `halcompile --compile`.
4. Ergebnis: `.so`; Protokoll: `.build.txt`. LinuxCNC-Entwicklungswerkzeuge sind erforderlich.

Für die Zielarchitektur kompilieren: ein x86-Modul läuft nicht auf dem ARM64-Pi. Der Editor installiert/lädt keine Module und verbindet keine Hardware. Die Komponente enthält alle Module und Const-Eingänge in einer `update`-Funktion. Diese gehört im vorhandenen Servo-Thread nach dem Lesen und vor dem Schreiben der Hardware.

Beispiel für eine bereits installierte Komponente und einen vorhandenen Thread:

```hal
loadrt machine_plc
addf machine-plc.update servo-thread
setp machine-plc.gain 2.5
```

Die tatsächlichen Namen aus Ihrem Export verwenden und Pins passend verbinden. Input liest externe HAL-Pins; Const startet mit dem Standardwert und ist per `setp` oder Signal änderbar.

## 10. Beispiele

### Vier Bits zu U32

Vier Bit-Inputs an n0…n3 der Vier-Bit-Math-Vorlage anschließen. Bei eigener Formel Variablen auf bit und Ergebnis auf u32 setzen:

```text
n0 + n1 * 2 + n2 * 4 + n3 * 8
```

n0=1, n1=0, n2=1, n3=0 ergibt 5.

### FIFO-Differenz

Float-Input an FIFO, `now`/`last` an Math `now - last`. Für eine Änderungsrate zusätzlich durch die tatsächliche Abtastperiode teilen.

### Einstellbare Verstärkung

Const `gain`, float, 2; Input `reading`, float; Math `x * @gain`; Output `scaled`, float. Reading an x anschließen. Reading=4 ergibt 8, gain=3 ergibt 12 ohne neue Verbindungen.

### Maschinenlogik aufteilen

Module für Eingänge, Schmierung und Spindel erstellen, Knoten verschieben und in All modules verbinden. Monitor und Export erfassen alle Module als eine Komponente. `examples/circular-direction.json` wählt nur die Richtung; ein vollständiger Werkzeugwechsel benötigt Ablaufsteuerung, Verriegelung, Sensoren, Verzögerungen und Fehlerbehandlung.

## 11. Fehlerbehebung

| Problem | Prüfung |
| --- | --- |
| Ausdrucksport fehlt | Quelle Input port; Constant und @Referenzen erzeugen keine Ports. |
| Formel/Typ/Vorlage gesperrt | Zuerst Disconnect all. |
| Rote Typbeschriftung | Konvertierung von Quelle zu Eingang prüfen. |
| Knoten/Verbindung unsichtbar | All modules, Fit und Port-Hilfe verwenden. |
| Const nicht löschbar / Referenz unbekannt | Verwendungen entfernen / exakten Namen prüfen. |
| Ungenaue Simulationszeit | 20-ms-Modellschritte; HAL hat eine eigene Update-Periode. |
| Startprojekt fehlerhaft | `--no-restore`, dann gültige Datei öffnen. |
| Build fehlgeschlagen | `.build.txt`, halcompile und Datei-/Pinnamen prüfen. |
| FIFO-Rückkopplung abgelehnt | Graphzyklen werden nicht unterstützt. |
| Display stoppt NC nicht | Fehlermeldung ist kein Abbruchbefehl. |

Betriebssystem-/Compilerdiagnosen behalten ihre eigene Sprache. Kataloge liegen unter `locales/`; fehlende Übersetzungen fallen auf Englisch zurück.

## 12. LinuxCNC 2.9 / 2.10

Die aktuelle 2.10-Entwicklungs-API schreibt Ausgänge mit `pin_set(value)` statt `pin = value`. Der Export erzeugt Setter mit bedingtem Zuweisungsersatz für ältere 2.9-halcompile-Versionen. Die bisherigen Typnamen `bit`, `float`, `s32`, `u32` werden noch akzeptiert, möglicherweise mit Veraltungswarnungen.

Nach einem LinuxCNC-Upgrade mit dessen halcompile erneut exportieren und kompilieren. Eine alte `.so` ersetzt dies nicht. Geprüft wurden installierte 2.9-Kompilierung und C-Prüfungen mit aktuellem 2.10-Generator sowie HAL/RTAPI-Headern; dies ist kein Laufzeit- oder Hardwaretest mit installiertem 2.10.

## Logger: Verlauf per Trigger speichern

**+ Logger** bietet 1–18 Eingänge `in1`, `in2` usw. Typen (bit, float, s32, u32) folgen automatisch der Quelle; Modul, Signal und Ausgangsname werden mitgespeichert. Unverbundene Eingänge liefern float 0. Die steigende Flanke von `trigger` speichert den Ringpuffer chronologisch. HIGH speichert einmal; vor dem nächsten Trigger LOW setzen. Der Verlauf bleibt erhalten.

Abtastzeit: positive ganze Millisekunden, auch `@constant`; Ringpuffer: 1–100000 Messwerte. Höchstens ein Messwert pro Update, Simulation mit 20 ms. Zwischen Abtastungen wird der vorhandene Verlauf gespeichert. Ohne Messwerte entstehen nur CSV/TSV-Kopfzeilen bzw. eine leere JSONL-Datei. CSV/TSV enthalten Signalnamen und Typen im Kopf, JSONL in jeder Zeile; `time_ms` ist die verstrichene Zeit. Zahlenformat: `.0g`–`.17g`, `.0f`–`.17f`, `.0e`–`.17e`; Ganzzahlen bleiben exakt. Dateinamen unterstützen `{timestamp}` (UTC), `{sequence}`, `{node}`. Feste Namen ersetzen die vorige Datei atomar. Das gewählte Format bestimmt den Inhalt, unabhängig von der Dateiendung.

Relative Pfade beziehen sich in der Simulation auf das gespeicherte Projekt, sonst auf das Editorverzeichnis; in LinuxCNC auf das Exportverzeichnis. Export erzeugt `.comp`, `.logger.py`, `.logger.json`, `.hal`. Komponente mit `halcompile` installieren und die generierte `.hal` nach Erstellung von `servo-thread` laden. Sie lädt Komponente und Python-Sammler (LinuxCNC-Modul `hal`) und fügt die Updatefunktion hinzu. Bisherige `loadrt`/`addf`-Zeilen ersetzen. Dateien zusammenhalten; nach Verschieben neu exportieren, da absolute Hilfsdateipfade enthalten sind.

Realtime sendet begrenzte HAL-Stream-Datensätze; der Sammler hält den Ringpuffer und schreibt außerhalb Realtime. Sammler beim Abtasten laufen lassen. Überläufe können Messwerte/Trigger verlieren; bei laufendem Speichern werden weitere Speicheranforderungen für denselben Logger gemeldet und verworfen. Ergebnisse/Fehler erscheinen im Simulationsstatus oder auf stderr des Sammlers. Große Puffer benötigen mehr Speicher. Beispiel: `examples/logger-history.json`.

Leitungen nahe der Linie anklicken, auch herausgezoomt. Auswahl wird gelb; Delete löscht Leitungen ohne ihre Nodes. Ctrl-Klick ermöglicht Mehrfachauswahl.

## Globale I/O und Live HAL-Debugging

**Globale I/O** verwaltet gemeinsame Ein-/Ausgänge, sichtbar in allen vorhandenen und neuen Modulen. Jede Definition wird einmal exportiert; Blockpositionen bleiben pro Modul erhalten. Rahmen/Kopf zum Verschieben, Doppelklick in der Verwaltung zum Bearbeiten. Normale Input/Output-Nodes können mit **Global (alle Module)** umgeschaltet werden. Entfernen löscht alle zugehörigen Verbindungen. Globale Ausgänge haben einen Treiber; vor einem Wechsel trennen. Quellenbeschriftung oder **Zum Treiber springen** öffnet dessen Modul und markiert den Node.

**HAL-Pin / Signal wählen** öffnet die Suche mit Typ-, Richtungs- und Kompatibilitätsfilter. **Aktualisieren** liest asynchron `halcmd -s show pin` und `halcmd -s show sig`. Anzeige: Wert, HAL-Signal, Projekttreiber und andere Signalmitglieder. Katalog laden/speichern ermöglicht Offline-Arbeit. Typen werden übernommen; Zuordnung löschen lässt einen manuell verdrahtbaren Pin. Ausgänge benötigen einen IN-Pin bzw. ein Signal ohne Treiber. Bestehende Netze werden verwendet, belegte Pins nicht umgehängt. Konflikte werden abgewiesen.

Export erzeugt `.comp`, `.hal`, `.unload.hal`, `.test.hal`, `.test.unload.hal`, `.hal.json` und gegebenenfalls Logger-Helfer. `.hal` lädt das gesamte Projekt mit I/O, Konstanten, Logger und update in `servo-thread`, nachdem Hardware-/GUI-Pins und Thread vorhanden sind; auch postgui möglich. Motion/Hardware bleibt in der Maschinenkonfiguration. `.test.hal` verdrahtet nur Eingänge. Unload-Dateien gehören zu erfolgreich geladenen Setups; teilweise fehlgeschlagene manuelle Loads müssen geprüft werden. Live-Startfehler rollen erfolgreiche Schritte automatisch zurück.

**Debug** exportiert Zwischenpins wie `name.debug-n12-result`, FIFO `last`/`now`, PID `out`/`error`; stabile Node-IDs und Manifest halten die Zuordnung. Normalexport enthält diese Pins nicht. **Live HAL-Test** und Simulate bauen/installieren automatisch einen Debug-Test mittels `halcompile --install` und laden `nne_live_<uid>`. Erfordert laufendes HAL, `servo-thread`, Python `hal` und Entwicklungstools. Installation braucht Schreibrechte; bereits erlaubtes `sudo -n` kann verwendet werden, andernfalls wird das sudo-Passwort verdeckt abgefragt und weder gespeichert noch protokolliert. Fehler erscheinen im Status.

Nur Eingänge werden extern verbunden. Der kompilierte Realtime-Code liefert die Anzeige über Python HAL mit etwa 20 Hz; lokale Simulation läuft dabei nicht. Gebundene Eingänge sind schreibgeschützt, freie Eingänge einstellbar. Strukturänderungen erfordern Stop. Kurze Pulse können zwischen Anzeigen fehlen; Logger speichert Historie. Status zeigt gemessene Laufzeit/Maximum in µs sowie das originale `.update.time`. Native HAL-Zeiten haben backendabhängige Takte; Debug misst zusätzlich Nanosekunden mit `rtapi_get_time()`. Die µs-Zeit umfasst den instrumentierten update-Rumpf, nicht den ganzen Servo-Thread. Stop/Exit entfernt Testkomponente und ihre Verbindungen, vorhandene Signale bleiben. Fingerabdruck wartet auf ein echtes RT-Update. Ein Live-Test pro Unix-Benutzer; installierter Test wird wiederverwendet, temporäre Quellen gelöscht. Live-Werte überschreiben keine gespeicherten Simulationsvorgaben.

Manuell: `sudo halcompile --install name.comp`, dann `halcmd -f name.hal`; für Eingangs-Test Debug-Export und `name.test.hal`. Vor Neuladen die vorige Instanz entfernen. Installation ersetzt kein geladenes Modul; RIP benötigt seine Buildumgebung. Beispiele: `examples/global-io.json`, `examples/hal-catalogue.json` (Beispielkatalog, keine reale Maschine).

Eine direkte Input → Output-Verbindung zwischen externen HAL-Zuordnungen gleichen Typs wird als HAL-Netz exportiert. Nur dafür verwendete Komponentenpins entfallen. Verarbeitung, Typkonvertierung, interne Komponentenpins oder verschiedene bestehende HAL-Signale behalten den Weg durch die Komponente. Eingänge für zusätzliche interne Logik bleiben erhalten. Reine Direktverbindungen benötigen kein loadrt/addf. Debug behält Beobachtungspins; der Live-Eingangstest verbindet keine externen Ausgangsziele.

Live HAL protokolliert Zeitstempel, Build-/Installationsausgabe, HAL-Befehle und Fehler in `.state/logs/live-hal.log` (oder `PLC_STATE_DIR/logs/live-hal.log`). Bei Fehlern erscheint der Pfad im Status. Rotation: 1 MiB pro Datei, drei Sicherungen. Passwörter werden nicht protokolliert. Der Build läuft im temporären Quellverzeichnis statt im SSHFS-Arbeitsverzeichnis.

## Counter – Zähler

**+ Zähler**: Eingänge `up`, `down`, `enable`, `reset` (`bit`); Ausgänge `count` (`s32`), `reached` (`bit`). Steigende Flanken addieren/subtrahieren 1; gleichzeitige Flanken heben sich auf. HIGH beim ersten Zyklus zählt als Flanke. Startwert, Schwelle und Standardfreigabe sind einstellbar, auch über Konstantenreferenzen.

Unverbundene Eingänge sind LOW, außer `enable` (Standardfreigabe, anfangs aktiv). Reset HIGH stellt bei jedem Zyklus den Startwert wieder her, auch deaktiviert. Deaktivierung hält den Wert. Flanken während Reset/Deaktivierung werden verworfen; gehaltenes HIGH zählt bei Freigabe nicht erneut. Sättigung: −2147483648 bis 2147483647. `reached = count >= Schwelle` wird auch bei Reset/Deaktivierung in jedem Zyklus ausgewertet und nicht gespeichert. Startwert: beim Start/Reset; Schwelle: in jedem Zyklus. Neustart verwirft den Zustand.

Beispiel: [counter.json](../examples/counter.json). In der Simulation `pulse-up` dreimal aus/einschalten: Wert 3, Schwellenausgang an. `pulse-down` senkt auf 2, `clear-count` setzt auf 0. JSON, Simulation, `.comp` und Debug-Monitore unterstützen beide Ausgangstypen. Gezählt werden nur abgetastete Flanken; schnelle physische Impulse benötigen Hardwarezähler/Encoder.

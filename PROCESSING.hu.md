# Feldolgozás és egyciklusos memória

Az új node-ok a **Node-ok → Feldolgozás…** menüből érhetők el. A szerkesztő magyar fordítást tartalmaz; az új kifejezések más nyelveken egyelőre angolul jelennek meg. A gráf szimulálható, menthető és a szokásos módon `.comp` + HAL-bekötés formájában exportálható. A feldolgozás a generált komponens `update` függvényében fut, nem a Qt-felület időzítőjében.

## Node-ok

| Node | Bemenet | Kimenet és működés |
| --- | --- | --- |
| SR/RS tároló | set, reset | out és not; választható SET- vagy RESET-elsőbbség; kezdőállapot |
| Hiszterézis | in, reset | out: felső küszöbnél 1, alsónál 0, közötte tartás; reset kezdőállapotra |
| Watchdog | trigger, enable, reset | healthy, fault, elapsed-ms; felfutó vagy mindkét él figyelése; választható tárolt hiba |
| Rámpa | in, enable, reset | out, reached; külön fel- és lefutási sebesség egység/s mértékegységben |
| Jelszűrő | in, enable, reset | out; aluláteresztő, mozgóátlag vagy medián |
| Állapotgép | advance0…advanceN, enable, reset | state, done, fault és active0…activeN |
| Memória írás / olvasás | író: in | olvasó: out; név szerint közös, egy ciklust tároló memória |

### Watchdog

Az engedélyezett felügyelet minden megfelelő életjel-él után új időkorlátot kezd. A folyamatosan HIGH jel nem jelent ismétlődő életjelet. Induláskor az időkorlátnak megfelelő türelmi idő van. A `latched` opcióval a hiba új életjel után is megmarad, amíg resetet nem kap; kikapcsolva a következő megfelelő él törli. A reset és az enable=0 törli a hibát/időt, és healthy=0 állapotot ad. Reset/tiltás alatt az érkező élek nem tárolódnak későbbre.

A felbontást a HAL-ciklus adja: 1 ms-os szálban a felügyelet ciklushatárokon értékelődik ki. Ez a node más jelek kimaradását érzékeli; a saját HAL-szál teljes megállását ugyanabban a megállt szálban nem tudja jelezni.

### Rámpa és szűrők

A rámpa az aktuális HAL-periódussal számol. Például 10 egység/s mellett egy 1 ms-os ciklus legfeljebb 0,01 egységet változtat. A 0 sebesség az adott irányban tartást jelent. Reset kezdőértékre állít, enable=0 tartja az állapotot. `reached` akkor igaz, ha a kimenet elérte a célt.

Aluláteresztő: `alpha = dt / (tau + dt)`, `out = (1-alpha)*előző + alpha*in`. A 0 időállandó pozitív ciklusidő mellett átenged. Az átlag és medián 1–63 mintát használ; induláskor csak a már beérkezett mintákkal számol. Páros számú mintánál a medián a két középső átlaga. Reset törli az előzményeket és kezdőértéket ad, tiltás tartja a kimenetet és az előzményeket. Az ablak mintaszám, tehát 1 ms-os szálban 63 minta 63 ms-nyi mintavételt fed le. A műveletek korlátosak, nincs ciklusonkénti memóriafoglalás a generált C-ben.

### Állapotgép

Az **Állapotok szerkesztése…** ablakban 2–16 állapot adható meg névvel, következő állapotszámmal és időkorláttal. Kezdőállapot: 0; az utolsó sor a végállapot. Minden állapotnak saját `advanceN` feltétele van: ennek felfutó éle léptet a beállított célra, ciklusonként legfeljebb egyszer. A cél lehet korábbi állapot is. Inaktív állapothoz érkező vagy tiltás közbeni él nem várakozik sorban.

Időkorlát 0: nincs időfelügyelet. Időtúllépéskor `fault=1`, a léptetés megáll, minden active kimenet 0. Ha az időkorlát és az átmenet ugyanabban a ciklusban következik be, a hiba élvez elsőbbséget. Reset törli a hibát és visszalép 0-ba. Tiltáskor az állapot és az eltelt idő megmarad. A végállapotban done=1; új ciklushoz reset szükséges. Állapotszám változtatása előtt a node kapcsolatait bontani kell.

## Visszacsatoló memóriapár

A **Memóriapár** művelet együtt hozza létre az írót és olvasót. A **Memória beállítása…** ablakban a név, típus és kezdőérték az egész csoporton együtt módosul. A két node külön modulba mozgatható; a memória neve az egész projekten belül közös, nem csak az adott modulban.

1. A ciklus elején az olvasók a tárolt értéket használják.
2. A gráf minden node-ja egyszer kiértékelődik.
3. Az írók értéke a ciklus végén kerül a memóriába.

Ez **pontosan egy ciklus késleltetés**: 1 ms-os HAL-szálnál 1 ms. A node-ok létrehozási és kiértékelési sorrendje nem módosítja ezt. Példa: `Memória olvasás → Math(x+1) → Memória írás` ciklusonként növelő visszacsatolás. A közvetlen, tároló nélküli kör továbbra is tiltott.

Egy névhez legfeljebb egy író, azonos típusú olvasók és egyező kezdőérték tartozhat. Az író bekötés nélkül nullát ír; író nélküli olvasó a kezdőértéket tartja. A memória szimuláció-resetkor vagy a HAL-komponens újratöltésekor inicializálódik; nem lemezre mentett üzemi állapot.

## Példák

- `examples/processing-chain.json`: bemenet → szűrő → rámpa → hiszterézis, külön watchdog.
- `examples/feedback-memory.json`: egyciklusos visszacsatolás két modul között.
- `examples/state-sequence.json`: várakozás, megmunkálás, kész állapot és időfelügyelet.

## Ellenőrzés és teljesítmény

A Python-szimuláció és az exportált, valóban lefordított C összehasonlító tesztjei az összes új kimenetet és üzemmódot lefedik, debug exporttal is. Külön vizsgált a reset/tiltás, küszöbök, tartott életjel, időtúllépési elsőbbség, szűrők feltöltődése és 63 mintás ablaka, valamint a memóriák ciklushatára és típuskonverziója.

A natív mérés reprodukálása a célgépen:

```sh
python3 benchmarks/processing_bench.py /tmp/processing-bench
cd /tmp/processing-bench
cc -O2 -std=c11 processing_bench.c -lm -o processing_bench
./processing_bench 60000
```

Ez szünet nélkül ismételt számítási időmérés, a node-ok számára 1 ms-os periódussal. Nem HAL-ébresztési jitter, nem fizikai I/O mérés. Az eredmény adott gráfra, gépre és futási körülményekre vonatkozik; nem általános valós idejű felső korlát. A natív HAL-fordítás külön ellenőrizhető: `/opt/automation-hal/bin/ahal compile --compile processing_bench.comp`.
